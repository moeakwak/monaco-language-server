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
current workspace_dir_path: app/cpp_workspace

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

## Client

Just use `monaco-languageclient`.