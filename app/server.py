import logging
import os
import re
import ssl
import subprocess
import threading
import argparse
import yaml
from datetime import datetime

from tornado import ioloop, process, web, websocket, httpserver

from pylsp_jsonrpc import streams

try:
    import ujson as json
except Exception:  # pylint: disable=broad-except
    import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("server.log".format(
            datetime.now().strftime("%Y%m%d-%H%M%S"))),
        logging.StreamHandler()
    ]
)

log = logging.getLogger(__name__)

enable_ssl = False


class JsonRpcStreamLogWriter(streams.JsonRpcStreamWriter):
    def write(self, ip, message):
        log.info("({}) < {}".format(ip, str(message)))
        return super().write(message)


class LogRequestHandler(web.RequestHandler):
    debug = False

    def initialize(self, debug) -> None:
        self.debug = debug

    def get(self):
        if self.debug:
            content = ""
            with open("server.log", "r") as f:
                if f:
                    content = """
                    <textarea style="width: 100%; height: 100%;">{}</textarea>
                    """.format(f.read())
                else:
                    content = "Cannot read server log"
            self.finish(content)
        else:
            self.set_status(400, "debug is off")
            self.finish()


class HomeRequestHandler(web.RequestHandler):
    commands = None

    def initialize(self, commands) -> None:
        self.commands = commands

    def get(self):
        self.write("""
        <h1>Language Server</h1>
        <h2>Support Languages</h2>
        <p>{}</p>
        <h2>Usage</h2>
        Use WebSocket connect {}://localhost/<language_name>
        """.format(" ".join(
            [lang for lang in self.commands.keys()]
        ), "wss" if enable_ssl else "ws"))


class FileServerWebSocketHandler(websocket.WebSocketHandler):
    rootUri = None

    def initialize(self, rootUri) -> None:
        self.rootUri = rootUri

    def open(self, *args, **kwargs):
        log.info("new FileServerWebSocketHandler request")

    def on_message(self, message):
        message = json.loads(message)
        if message['type'] == 'get_rootUri':
            self.write_message(json.dumps(
                {'result': 'ok', 'data': rootUri}))
        elif message['type'] == 'update':
            if 'filename' not in message or 'code' not in message:
                self.write_message(json.dumps(
                    {'result': 'error', 'description': 'no filename or code'}))
            else:
                filename = message['filename']
                code = message['code']
                with open(os.path.join(rootUri, filename), 'w') as f:
                    f.write(code)
                log.info("update file {} with {} characters".format(
                    filename, len(code)))
                self.write_message(json.dumps({'result': 'ok'}))
        else:
            self.write_message(json.dumps(
                {'result': 'error', 'description': 'no such type'}))

    def check_origin(self, origin):
        return True


class LanguageServerWebSocketHandler(websocket.WebSocketHandler):
    writer = None
    lang = None
    commands = None
    uri = None

    def initialize(self, commands) -> None:
        self.commands = commands

    def open(self, *args, **kwargs):
        if args[0] not in self.commands:
            self.close(1001, "language {} is not supported".format((args[0])))
            return

        self.lang = args[0]
        log.info("Spawning {} subprocess".format(self.lang))

        # Create an instance of the language server
        proc = process.Subprocess(
            self.commands[self.lang], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        # Create a writer that formats json messages with the correct LSP headers
        self.writer = JsonRpcStreamLogWriter(proc.stdin)

        # Create a reader for consuming stdout of the language server. We need to
        # consume this in another thread
        def consume():
            # Start a tornado IOLoop for reading/writing to the process in this thread
            ioloop.IOLoop()
            reader = streams.JsonRpcStreamReader(proc.stdout)
            reader.listen(lambda msg: self.write_message(json.dumps(msg)))

        thread = threading.Thread(target=consume)
        thread.daemon = True
        thread.start()

    def on_message(self, message):
        """Forward client->server messages to the endpoint."""
        message = json.loads(message)
        # fix "invalid params of textDocument/codeAction: expected int" problem in ccls
        try:
            for each in message["params"]['context']['diagnostics']:
                if "code" in each and str.isnumeric(each["code"]):
                    each["code"] = int(each["code"])
        except KeyError:
            pass
        ip = self.request.remote_ip
        log.info("({}) > {}".format(ip, str(message)))
        self.writer.write(ip, message)

    # def on_close(self):
    #     pass

    def check_origin(self, origin):
        return True


if __name__ == "__main__":
    welcome = "WebSocket Language Server For Monaco Editor"
    print("*" * (len(welcome)) + "\n" + welcome + "\n" + "*" * (len(welcome)))
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str,
                        default="config.yml", help="yaml configuration")
    args = parser.parse_args()

    file_dir_path = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(file_dir_path, args.config)

    if not os.path.isfile(config_path):
        log.error("config file {} not exits!".format(config_path))
        exit(1)

    config = None
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    rootUri = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "cpp_workspace")
    if not os.path.exists(rootUri):
        os.makedirs(rootUri)

    print("use config: {}\ncurrent rootUri: {}\n".format(
        config_path, rootUri))

    debug = False
    if "debug" in config:
        debug = config["debug"]

    app = web.Application([
        (r"/", HomeRequestHandler, dict(commands=config['commands'])),
        (r"/log", LogRequestHandler, dict(debug=debug)),
        (r"/file", FileServerWebSocketHandler,
         dict(rootUri=rootUri)),
        (r"/(.*)", LanguageServerWebSocketHandler,
         dict(commands=config['commands']))
    ])

    # ssl config
    if "ssl" in config and os.path.exists(os.path.join(file_dir_path, config["ssl"]["crt"])) and os.path.exists(os.path.join(file_dir_path, config["ssl"]["key"])):
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(os.path.join(file_dir_path, config["ssl"]["crt"]),
                                os.path.join(file_dir_path, config["ssl"]["key"]))
        server = httpserver.HTTPServer(app, ssl_options=ssl_ctx)
        enable_ssl = True
    else:
        server = httpserver.HTTPServer(app)
        enable_ssl = False

    print("all commands:\n" + "\n".join(
        ["  - {}: {}".format(lang, " ".join(config['commands'][lang]))
         for lang in config['commands'].keys()]
    ))
    print("\nStarted Web Socket at:\n" + "\n".join(
        ["  - {}: {}://{}:{}/{}".format(lang, "wss" if enable_ssl else "ws", config['host'],
                                        config['port'], lang) for lang in config['commands'].keys()])
    )

    if debug:
        print("Visit {}://{}:{}/log to see log.".format("https" if enable_ssl else "http", config['host'],
                                                        config['port']))
    else:
        print("Option debug is off.")

    if "clean_files_on_start" in config and config["clean_files_on_start"]:
        for f in os.listdir(rootUri):
            p = os.path.join(rootUri, f)
            if os.path.isfile(p) and re.match(r"(.+)\.(cpp|js|py|go|txt|c|java)", f):
                os.remove(p)

    server.listen(config['port'], address=config['host'])
    ioloop.IOLoop.current().start()
