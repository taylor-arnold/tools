"""Command line interface for ptools."""

import glob
import logging
import re
import subprocess
import sys
from pathlib import Path

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


def format_bib_entry(entry: str) -> str:
    """Format a single bibliography entry with consistent style."""
    lines = entry.strip().split('\n')
    if not lines:
        return entry
    
    # Parse the first line to get entry type and key
    first_line = lines[0].strip()
    if not first_line.startswith('@'):
        return entry
    
    # Extract entry type and citation key
    match = re.match(r'@(\w+)\s*\{\s*([^,\s\}]+)\s*,?', first_line)
    if not match:
        return entry
    
    entry_type = match.group(1).lower()
    citation_key = match.group(2)
    
    # Start building the formatted entry - entry type and citation key on same line
    formatted_lines = [f"@{entry_type}" + "{" + citation_key + ","]
    
    # Collect all fields
    fields = []
    current_field = ""
    in_field = False
    brace_count = 0
    
    # Process all lines to extract fields
    for i, line in enumerate(lines):
        if i == 0:  # Skip the first line (entry type)
            continue
            
        stripped = line.strip()
        if not stripped or stripped == '}':
            if current_field.strip():
                fields.append(current_field.strip())
                current_field = ""
            continue
        
        # Handle multi-line fields
        if not in_field and '=' in stripped:
            # New field starts
            if current_field.strip():
                fields.append(current_field.strip())
            current_field = stripped
            in_field = True
            brace_count = stripped.count('{') - stripped.count('}')
        else:
            # Continuation of current field
            current_field += " " + stripped
            brace_count += stripped.count('{') - stripped.count('}')
        
        # Check if field is complete (braces balanced and ends with comma or is last)
        if in_field and brace_count <= 0 and (stripped.endswith(',') or stripped.endswith('}')):
            fields.append(current_field.strip())
            current_field = ""
            in_field = False
            brace_count = 0
    
    # Add any remaining field
    if current_field.strip():
        fields.append(current_field.strip())
    
    # Format each field
    for field in fields:
        if '=' not in field:
            continue
            
        # Parse field = value
        field_parts = field.split('=', 1)
        field_name = field_parts[0].strip()
        field_value = field_parts[1].strip()
        
        # Remove trailing comma if present
        if field_value.endswith(','):
            field_value = field_value[:-1].strip()
        
        # Convert quotes to curly braces if needed
        if field_value.startswith('"') and field_value.endswith('"'):
            field_value = '{' + field_value[1:-1] + '}'
        elif not (field_value.startswith('{') and field_value.endswith('}')):
            # If it's not already in braces and not a number, wrap it
            if not field_value.isdigit():
                field_value = '{' + field_value + '}'
        
        # Format with equals sign in column 16
        spaces_needed = max(1, 16 - len(field_name) - 1)  # -1 for the space before =
        formatted_field = f"  {field_name}{' ' * spaces_needed}= {field_value},"
        formatted_lines.append(formatted_field)
    
    # Remove trailing comma from last field
    if formatted_lines and formatted_lines[-1].endswith(','):
        formatted_lines[-1] = formatted_lines[-1][:-1]
    
    # Close the entry
    formatted_lines.append("}")
    
    return '\n'.join(formatted_lines)


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
        # Read the file content
        content = bib_file.read_text(encoding='utf-8')
        
        # Parse bibliography entries
        entries = []
        current_entry = []
        in_entry = False
        brace_count = 0
        
        for line in content.split('\n'):
            stripped = line.strip()
            
            # Start of new entry
            if stripped.startswith('@') and not in_entry:
                if current_entry:
                    entries.append('\n'.join(current_entry))
                current_entry = [line]
                in_entry = True
                brace_count = line.count('{') - line.count('}')
            elif in_entry:
                current_entry.append(line)
                brace_count += line.count('{') - line.count('}')
                
                # End of entry when braces are balanced
                if brace_count <= 0:
                    entries.append('\n'.join(current_entry))
                    current_entry = []
                    in_entry = False
                    brace_count = 0
            elif not stripped and not in_entry:
                # Preserve empty lines between entries
                if current_entry:
                    entries.append('\n'.join(current_entry))
                    current_entry = []
        
        # Add any remaining entry
        if current_entry:
            entries.append('\n'.join(current_entry))
        
        # Sort entries by citation key (on the first line after formatting)
        def get_citation_key(entry: str) -> str:
            lines = entry.split('\n')
            # After formatting, citation key is on the first line: @type{key,
            first_line = lines[0].strip()
            if '{' in first_line:
                key_part = first_line.split('{', 1)[1]
                if key_part.endswith(','):
                    return key_part[:-1].strip().lower()
                return key_part.strip().lower()
            return entry.lower()
        
        # Filter out empty entries, format, and sort
        non_empty_entries = [e for e in entries if e.strip()]
        formatted_entries = [format_bib_entry(entry) for entry in non_empty_entries]
        sorted_entries = sorted(formatted_entries, key=get_citation_key)
        
        # Write back to file
        sorted_content = '\n\n'.join(sorted_entries)
        if sorted_content and not sorted_content.endswith('\n'):
            sorted_content += '\n'
            
        bib_file.write_text(sorted_content, encoding='utf-8')
        
        logger.info(f"Successfully sorted and formatted {len(sorted_entries)} entries in {bib_file}")
        click.echo(f"Sorted and formatted {len(sorted_entries)} bibliography entries")
        
    except Exception as e:
        logger.error(f"Failed to sort bibliography: {e}")
        raise click.ClickException(f"Failed to sort bibliography: {e}")


if __name__ == "__main__":
    main()