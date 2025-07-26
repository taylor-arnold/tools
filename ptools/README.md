
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


## Shell Autocompletion

To enable tab completion for `ptools` commands, run:

```bash
ptools completion
```

This will show instructions for your shell. For example, with bash:

```bash
# Add to ~/.bashrc for persistent completion
eval "$(_PTOOLS_COMPLETE=bash_source ptools)"
```

Or generate a completion script file:

```bash
_PTOOLS_COMPLETE=bash_source ptools > ~/.ptools-complete.bash
echo 'source ~/.ptools-complete.bash' >> ~/.bashrc
```

After setup, restart your shell and you'll have tab completion for:
- Command names (`ptools x<TAB>` → `ptools xelatex`)
- File paths for arguments
- Option names

