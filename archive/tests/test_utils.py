"""Tests for utility functions in dss.cli."""

import hashlib
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from colorama import Fore, Style
from dss.cli import ColoredFormatter, calculate_sha256, format_size, setup_logging


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""

    def test_format_error_message(self):
        """Test formatting of error messages."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test error",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        assert result == f"{Fore.RED}Test error{Style.RESET_ALL}"

    def test_format_warning_message(self):
        """Test formatting of warning messages."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Test warning",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        assert result == f"{Fore.YELLOW}Test warning{Style.RESET_ALL}"

    def test_format_info_message(self):
        """Test formatting of info messages."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test info",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        assert result == f"{Fore.GREEN}Test info{Style.RESET_ALL}"


class TestCalculateSha256:
    """Tests for calculate_sha256 function."""

    def test_calculate_sha256_empty_file(self, empty_test_file: Path):
        """Test SHA256 calculation of empty file."""
        result = calculate_sha256(empty_test_file)
        # SHA256 of empty file
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert result == expected

    def test_calculate_sha256_with_content(self, test_file: Path):
        """Test SHA256 calculation of file with content."""
        result = calculate_sha256(test_file)

        # Calculate expected hash
        expected_hash = hashlib.sha256(b"Hello, World!").hexdigest()
        assert result == expected_hash

    def test_calculate_sha256_nonexistent_file(self, temp_dir: Path):
        """Test SHA256 calculation of nonexistent file raises error."""
        nonexistent_file = temp_dir / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            calculate_sha256(nonexistent_file)


class TestFormatSize:
    """Tests for format_size function."""

    def test_format_bytes(self):
        """Test formatting of byte sizes."""
        assert format_size(0) == "0.0B"
        assert format_size(512) == "512.0B"
        assert format_size(1023) == "1023.0B"

    def test_format_kilobytes(self):
        """Test formatting of kilobyte sizes."""
        assert format_size(1024) == "1.0K"
        assert format_size(1536) == "1.5K"
        assert format_size(1024 * 1023) == "1023.0K"

    def test_format_megabytes(self):
        """Test formatting of megabyte sizes."""
        assert format_size(1024 * 1024) == "1.0M"
        assert format_size(int(1.5 * 1024 * 1024)) == "1.5M"

    def test_format_gigabytes(self):
        """Test formatting of gigabyte sizes."""
        assert format_size(1024 * 1024 * 1024) == "1.0G"
        assert format_size(int(2.5 * 1024 * 1024 * 1024)) == "2.5G"

    def test_format_terabytes(self):
        """Test formatting of terabyte sizes."""
        assert format_size(1024 * 1024 * 1024 * 1024) == "1.0T"

    def test_format_petabytes(self):
        """Test formatting of petabyte sizes."""
        assert format_size(1024 * 1024 * 1024 * 1024 * 1024) == "1.0P"


class TestSetupLogging:
    """Tests for setup_logging function."""

    @patch("dss.cli.logging.basicConfig")
    def test_setup_logging_default(self, mock_basic_config):
        """Test default logging setup."""
        setup_logging()

        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args
        assert call_args[1]["level"] == logging.INFO
        assert call_args[1]["format"] == "%(message)s"

    @patch("dss.cli.logging.basicConfig")
    def test_setup_logging_verbose(self, mock_basic_config):
        """Test verbose logging setup."""
        setup_logging(verbose=True)

        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args
        assert call_args[1]["level"] == logging.DEBUG
