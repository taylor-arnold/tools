"""Tests for the add command."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from dss.cli import main


class TestAddCommand:
    """Tests for the add CLI command."""

    def test_add_new_file(self, working_directory: Path, cli_runner: CliRunner, test_file: Path, mock_uuid):
        """Test adding a new file to manifest."""
        # Create manifest first
        cli_runner.invoke(main, ['init'])
        
        result = cli_runner.invoke(main, ['add', 'test_file.txt'])
        
        assert result.exit_code == 0
        assert "Added test_file.txt to manifest" in result.output
        
        # Check manifest was updated
        with open("manifest.yml") as f:
            data = yaml.safe_load(f)
        
        assert "test_file.txt" in data["datasets"]
        dataset = data["datasets"]["test_file.txt"]
        assert "sha256" in dataset
        assert dataset["size_bytes"] == 13  # "Hello, World!" length
        assert dataset["size_human"] == "13B"
        assert dataset["description"] == ""

    def test_add_multiple_files(self, working_directory: Path, cli_runner: CliRunner, mock_uuid):
        """Test adding multiple files to manifest."""
        # Create manifest and test files
        cli_runner.invoke(main, ['init'])
        
        file1 = Path("file1.txt")
        file2 = Path("file2.txt")
        file1.write_text("content1")
        file2.write_text("content2")
        
        result = cli_runner.invoke(main, ['add', 'file1.txt', 'file2.txt'])
        
        assert result.exit_code == 0
        assert "Added file1.txt to manifest" in result.output
        assert "Added file2.txt to manifest" in result.output
        assert "Summary: 2 added, 0 updated, 0 unchanged" in result.output
        
        # Check both files in manifest
        with open("manifest.yml") as f:
            data = yaml.safe_load(f)
        
        assert "file1.txt" in data["datasets"]
        assert "file2.txt" in data["datasets"]

    def test_add_unchanged_file(self, working_directory: Path, cli_runner: CliRunner, test_file: Path, mock_uuid):
        """Test adding a file that hasn't changed."""
        # Create manifest and add file first time
        cli_runner.invoke(main, ['init'])
        cli_runner.invoke(main, ['add', 'test_file.txt'])
        
        # Add same file again
        result = cli_runner.invoke(main, ['add', 'test_file.txt'])
        
        assert result.exit_code == 0
        assert "File test_file.txt is unchanged (SHA256 matches)" in result.output

    def test_add_changed_file(self, working_directory: Path, cli_runner: CliRunner, mock_uuid):
        """Test adding a file that has changed."""
        # Create manifest and add file
        cli_runner.invoke(main, ['init'])
        
        test_file = Path("test_file.txt")
        test_file.write_text("original content")
        cli_runner.invoke(main, ['add', 'test_file.txt'])
        
        # Modify file and add again
        test_file.write_text("modified content")
        result = cli_runner.invoke(main, ['add', 'test_file.txt'])
        
        assert result.exit_code == 0
        assert "File test_file.txt has changed, updating information" in result.output
        
        # Check manifest was updated
        with open("manifest.yml") as f:
            data = yaml.safe_load(f)
        
        dataset = data["datasets"]["test_file.txt"]
        assert dataset["size_bytes"] == 16  # "modified content" length

    def test_add_fails_without_manifest(self, working_directory: Path, cli_runner: CliRunner, test_file: Path):
        """Test that add fails if no manifest exists."""
        result = cli_runner.invoke(main, ['add', 'test_file.txt'])
        
        assert result.exit_code == 1
        assert "No manifest.yml found in current directory" in result.output

    def test_add_nonexistent_file(self, working_directory: Path, cli_runner: CliRunner, mock_uuid):
        """Test adding a nonexistent file."""
        cli_runner.invoke(main, ['init'])
        
        result = cli_runner.invoke(main, ['add', 'nonexistent.txt'])
        
        assert result.exit_code == 1
        assert "File not found, skipping: nonexistent.txt" in result.output
        assert "No valid files found to add" in result.output

    def test_add_directory(self, working_directory: Path, cli_runner: CliRunner, mock_uuid):
        """Test that directories are skipped."""
        cli_runner.invoke(main, ['init'])
        
        # Create a directory
        test_dir = Path("test_directory")
        test_dir.mkdir()
        
        result = cli_runner.invoke(main, ['add', 'test_directory'])
        
        assert result.exit_code == 1
        assert "No valid files found to add" in result.output

    def test_add_hidden_file(self, working_directory: Path, cli_runner: CliRunner, mock_uuid):
        """Test that hidden files are skipped."""
        cli_runner.invoke(main, ['init'])
        
        # Create a hidden file
        hidden_file = Path(".hidden_file")
        hidden_file.write_text("hidden content")
        
        result = cli_runner.invoke(main, ['add', '.hidden_file'])
        
        assert result.exit_code == 1
        assert "No valid files found to add" in result.output

    def test_add_manifest_file_itself(self, working_directory: Path, cli_runner: CliRunner, mock_uuid):
        """Test that manifest.yml file is skipped."""
        cli_runner.invoke(main, ['init'])
        
        result = cli_runner.invoke(main, ['add', 'manifest.yml'])
        
        assert result.exit_code == 1
        assert "No valid files found to add" in result.output

    def test_add_file_outside_manifest_directory(self, working_directory: Path, cli_runner: CliRunner, temp_dir: Path, mock_uuid):
        """Test that files outside manifest directory are skipped."""
        cli_runner.invoke(main, ['init'])
        
        # Create file outside working directory
        outside_file = temp_dir / "outside_file.txt"
        outside_file.write_text("outside content")
        
        result = cli_runner.invoke(main, ['add', str(outside_file)])
        
        assert result.exit_code == 1
        assert f"File must be in same directory as manifest.yml, skipping: {outside_file}" in result.output

    def test_add_creates_manifest_uuid_for_old_manifest(self, working_directory: Path, cli_runner: CliRunner, test_file: Path, mock_uuid):
        """Test that add creates manifest UUID for backward compatibility."""
        # Create old-style manifest without UUID
        manifest_data = {
            "version": "1.0",
            "datasets": {}
        }
        
        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)
        
        result = cli_runner.invoke(main, ['add', 'test_file.txt'])
        
        assert result.exit_code == 0
        assert "Generated new manifest UUID: test-uuid-1234" in result.output
        
        # Check UUID was added to manifest
        with open("manifest.yml") as f:
            data = yaml.safe_load(f)
        
        assert data["manifest_uuid"] == "test-uuid-1234"