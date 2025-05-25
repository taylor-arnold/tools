
```
  # Install dependencies
  uv sync --dev

  # Run the CLI
  uv run ptools xelatex paper.tex
  uv run ptools pdflatex document.tex
  uv run ptools texcount article.tex
  uv run ptools bsort references.bib

  # Run tests
  uv run pytest

  # Lint code
  uv run ruff check

```

To create a Python environment that can run this CLI (and others)
directly anywhere on your machine, use the following code:

```
  uv venv ~/.local/uv-tools
  source ~/.local/uv-tools/bin/activate
  python -m ensurepip --upgrade
  python3 -m pip install --upgrade pip
  python3 -m pip install yt-dlp

  python3 -m pip install git+https://github.com/taylor-arnold/ptools.git

  export PATH="$HOME/.local/uv-tools/bin:$PATH"
```

