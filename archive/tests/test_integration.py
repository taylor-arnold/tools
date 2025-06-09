"""Integration tests for dss CLI workflow."""

import hashlib
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner
from dss.cli import main


class TestFullWorkflow:
    """Integration tests for complete dss workflows."""

    def test_complete_local_workflow(
        self, working_directory: Path, cli_runner: CliRunner, mock_uuid
    ):
        """Test complete local workflow: init -> add -> modify -> add."""
        # Initialize manifest
        result = cli_runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert "test-uuid-1234" in result.output

        # Create and add first file
        file1 = Path("data1.txt")
        file1.write_text("Initial content for file 1")

        result = cli_runner.invoke(main, ["add", "data1.txt"])
        assert result.exit_code == 0
        assert "Added data1.txt to manifest" in result.output

        # Create and add second file
        file2 = Path("data2.txt")
        file2.write_text("Content for file 2")

        result = cli_runner.invoke(main, ["add", "data2.txt"])
        assert result.exit_code == 0
        assert "Added data2.txt to manifest" in result.output

        # Add both files at once (should show unchanged)
        result = cli_runner.invoke(main, ["add", "data1.txt", "data2.txt"])
        assert result.exit_code == 0
        assert "Summary: 0 added, 0 updated, 2 unchanged" in result.output

        # Modify first file and re-add
        file1.write_text("Modified content for file 1")
        result = cli_runner.invoke(main, ["add", "data1.txt"])
        assert result.exit_code == 0
        assert "File data1.txt has changed, updating information" in result.output

        # Verify final manifest state
        with open("manifest.yml") as f:
            manifest_data = yaml.safe_load(f)

        assert manifest_data["manifest_uuid"] == "test-uuid-1234"
        assert len(manifest_data["datasets"]) == 2
        assert "data1.txt" in manifest_data["datasets"]
        assert "data2.txt" in manifest_data["datasets"]

        # Verify SHA256 hashes are correct
        file1_hash = hashlib.sha256(b"Modified content for file 1").hexdigest()
        file2_hash = hashlib.sha256(b"Content for file 2").hexdigest()

        assert manifest_data["datasets"]["data1.txt"]["sha256"] == file1_hash
        assert manifest_data["datasets"]["data2.txt"]["sha256"] == file2_hash

    @patch("dss.cli.subprocess.run")
    def test_complete_remote_workflow(
        self, mock_subprocess, working_directory: Path, cli_runner: CliRunner, mock_uuid
    ):
        """Test complete remote workflow: init -> add -> push -> pull."""
        # Mock all subprocess calls to succeed
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = ""

        # Initialize manifest with remote config
        result = cli_runner.invoke(main, ["init"])
        assert result.exit_code == 0

        # Add remote configuration to manifest
        with open("manifest.yml") as f:
            manifest_data = yaml.safe_load(f)

        manifest_data["remote@1"] = {
            "uname": "testuser",
            "url": "test.example.com",
            "base_path": "/data/test",
            "port": 22,
        }

        with open("manifest.yml", "w") as f:
            yaml.dump(manifest_data, f)

        # Create and add files
        file1 = Path("dataset1.txt")
        file2 = Path("dataset2.txt")
        file1.write_text("Dataset 1 content")
        file2.write_text("Dataset 2 content")

        result = cli_runner.invoke(main, ["add", "dataset1.txt", "dataset2.txt"])
        assert result.exit_code == 0
        assert "Summary: 2 added, 0 updated, 0 unchanged" in result.output

        # Push files to remote
        result = cli_runner.invoke(main, ["push"])
        assert result.exit_code == 0
        assert "Successfully pushed: dataset1.txt" in result.output
        assert "Successfully pushed: dataset2.txt" in result.output

        # Verify push created correct remote paths
        with open("manifest.yml") as f:
            manifest_data = yaml.safe_load(f)

        assert (
            manifest_data["datasets"]["dataset1.txt"]["remote@1"]
            == "test-uuid-1234/dataset1.txt"
        )
        assert (
            manifest_data["datasets"]["dataset2.txt"]["remote@1"]
            == "test-uuid-1234/dataset2.txt"
        )

        # Remove local files and pull them back
        file1.unlink()
        file2.unlink()

        result = cli_runner.invoke(main, ["pull"])
        assert result.exit_code == 0

        # Verify subprocess calls included correct paths with manifest UUID
        ssh_calls = [
            call for call in mock_subprocess.call_args_list if "ssh" in str(call)
        ]
        rsync_calls = [
            call for call in mock_subprocess.call_args_list if "rsync" in str(call)
        ]

        # Should have SSH calls for file existence checks
        assert len(ssh_calls) >= 2

        # Should have rsync calls for both push and pull operations
        assert len(rsync_calls) >= 4  # 2 push + 2 pull

        # Verify all remote paths use manifest UUID
        for call in rsync_calls:
            call_str = " ".join(call[0][0])
            if "test.example.com" in call_str:
                assert "test-uuid-1234" in call_str

    def test_backward_compatibility_workflow(
        self, working_directory: Path, cli_runner: CliRunner, mock_uuid
    ):
        """Test backward compatibility with old manifests without UUID."""
        # Create old-style manifest manually
        old_manifest = {
            "version": "1.0",
            "datasets": {
                "legacy_file.txt": {
                    "uuid": "old-file-uuid-5678",  # Old per-file UUID
                    "sha256": "abc123def456",
                    "size_bytes": 100,
                    "size_human": "100B",
                    "uploaded": "2023-01-01T00:00:00Z",
                }
            },
        }

        with open("manifest.yml", "w") as f:
            yaml.dump(old_manifest, f)

        # Create the legacy file
        legacy_file = Path("legacy_file.txt")
        legacy_file.write_text("Legacy file content")

        # Add operation should generate manifest UUID and preserve file data
        result = cli_runner.invoke(main, ["add", "legacy_file.txt"])
        assert result.exit_code == 0
        assert "Generated new manifest UUID: test-uuid-1234" in result.output

        # Verify manifest was upgraded
        with open("manifest.yml") as f:
            updated_manifest = yaml.safe_load(f)

        assert updated_manifest["manifest_uuid"] == "test-uuid-1234"
        assert "legacy_file.txt" in updated_manifest["datasets"]
        # Old UUID should be preserved in the dataset entry
        assert "uuid" in updated_manifest["datasets"]["legacy_file.txt"]

    def test_error_handling_workflow(
        self, working_directory: Path, cli_runner: CliRunner
    ):
        """Test error handling in various scenarios."""
        # Test operations without manifest
        result = cli_runner.invoke(main, ["add", "nonexistent.txt"])
        assert result.exit_code == 1
        assert "No manifest.yml found" in result.output

        result = cli_runner.invoke(main, ["push"])
        assert result.exit_code == 1
        assert "No manifest.yml found" in result.output

        result = cli_runner.invoke(main, ["pull"])
        assert result.exit_code == 1
        assert "No manifest.yml found" in result.output

        # Initialize and test with invalid files
        cli_runner.invoke(main, ["init"])

        result = cli_runner.invoke(main, ["add", "nonexistent.txt"])
        assert result.exit_code == 1
        assert "No valid files found to add" in result.output

        # Test with directory instead of file
        test_dir = Path("test_directory")
        test_dir.mkdir()

        result = cli_runner.invoke(main, ["add", "test_directory"])
        assert result.exit_code == 1
        assert "No valid files found to add" in result.output

    def test_mixed_file_operations(
        self, working_directory: Path, cli_runner: CliRunner, mock_uuid
    ):
        """Test operations with mix of valid/invalid files."""
        # Initialize manifest
        cli_runner.invoke(main, ["init"])

        # Create valid files
        valid_file1 = Path("valid1.txt")
        valid_file2 = Path("valid2.txt")
        valid_file1.write_text("Valid content 1")
        valid_file2.write_text("Valid content 2")

        # Create directory (invalid)
        test_dir = Path("test_dir")
        test_dir.mkdir()

        # Create hidden file (invalid)
        hidden_file = Path(".hidden")
        hidden_file.write_text("Hidden content")

        # Add mix of valid and invalid files
        result = cli_runner.invoke(
            main,
            [
                "add",
                "valid1.txt",
                "test_dir",
                ".hidden",
                "nonexistent.txt",
                "valid2.txt",
            ],
        )

        assert result.exit_code == 0
        assert "Summary: 2 added, 0 updated, 0 unchanged" in result.output

        # Verify only valid files were added
        with open("manifest.yml") as f:
            manifest_data = yaml.safe_load(f)

        assert len(manifest_data["datasets"]) == 2
        assert "valid1.txt" in manifest_data["datasets"]
        assert "valid2.txt" in manifest_data["datasets"]
        assert "test_dir" not in manifest_data["datasets"]
        assert ".hidden" not in manifest_data["datasets"]
