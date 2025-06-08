"""Tests for the CLI module."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from ptools.cli import main


def test_main_help():
    """Test that the main command shows help."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "ptools - LaTeX and document processing tools" in result.output


def test_version():
    """Test version option."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_xelatex_help():
    """Test xelatex command help."""
    runner = CliRunner()
    result = runner.invoke(main, ["xelatex", "--help"])
    assert result.exit_code == 0
    assert "Compile LaTeX document using XeLaTeX" in result.output


def test_pdflatex_help():
    """Test pdflatex command help."""
    runner = CliRunner()
    result = runner.invoke(main, ["pdflatex", "--help"])
    assert result.exit_code == 0
    assert "Compile LaTeX document using pdfLaTeX" in result.output


def test_texcount_help():
    """Test texcount command help."""
    runner = CliRunner()
    result = runner.invoke(main, ["texcount", "--help"])
    assert result.exit_code == 0
    assert "Count words in LaTeX document" in result.output


def test_bsort_help():
    """Test bsort command help."""
    runner = CliRunner()
    result = runner.invoke(main, ["bsort", "--help"])
    assert result.exit_code == 0
    assert "Sort bibliography entries" in result.output


def test_xelatex_file_not_found():
    """Test xelatex with non-existent file."""
    runner = CliRunner()
    result = runner.invoke(main, ["xelatex", "nonexistent.tex"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_pdflatex_file_not_found():
    """Test pdflatex with non-existent file."""
    runner = CliRunner()
    result = runner.invoke(main, ["pdflatex", "nonexistent.tex"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_texcount_file_not_found():
    """Test texcount with non-existent file."""
    runner = CliRunner()
    result = runner.invoke(main, ["texcount", "nonexistent.tex"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_bsort_file_not_found():
    """Test bsort with non-existent file."""
    runner = CliRunner()
    result = runner.invoke(main, ["bsort", "nonexistent.bib"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_bsort_basic_functionality():
    """Test bsort with a simple bibliography file."""
    runner = CliRunner()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
        bib_content = """@article{zebra2023,
  title={Zebra Study},
  author={Zebra, A.},
  year={2023}
}

@article{alpha2022,
  title={Alpha Research},
  author={Alpha, B.},
  year={2022}
}"""
        f.write(bib_content)
        f.flush()
        
        try:
            result = runner.invoke(main, ["bsort", f.name])
            assert result.exit_code == 0
            assert "Sorted 2 bibliography entries" in result.output
            
            # Check that file was sorted (alpha should come before zebra)
            sorted_content = Path(f.name).read_text()
            alpha_pos = sorted_content.find("@article{alpha2022")
            zebra_pos = sorted_content.find("@article{zebra2023")
            assert alpha_pos < zebra_pos
            
        finally:
            Path(f.name).unlink()


def test_wrong_file_extension():
    """Test commands with wrong file extensions."""
    runner = CliRunner()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("test content")
        f.flush()
        
        try:
            # Test xelatex with wrong extension
            result = runner.invoke(main, ["xelatex", f.name])
            assert result.exit_code != 0
            assert ".tex extension" in result.output
            
            # Test texcount with wrong extension  
            result = runner.invoke(main, ["texcount", f.name])
            assert result.exit_code != 0
            assert ".tex extension" in result.output
            
        finally:
            Path(f.name).unlink()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("test content")
        f.flush()
        
        try:
            # Test bsort with wrong extension
            result = runner.invoke(main, ["bsort", f.name])
            assert result.exit_code != 0
            assert ".bib extension" in result.output
            
        finally:
            Path(f.name).unlink()