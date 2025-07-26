# Tools

A collection of commandline tools that I use to organise my work across several 
different projects. Mostly meant for my own use but provided for reference in 
case others find them useful.

To create a Python environment that can run these CLIs directly anywhere on the
machine, use the following code:

```
  # do this once to create the environment
  uv venv ~/.local/uv-tools
  source ~/.local/uv-tools/bin/activate
  python -m ensurepip --upgrade
  python3 -m pip install --upgrade pip
  python3 -m pip install yt-dlp

  # run this in each directory and then repeat for each tool
  python3 -m pip install .

  # add this to your your start-up script
  export PATH="$HOME/.local/uv-tools/bin:$PATH"
```