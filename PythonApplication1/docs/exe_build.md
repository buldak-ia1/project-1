# MetaSort EXE Build

## Build

- Install PyInstaller if needed: `python -m pip install pyinstaller`.
- Run `powershell -ExecutionPolicy Bypass -File build_exe.ps1`.
- The output file is `dist\MetaSort\MetaSort.exe`.

## Runtime Behavior

- Running `MetaSort.exe` starts the local MetaSort web server.
- The default browser opens `http://127.0.0.1:8765`.
- A small console window stays open so you can stop the server with `Ctrl+C` or by closing the window.
- If port `8765` is already in use, MetaSort picks an available local port and opens that URL.
- Bundled `frontend` and default `config` are read from the EXE resources.
- User runtime files such as `config`, `demo_input`, and `demo_output` are created in `%LOCALAPPDATA%\MetaSort`, not inside the rebuildable `dist` folder.
- The light EXE excludes heavy optional CLIP dependencies; visual embeddings fall back to local heuristics unless a future full-model build is added.
