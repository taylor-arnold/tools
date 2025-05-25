"""Command line interface for ptools."""

import glob
import logging
import re
import subprocess
import sys
from pathlib import Path

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode
import click
import colorama
from colorama import Fore, Style

from . import __version__

# Initialize colorama for cross-platform colored output
colorama.init()


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log messages."""
    
    def format(self, record):
        if record.levelno >= logging.ERROR:
            color = Fore.RED
        elif record.levelno >= logging.WARNING:
            color = Fore.YELLOW
        else:
            color = Fore.GREEN
        
        return f"{color}{record.getMessage()}{Style.RESET_ALL}"


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create a custom handler with colored formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter())
    
    # Configure the root logger
    logging.basicConfig(
        level=level,
        handlers=[handler],
        format="%(message)s"  # Simple format since ColoredFormatter handles the actual formatting
    )


def run_latex_workflow(tex_file: Path, latex_cmd: str) -> None:
    """Run the complete LaTeX workflow: latex -> latex -> bibtex -> latex -> latex -> cleanup."""
    logger = logging.getLogger(__name__)
    
    if not tex_file.exists():
        raise click.ClickException(f"File not found: {tex_file}")
    
    if tex_file.suffix != ".tex":
        raise click.ClickException(f"File must have .tex extension: {tex_file}")
    
    base_name = tex_file.stem
    work_dir = tex_file.parent
    
    def run_cmd(cmd: list[str], description: str) -> None:
        """Run a command and handle errors."""
        logger.debug(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout and logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"{description} stdout: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"{description} failed")
            if e.stdout:
                click.echo(f"STDOUT:\n{e.stdout}", err=True)
            if e.stderr:
                click.echo(f"STDERR:\n{e.stderr}", err=True)
            raise click.ClickException(f"{description} failed with exit code {e.returncode}")
    
    # Run latex twice
    run_cmd([latex_cmd, "-interaction=nonstopmode", tex_file.name], f"{latex_cmd} (1st pass)")
    run_cmd([latex_cmd, "-interaction=nonstopmode", tex_file.name], f"{latex_cmd} (2nd pass)")
    
    # Run bibtex if .bib files exist or .aux contains citations
    aux_file = work_dir / f"{base_name}.aux"
    if aux_file.exists():
        aux_content = aux_file.read_text()
        if "\\citation" in aux_content or "\\bibdata" in aux_content:
            run_cmd(["bibtex", base_name], "bibtex")
            # Run latex twice more after bibtex
            run_cmd([latex_cmd, "-interaction=nonstopmode", tex_file.name], f"{latex_cmd} (3rd pass)")
            run_cmd([latex_cmd, "-interaction=nonstopmode", tex_file.name], f"{latex_cmd} (4th pass)")
    
    # Cleanup auxiliary files
    cleanup_patterns = [
        f"{base_name}.aux",
        f"{base_name}.log", 
        f"{base_name}.bbl",
        f"{base_name}.blg",
        f"{base_name}.fls",
        f"{base_name}.fdb_latexmk",
        f"{base_name}.synctex.gz",
        f"{base_name}.out",
        f"{base_name}.toc",
        f"{base_name}.lof",
        f"{base_name}.lot",
        f"{base_name}.nav",
        f"{base_name}.snm",
        f"{base_name}.vrb"
    ]
    
    for pattern in cleanup_patterns:
        for file_path in work_dir.glob(pattern):
            logger.debug(f"Removing {file_path}")
            file_path.unlink(missing_ok=True)
    
    logger.info(f"Successfully processed {tex_file}")


@click.group()
@click.version_option(version=__version__)
@click.option(
    "-v", "--verbose", 
    is_flag=True, 
    help="Enable verbose logging"
)
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """ptools - LaTeX and document processing tools."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@main.command()
@click.argument("tex_file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def xelatex(ctx: click.Context, tex_file: Path) -> None:
    """Compile LaTeX document using XeLaTeX."""
    run_latex_workflow(tex_file, "xelatex")


@main.command()
@click.argument("tex_file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def pdflatex(ctx: click.Context, tex_file: Path) -> None:
    """Compile LaTeX document using pdfLaTeX."""
    run_latex_workflow(tex_file, "pdflatex")


@main.command()
@click.argument("tex_file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def texcount(ctx: click.Context, tex_file: Path) -> None:
    """Count words in LaTeX document using texcount."""
    logger = logging.getLogger(__name__)
    
    if not tex_file.exists():
        raise click.ClickException(f"File not found: {tex_file}")
    
    if tex_file.suffix != ".tex":
        raise click.ClickException(f"File must have .tex extension: {tex_file}")
    
    try:
        result = subprocess.run(
            ["texcount", str(tex_file)],
            capture_output=True,
            text=True,
            check=True
        )
        click.echo(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("texcount failed")
        if e.stderr:
            click.echo(f"STDERR:\n{e.stderr}", err=True)
        raise click.ClickException(f"texcount failed with exit code {e.returncode}")
    except FileNotFoundError:
        raise click.ClickException("texcount command not found. Please install texcount.")


class CustomBibTexWriter(BibTexWriter):
    """Custom BibTeX writer with consistent formatting."""
    
    def __init__(self):
        super().__init__()
        self.indent = '  '
        self.align_values = True
        self.order_entries_by = 'id'
        self.add_trailing_comma = False
        self.common_strings = []


@main.command()
@click.argument("bib_file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def bsort(ctx: click.Context, bib_file: Path) -> None:
    """Sort bibliography entries in a .bib file."""
    logger = logging.getLogger(__name__)
    
    if not bib_file.exists():
        raise click.ClickException(f"File not found: {bib_file}")
    
    if bib_file.suffix != ".bib":
        raise click.ClickException(f"File must have .bib extension: {bib_file}")
    
    try:
        # Read and parse the bibliography file
        with open(bib_file, 'r', encoding='utf-8') as bibtex_file:
            parser = bibtexparser.bparser.BibTexParser()
            parser.customization = convert_to_unicode
            bib_database = bibtexparser.load(bibtex_file, parser=parser)
        
        # Sort entries by citation key (case-insensitive)
        bib_database.entries.sort(key=lambda entry: entry.get('ID', '').lower())
        
        # Write the sorted bibliography back to file
        writer = CustomBibTexWriter()
        with open(bib_file, 'w', encoding='utf-8') as bibtex_file:
            bibtexparser.dump(bib_database, bibtex_file, writer=writer)
        
        logger.info(f"Successfully sorted and formatted {len(bib_database.entries)} entries in {bib_file}")
        click.echo(f"Sorted and formatted {len(bib_database.entries)} bibliography entries")
        
    except Exception as e:
        logger.error(f"Failed to sort bibliography: {e}")
        raise click.ClickException(f"Failed to sort bibliography: {e}")


if __name__ == "__main__":
    main()