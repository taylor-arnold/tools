"""Tests for remote operations (push/pull commands)."""

from pathlib import Path
from unittest.mock import MagicMock

import yaml
from click.testing import CliRunner
from dss.cli import main


class TestPushCommand:
    """Tests for the push CLI command."""

    def test_push_success(
        self,
        working_directory: Path,
        cli_runner: CliRunner,
        manifest_file: Path,
        test_file: Path,
        mock_subprocess,
    ):
        """Test successful file push."""
        # Copy manifest to working directory
        with open(manifest_file) as f:
            manifest_data = yaml.safe_load(f)

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        result = cli_runner.invoke(main, ["push", "test_file.txt"])

        assert result.exit_code == 0
        assert "Pushing test_file.txt to test.example.com" in result.output
        assert "Successfully pushed: test_file.txt" in result.output

        # Check subprocess calls
        assert mock_subprocess.call_count == 2  # mkdir + rsync

        # Check mkdir call
        mkdir_call = mock_subprocess.call_args_list[0]
        assert "mkdir -p /data/test/test-uuid-1234" in " ".join(mkdir_call[0][0])

        # Check rsync call
        rsync_call = mock_subprocess.call_args_list[1]
        assert "rsync" in rsync_call[0][0]
        assert "test_file.txt" in rsync_call[0][0]
        assert (
            "testuser@test.example.com:/data/test/test-uuid-1234/test_file.txt"
            in rsync_call[0][0]
        )

    def test_push_all_files(
        self,
        working_directory: Path,
        cli_runner: CliRunner,
        manifest_file: Path,
        mock_subprocess,
    ):
        """Test pushing all files."""
        # Create test files and manifest
        test_file1 = Path("test_file.txt")
        test_file2 = Path("another_file.txt")
        test_file1.write_text("content1")
        test_file2.write_text("content2")

        manifest_data = {
            "version": "1.0",
            "manifest_uuid": "test-uuid-1234",
            "datasets": {
                "test_file.txt": {"sha256": "abc123", "size_bytes": 8},
                "another_file.txt": {"sha256": "def456", "size_bytes": 8},
            },
            "remote@1": {
                "uname": "testuser",
                "url": "test.example.com",
                "base_path": "/data/test",
                "port": 22,
            },
        }

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        result = cli_runner.invoke(main, ["push"])

        assert result.exit_code == 0
        assert "Successfully pushed: test_file.txt" in result.output
        assert "Successfully pushed: another_file.txt" in result.output

    def test_push_missing_manifest(
        self, working_directory: Path, cli_runner: CliRunner
    ):
        """Test push fails without manifest."""
        result = cli_runner.invoke(main, ["push"])

        assert result.exit_code == 1
        assert "No manifest.yml found" in result.output

    def test_push_missing_remote_config(
        self, working_directory: Path, cli_runner: CliRunner
    ):
        """Test push fails without remote configuration."""
        manifest_data = {
            "version": "1.0",
            "manifest_uuid": "test-uuid-1234",
            "datasets": {"test_file.txt": {"sha256": "abc123"}},
        }

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        result = cli_runner.invoke(main, ["push"])

        assert result.exit_code == 1
        assert "No remote@1 configuration found" in result.output

    def test_push_missing_manifest_uuid(
        self, working_directory: Path, cli_runner: CliRunner, test_file: Path
    ):
        """Test push fails without manifest UUID."""
        manifest_data = {
            "version": "1.0",
            "datasets": {"test_file.txt": {"sha256": "abc123"}},
            "remote@1": {
                "uname": "testuser",
                "url": "test.example.com",
                "base_path": "/data/test",
            },
        }

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        result = cli_runner.invoke(main, ["push"])

        assert result.exit_code == 1
        assert "No manifest UUID found" in result.output

    def test_push_nonexistent_file(
        self,
        working_directory: Path,
        cli_runner: CliRunner,
        manifest_file: Path,
        mock_subprocess,
    ):
        """Test push skips nonexistent local files."""
        with open(manifest_file) as f:
            manifest_data = yaml.safe_load(f)

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        result = cli_runner.invoke(main, ["push", "test_file.txt"])

        assert result.exit_code == 0
        assert "Local file not found: test_file.txt" in result.output

    def test_push_mkdir_failure(
        self,
        working_directory: Path,
        cli_runner: CliRunner,
        manifest_file: Path,
        test_file: Path,
        mock_subprocess,
    ):
        """Test push handles mkdir failure."""
        # Setup mock to fail on mkdir
        mock_subprocess.side_effect = [
            MagicMock(returncode=1, stderr="Permission denied"),  # mkdir fails
            MagicMock(returncode=0),  # rsync would succeed but won't be called
        ]

        with open(manifest_file) as f:
            manifest_data = yaml.safe_load(f)

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        result = cli_runner.invoke(main, ["push", "test_file.txt"])

        assert result.exit_code == 0
        assert "Failed to create remote directory" in result.output

    def test_push_rsync_failure(
        self,
        working_directory: Path,
        cli_runner: CliRunner,
        manifest_file: Path,
        test_file: Path,
        mock_subprocess,
    ):
        """Test push handles rsync failure."""
        # Setup mock to succeed on mkdir but fail on rsync
        mock_subprocess.side_effect = [
            MagicMock(returncode=0),  # mkdir succeeds
            MagicMock(returncode=1, stderr="Connection failed"),  # rsync fails
        ]

        with open(manifest_file) as f:
            manifest_data = yaml.safe_load(f)

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        result = cli_runner.invoke(main, ["push", "test_file.txt"])

        assert result.exit_code == 0
        assert "Failed to push test_file.txt" in result.output


