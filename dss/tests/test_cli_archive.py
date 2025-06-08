"""Tests for archive operations (expand/compress commands)."""

import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from dss.cli import main


class TestExpandCommand:
    """Tests for the expand CLI command."""

    def test_expand_tar_file(self, working_directory: Path, cli_runner: CliRunner):
        """Test expanding a tar file."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create a test directory and tar file
        test_dir = Path("test_directory")
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")
        
        # Create tar file
        with tarfile.open("test_directory.tar", "w") as tar:
            tar.add(test_dir, arcname="test_directory")
        
        # Remove original directory
        import shutil
        shutil.rmtree(test_dir)
        
        result = cli_runner.invoke(main, ['expand'])
        
        assert result.exit_code == 0
        assert "Expanding test_directory.tar to test_directory" in result.output
        assert "Successfully expanded test_directory.tar" in result.output
        assert "Expand summary: 1 expanded, 0 skipped" in result.output
        
        # Check directory was recreated
        assert test_dir.exists()
        assert (test_dir / "file1.txt").exists()
        assert (test_dir / "file2.txt").exists()

    def test_expand_tar_bz2_file(self, working_directory: Path, cli_runner: CliRunner):
        """Test expanding a tar.bz2 file."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create a test directory and tar.bz2 file
        test_dir = Path("test_directory")
        test_dir.mkdir()
        (test_dir / "compressed_file.txt").write_text("compressed content")
        
        # Create tar.bz2 file
        with tarfile.open("test_directory.tar.bz2", "w:bz2") as tar:
            tar.add(test_dir, arcname="test_directory")
        
        # Remove original directory
        import shutil
        shutil.rmtree(test_dir)
        
        result = cli_runner.invoke(main, ['expand'])
        
        assert result.exit_code == 0
        assert "Expanding test_directory.tar.bz2 to test_directory" in result.output
        assert "Successfully expanded test_directory.tar.bz2" in result.output
        
        # Check directory was recreated
        assert test_dir.exists()
        assert (test_dir / "compressed_file.txt").exists()

    def test_expand_skips_existing_directory(self, working_directory: Path, cli_runner: CliRunner):
        """Test that expand skips when target directory exists."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create directory and tar file
        test_dir = Path("test_directory")
        test_dir.mkdir()
        (test_dir / "existing_file.txt").write_text("existing")
        
        with tarfile.open("test_directory.tar", "w") as tar:
            tar.add(test_dir, arcname="test_directory")
        
        result = cli_runner.invoke(main, ['expand'])
        
        assert result.exit_code == 0
        assert "Directory test_directory already exists, skipping test_directory.tar" in result.output
        assert "Expand summary: 0 expanded, 1 skipped" in result.output

    def test_expand_no_tar_files(self, working_directory: Path, cli_runner: CliRunner):
        """Test expand when no tar files exist."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        result = cli_runner.invoke(main, ['expand'])
        
        assert result.exit_code == 0
        assert "No tar or tar.bz2 files found in current directory" in result.output

    def test_expand_without_manifest(self, working_directory: Path, cli_runner: CliRunner):
        """Test expand fails without manifest."""
        result = cli_runner.invoke(main, ['expand'])
        
        assert result.exit_code == 1
        assert "No manifest.yml found in current directory" in result.output

    def test_expand_corrupted_tar(self, working_directory: Path, cli_runner: CliRunner):
        """Test expand handles corrupted tar files gracefully."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create a corrupted tar file
        corrupted_tar = Path("corrupted.tar")
        corrupted_tar.write_text("This is not a valid tar file")
        
        result = cli_runner.invoke(main, ['expand'])
        
        assert result.exit_code == 0
        assert "Failed to expand corrupted.tar" in result.output


class TestCompressCommand:
    """Tests for the compress CLI command."""

    def test_compress_directory(self, working_directory: Path, cli_runner: CliRunner):
        """Test compressing a directory."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create test directory with files
        test_dir = Path("test_directory")
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")
        
        result = cli_runner.invoke(main, ['compress'])
        
        assert result.exit_code == 0
        assert "Compressing test_directory to test_directory.tar.bz2" in result.output
        assert "Successfully compressed test_directory" in result.output
        assert "Compress summary: 1 compressed, 0 skipped" in result.output
        
        # Check tar.bz2 file was created
        tar_file = Path("test_directory.tar.bz2")
        assert tar_file.exists()
        
        # Verify tar file contents
        with tarfile.open(tar_file, "r:bz2") as tar:
            names = tar.getnames()
            assert "test_directory/file1.txt" in names
            assert "test_directory/file2.txt" in names

    def test_compress_multiple_directories(self, working_directory: Path, cli_runner: CliRunner):
        """Test compressing multiple directories."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create multiple test directories
        for i in range(3):
            test_dir = Path(f"test_dir_{i}")
            test_dir.mkdir()
            (test_dir / f"file_{i}.txt").write_text(f"content_{i}")
        
        result = cli_runner.invoke(main, ['compress'])
        
        assert result.exit_code == 0
        assert "Compress summary: 3 compressed, 0 skipped" in result.output
        
        # Check all tar.bz2 files were created
        for i in range(3):
            tar_file = Path(f"test_dir_{i}.tar.bz2")
            assert tar_file.exists()

    def test_compress_skips_existing_archive(self, working_directory: Path, cli_runner: CliRunner):
        """Test that compress skips when archive already exists."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create directory and existing archive
        test_dir = Path("test_directory")
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        
        existing_archive = Path("test_directory.tar.bz2")
        existing_archive.write_text("existing archive")
        
        result = cli_runner.invoke(main, ['compress'])
        
        assert result.exit_code == 0
        assert "Archive test_directory.tar.bz2 already exists, skipping test_directory" in result.output
        assert "Compress summary: 0 compressed, 1 skipped" in result.output

    def test_compress_no_directories(self, working_directory: Path, cli_runner: CliRunner):
        """Test compress when no directories exist."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create some files but no directories
        Path("file1.txt").write_text("content1")
        Path("file2.txt").write_text("content2")
        
        result = cli_runner.invoke(main, ['compress'])
        
        assert result.exit_code == 0
        assert "No directories found in current directory" in result.output

    def test_compress_skips_hidden_directories(self, working_directory: Path, cli_runner: CliRunner):
        """Test that compress skips hidden directories."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create hidden directory
        hidden_dir = Path(".hidden_directory")
        hidden_dir.mkdir()
        (hidden_dir / "file.txt").write_text("hidden content")
        
        # Create regular directory
        normal_dir = Path("normal_directory")
        normal_dir.mkdir()
        (normal_dir / "file.txt").write_text("normal content")
        
        result = cli_runner.invoke(main, ['compress'])
        
        assert result.exit_code == 0
        assert "Compress summary: 1 compressed, 0 skipped" in result.output
        
        # Only normal directory should be compressed
        assert Path("normal_directory.tar.bz2").exists()
        assert not Path(".hidden_directory.tar.bz2").exists()

    def test_compress_skips_pycache(self, working_directory: Path, cli_runner: CliRunner):
        """Test that compress skips __pycache__ directories."""
        # Create manifest
        cli_runner.invoke(main, ['init'])
        
        # Create __pycache__ directory
        pycache_dir = Path("__pycache__")
        pycache_dir.mkdir()
        (pycache_dir / "module.pyc").write_text("bytecode")
        
        result = cli_runner.invoke(main, ['compress'])
        
        assert result.exit_code == 0
        assert "No directories found in current directory" in result.output

    def test_compress_without_manifest(self, working_directory: Path, cli_runner: CliRunner):
        """Test compress fails without manifest."""
        result = cli_runner.invoke(main, ['compress'])
        
        assert result.exit_code == 1
        assert "No manifest.yml found in current directory" in result.output