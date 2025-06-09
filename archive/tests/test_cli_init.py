"""Tests for the init command."""

from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner
from dss.cli import main


class TestInitCommand:
    """Tests for the init CLI command."""

    def test_init_creates_manifest(
        self, working_directory: Path, cli_runner: CliRunner, mock_uuid
    ):
        """Test that init creates a manifest file."""
        result = cli_runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert (
            "Initialized empty manifest: manifest.yml (UUID: test-uuid-1234)"
            in result.output
        )

        # Check manifest file was created
        manifest_path = working_directory / "manifest.yml"
        assert manifest_path.exists()

        # Check manifest content
        with open(manifest_path) as f:
            data = yaml.safe_load(f)

        assert data["version"] == "1.0"
        assert data["manifest_uuid"] == "test-uuid-1234"
        assert data["datasets"] == {}

    def test_init_creates_gitignore(
        self, working_directory: Path, cli_runner: CliRunner, mock_uuid
    ):
        """Test that init creates a .gitignore file."""
        result = cli_runner.invoke(main, ["init"])

        assert result.exit_code == 0

        # Check .gitignore was created
        gitignore_path = working_directory / ".gitignore"
        assert gitignore_path.exists()

        # Check .gitignore content
        content = gitignore_path.read_text()
        assert "manifest.yml" in content

    def test_init_does_not_overwrite_gitignore(
        self, working_directory: Path, cli_runner: CliRunner, mock_uuid
    ):
        """Test that init doesn't overwrite existing .gitignore."""
        # Create existing .gitignore
        gitignore_path = working_directory / ".gitignore"
        gitignore_path.write_text("existing_content\\n")

        result = cli_runner.invoke(main, ["init"])

        assert result.exit_code == 0

        # Check .gitignore was not overwritten
        content = gitignore_path.read_text()
        assert content == "existing_content\\n"

    def test_init_fails_if_manifest_exists(
        self, working_directory: Path, cli_runner: CliRunner
    ):
        """Test that init fails if manifest already exists."""
        # Create existing manifest
        manifest_path = working_directory / "manifest.yml"
        manifest_path.write_text("existing manifest")

        result = cli_runner.invoke(main, ["init"])

        assert result.exit_code == 1
        assert "Manifest file already exists" in result.output

    @patch("dss.cli.Path.home")
    def test_init_loads_remote_config(
        self,
        mock_home,
        working_directory: Path,
        cli_runner: CliRunner,
        mock_uuid,
        temp_dir: Path,
    ):
        """Test that init loads remote configuration if available."""
        # Setup mock home directory
        config_dir = temp_dir / ".config" / "dss"
        config_dir.mkdir(parents=True)
        remote_config_path = config_dir / "remote"

        remote_config = {
            "remote@1": {
                "uname": "testuser",
                "url": "test.example.com",
                "base_path": "/data/test",
                "port": 22,
            }
        }

        with open(remote_config_path, "w") as f:
            yaml.dump(remote_config, f)

        mock_home.return_value = temp_dir

        result = cli_runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert "Loaded 1 remote configurations from config" in result.output

        # Check manifest includes remote config
        manifest_path = working_directory / "manifest.yml"
        with open(manifest_path) as f:
            data = yaml.safe_load(f)

        assert "remote@1" in data
        assert data["remote@1"]["uname"] == "testuser"

    @patch("dss.cli.Path.home")
    def test_init_handles_missing_remote_config(
        self,
        mock_home,
        working_directory: Path,
        cli_runner: CliRunner,
        mock_uuid,
        temp_dir: Path,
    ):
        """Test that init handles missing remote config gracefully."""
        mock_home.return_value = temp_dir

        result = cli_runner.invoke(main, ["init"])

        assert result.exit_code == 0
        # Should not contain remote config loading message
        assert "Loaded" not in result.output

    @patch("dss.cli.Path.home")
    def test_init_handles_invalid_remote_config(
        self,
        mock_home,
        working_directory: Path,
        cli_runner: CliRunner,
        mock_uuid,
        temp_dir: Path,
    ):
        """Test that init handles invalid remote config gracefully."""
        # Setup mock home directory with invalid config
        config_dir = temp_dir / ".config" / "dss"
        config_dir.mkdir(parents=True)
        remote_config_path = config_dir / "remote"

        # Write invalid YAML
        remote_config_path.write_text("invalid: yaml: content: [")

        mock_home.return_value = temp_dir

        result = cli_runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert "Failed to load remote config" in result.output
