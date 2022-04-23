# monaco-language-server

This is a simple language server example in Python.

Supports:
- python (pyls)
- c++ (ccls or clangd)

## Usage

First, Install `ccls` (or `clangd`) and confirm `ccls --version` has output.

```
sudo apt-get -y ccls
```

Then install requirements:

```shell
pip3 install -r requirements.txt
```

Edit configuration `app/config.yaml` if needed.

```yaml
host: 0.0.0.0
port: 3000      # change the port if in use
# ...
```

Run `server.py`:

```shell
python3 -u server.py
```

The output should look like:

```
*******************************************
WebSocket Language Server For Monaco Editor
*******************************************
use config: app/config.yaml
current rootUri: app/cpp_workspace

all commands:
- python: pyls -v
- cpp: ccls --init={
    "capabilities": {
    "foldingRangeProvider":false
    },
    "index":{
    "onChange":true,
    "trackDependency":2
    }
}


Started Web Socket at:
- python: ws://0.0.0.0:3000/python
- cpp: ws://0.0.0.0:3000/cpp
```

## Configuration

### Formatting

To configure formatting in `ccls`, just set `.clang-format` in `app/cpp_workspace`.

## Client

Use `monaco-languageclient` and `@codingame/monaco-jsonrpc`.

```js
const {
  MonacoLanguageClient,
  CloseAction,
  ErrorAction,
  MonacoServices,
  createConnection,
} = require("monaco-languageclient");

import { listen } from "@codingame/monaco-jsonrpc";

// ...
```

To use `ccls`/`clangd`, files should sycronized to server. `server.py` provide a `/file` api to update files.

The client should:
1. connect `ws://.../file` via WebSocket
2. send message `"get_rootUri"` to get absolute path of `rootUri` in MonacoServer
```js
let webSocket = new WebSocket("ws://" + serverHost + "/file");
webSocket.onopen = () => {
  webSocket.send(JSON.stringify({ type: "get_rootUri" }));
};
webSocket.onmessage = (ev) => {
  let message = JSON.parse(ev.data);
  if (message.result == "ok") {
      rootUri = message.data;
  } else {
      // ...
  }
  webSocket.close();
};

```
3. Use this path as `rootUri` option:
```js
const { MonacoServices } = require("monaco-languageclient");
MonacoServices.install(monaco, { rootUri });
```
4. Use `file://filename` uri to create model:
```js
let model = monaco.editor.createModel(code, language, monaco.Uri.parse("file://" + filename));
```
5. Update file if monaco editor changed (create if `filename` not exists)
```js
monaco_model.onDidChangeContent((e) => {
  if (lang == "cpp") {
    console.log("try to update file");
    updateFile(filename, monaco_model.getValue());
  }
});

function updateFile(filename, code) {
  let url = "ws://" + serverHost + "/file";
  if (!!fileWebSocket && fileWebSocket.readyState == fileWebSocket.OPEN) {
    // reuse opening fileWebSocket
    fileWebSocket.send(JSON.stringify({ type: "update", filename, code }));
  } else {
    fileWebSocket = new WebSocket(url);
    fileWebSocket.onopen = (ev) => {
      fileWebSocket.send(JSON.stringify({ type: "update", filename, code }));
    };
    fileWebSocket.onmessage = (ev) => {
      let message = JSON.parse(ev.data);
      if (message.result == "ok") {
        console.log("update file success:", filename);
      } else {
        console.warn("update file failed:", ev);
      }
    };
  }
}
```