class TestPullCommand:
    """Tests for the pull CLI command."""

    def test_pull_success(
        self,
        working_directory: Path,
        cli_runner: CliRunner,
        manifest_file: Path,
        mock_subprocess,
    ):
        """Test successful file pull."""
        with open(manifest_file) as f:
            manifest_data = yaml.safe_load(f)

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        # Mock successful pull - file exists and download succeeds
        mock_subprocess.side_effect = [
            MagicMock(returncode=0),  # ls check succeeds
            MagicMock(returncode=0),  # rsync succeeds
        ]

        result = cli_runner.invoke(main, ["pull", "test_file.txt"])

        assert result.exit_code == 0
        assert "Pulling test_file.txt from test.example.com" in result.output

    def test_pull_missing_remote_file(
        self,
        working_directory: Path,
        cli_runner: CliRunner,
        manifest_file: Path,
        mock_subprocess,
    ):
        """Test pull handles missing remote file."""
        with open(manifest_file) as f:
            manifest_data = yaml.safe_load(f)

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        # Mock file not found on remote
        mock_subprocess.return_value.returncode = 1

        result = cli_runner.invoke(main, ["pull", "test_file.txt"])

        assert result.exit_code == 0
        assert "Remote file not found" in result.output

    def test_pull_all_files(
        self, working_directory: Path, cli_runner: CliRunner, mock_subprocess
    ):
        """Test pulling all files from manifest."""
        manifest_data = {
            "version": "1.0",
            "manifest_uuid": "test-uuid-1234",
            "datasets": {
                "file1.txt": {"sha256": "abc123", "size_bytes": 8},
                "file2.txt": {"sha256": "def456", "size_bytes": 8},
            },
            "remote@1": {
                "uname": "testuser",
                "url": "test.example.com",
                "base_path": "/data/test",
            },
        }

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        # Mock all operations succeed
        mock_subprocess.return_value.returncode = 0

        result = cli_runner.invoke(main, ["pull"])

        assert result.exit_code == 0
        # Should attempt to pull both files
        assert mock_subprocess.call_count >= 2

    def test_pull_custom_remote(
        self, working_directory: Path, cli_runner: CliRunner, mock_subprocess
    ):
        """Test pull with custom remote server."""
        manifest_data = {
            "version": "1.0",
            "manifest_uuid": "test-uuid-1234",
            "datasets": {"test_file.txt": {"sha256": "abc123"}},
            "remote@2": {
                "uname": "user2",
                "url": "remote2.example.com",
                "base_path": "/data/remote2",
            },
        }

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        mock_subprocess.return_value.returncode = 0

        result = cli_runner.invoke(main, ["pull", "--remote", "2", "test_file.txt"])

        assert result.exit_code == 0
        # Check that it used remote@2 configuration
        rsync_call = mock_subprocess.call_args_list[-1]  # Last call should be rsync
        assert "user2@remote2.example.com" in " ".join(rsync_call[0][0])

    def test_pull_missing_manifest_uuid(
        self, working_directory: Path, cli_runner: CliRunner
    ):
        """Test pull fails without manifest UUID."""
        manifest_data = {
            "version": "1.0",
            "datasets": {"test_file.txt": {"sha256": "abc123"}},
            "remote@1": {
                "uname": "testuser",
                "url": "test.example.com",
                "base_path": "/data/test",
            },
        }

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        result = cli_runner.invoke(main, ["pull"])

        assert result.exit_code == 1
        assert "No manifest UUID found" in result.output
