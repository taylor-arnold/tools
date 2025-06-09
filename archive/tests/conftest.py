"""Pytest configuration and fixtures for dss tests."""

import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner


@pytest.fixture
def temp_dir() -> Generator[Path]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI runner for testing commands."""
    return CliRunner()


@pytest.fixture
def sample_manifest_data() -> dict[str, Any]:
    """Sample manifest data for testing."""
    return {
        "version": "1.0",
        "manifest_uuid": "test-uuid-1234",
        "datasets": {
            "test_file.txt": {
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "size_bytes": 0,
                "size_human": "0B",
                "uploaded": "2023-01-01T00:00:00Z",
                "description": "Test file",
            }
        },
        "remote@1": {
            "uname": "testuser",
            "url": "test.example.com",
            "base_path": "/data/test",
            "port": 22,
        },
    }


@pytest.fixture
def manifest_file(temp_dir: Path, sample_manifest_data: dict[str, Any]) -> Path:
    """Create a test manifest file."""
    manifest_path = temp_dir / "manifest.yml"
    with open(manifest_path, "w") as f:
        yaml.dump(sample_manifest_data, f)
    return manifest_path


@pytest.fixture
def test_file(temp_dir: Path) -> Path:
    """Create a test file with known content."""
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("Hello, World!")
    return file_path


@pytest.fixture
def empty_test_file(temp_dir: Path) -> Path:
    """Create an empty test file."""
    file_path = temp_dir / "test_file.txt"
    file_path.touch()
    return file_path


@pytest.fixture
def mock_subprocess():
    """Mock subprocess calls for remote operations."""
    with patch("dss.cli.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        yield mock_run


@pytest.fixture
def mock_uuid():
    """Mock UUID generation for predictable testing."""
    with patch("dss.cli.uuid.uuid4") as mock_uuid4:
        mock_uuid4.return_value.hex = "test-uuid-1234"
        mock_uuid4.return_value.__str__ = lambda x: "test-uuid-1234"
        yield mock_uuid4


@pytest.fixture
def working_directory(temp_dir: Path) -> Generator[Path]:
    """Change to temporary directory for test duration."""
    original_cwd = Path.cwd()
    try:
        import os

        os.chdir(temp_dir)
        yield temp_dir
    finally:
        os.chdir(original_cwd)
