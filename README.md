

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