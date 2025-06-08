"""Command line interface for dss - Dataset archive tools.

This module provides a CLI for managing data archives with manifest files.
It supports file tracking, remote synchronization, and archive operations.
"""

import glob
import hashlib
import logging
import os
import re
import subprocess
import sys
import tarfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import click
import colorama
import yaml
from colorama import Fore, Style

from . import __version__

# Initialize colorama for cross-platform colored output
colorama.init()


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log messages."""
    
    def format(self, record: logging.LogRecord) -> str:
        if record.levelno >= logging.ERROR:
            color = Fore.RED
        elif record.levelno >= logging.WARNING:
            color = Fore.YELLOW
        else:
            color = Fore.GREEN
        
        return f"{color}{record.getMessage()}{Style.RESET_ALL}"


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration.
    
    Args:
        verbose: If True, set logging level to DEBUG, otherwise INFO.
    """
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


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file.
    
    Args:
        file_path: Path to the file to hash.
        
    Returns:
        The SHA256 hash as a hexadecimal string.
    """
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def format_size(size_bytes: int) -> str:
    """Format file size in human readable format.
    
    Args:
        size_bytes: Size in bytes to format.
        
    Returns:
        Human-readable size string (e.g., '1.5M', '2.3G').
    """
    for unit in ['B', 'K', 'M', 'G', 'T']:
        if size_bytes < 1024.0:
            if unit == 'B':
                return f"{size_bytes}{unit}"
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}P"


@click.group()
@click.version_option(version=__version__)
@click.option(
    "-v", "--verbose", 
    is_flag=True, 
    help="Enable verbose logging"
)
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """dss - Dataset archive tools.
    
    A command-line tool for managing data archives with manifest files.
    Supports file tracking, remote synchronization, and archive operations.
    
    Args:
        ctx: Click context object.
        verbose: Enable verbose logging output.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a new manifest file.
    
    Creates a new manifest.yml file in the current directory with a unique UUID.
    Also creates a .gitignore file if one doesn't exist.
    
    Args:
        ctx: Click context object.
        
    Raises:
        SystemExit: If manifest already exists or creation fails.
    """
    manifest_path = Path("manifest.yml")
    
    if manifest_path.exists():
        logging.error(f"Manifest file already exists: {manifest_path}")
        sys.exit(1)
    
    # Create empty manifest structure with manifest-level UUID
    manifest_uuid = str(uuid.uuid4())
    manifest_data = {
        "version": "1.0",
        "manifest_uuid": manifest_uuid,
        "datasets": {}
    }
    
    # Try to load default remote configurations
    config_path = Path.home() / ".config" / "dss" / "remote"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                remote_configs = yaml.safe_load(f)
            
            if remote_configs and isinstance(remote_configs, dict):
                # Add remote configurations to manifest
                for remote_key, remote_config in remote_configs.items():
                    if remote_key.startswith("remote@"):
                        manifest_data[remote_key] = remote_config
                logging.info(f"Loaded {len([k for k in remote_configs.keys() if k.startswith('remote@')])} remote configurations from config")
            else:
                logging.debug("Config file is empty or invalid format")
        except Exception as e:
            logging.warning(f"Failed to load remote config from {config_path}: {e}")
    else:
        logging.debug(f"No remote config found at {config_path}")
    
    try:
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)
        
        logging.info(f"Initialized empty manifest: {manifest_path} (UUID: {manifest_uuid})")
        
        # Create .gitignore if it doesn't exist
        gitignore_path = Path(".gitignore")
        if not gitignore_path.exists():
            with open(gitignore_path, "w") as f:
                f.write("manifest.yml\n")
            logging.info(f"Created .gitignore with manifest.yml")
        else:
            logging.debug(".gitignore already exists, not modifying")
        
    except Exception as e:
        logging.error(f"Failed to create manifest file: {e}")
        sys.exit(1)


@main.command()
@click.argument("filenames", nargs=-1, required=True)
@click.pass_context
def add(ctx: click.Context, filenames: Tuple[str, ...]) -> None:
    """Add files to the manifest.
    
    Adds one or more files to the manifest, calculating their SHA256 hashes
    and file sizes. Files must be in the same directory as the manifest.
    
    Args:
        ctx: Click context object.
        filenames: Tuple of filenames to add to the manifest.
        
    Raises:
        SystemExit: If no manifest exists, no valid files found, or operation fails.
    """
    manifest_path = Path("manifest.yml")
    
    # Check if manifest exists
    if not manifest_path.exists():
        logging.error("No manifest.yml found in current directory. Run 'dss init' first.")
        sys.exit(1)
    
    # Get the manifest directory (current working directory)
    manifest_dir = manifest_path.parent.resolve()
    
    # Filter filenames to only include regular files (not directories or hidden files)
    valid_files = []
    for filename in filenames:
        file_path = Path(filename)
        
        # Skip if file doesn't exist
        if not file_path.exists():
            logging.warning(f"File not found, skipping: {filename}")
            continue
            
        # Skip directories
        if file_path.is_dir():
            logging.debug(f"Skipping directory: {filename}")
            continue
            
        # Skip hidden files (starting with .)
        if file_path.name.startswith('.'):
            logging.debug(f"Skipping hidden file: {filename}")
            continue
            
        # Skip if not a regular file
        if not file_path.is_file():
            logging.debug(f"Skipping non-regular file: {filename}")
            continue
        
        # Skip if this is the manifest file
        if file_path.name == "manifest.yml":
            logging.debug(f"Skipping manifest file: {filename}")
            continue

        # Check if file is in the same directory as manifest
        file_dir = file_path.resolve().parent
        if file_dir != manifest_dir:
            logging.warning(f"File must be in same directory as manifest.yml, skipping: {filename}")
            continue
        
        # Normalize filename to remove leading ./
        normalized_filename = str(file_path.name)
        valid_files.append(normalized_filename)
    
    if not valid_files:
        logging.error("No valid files found to add")
        sys.exit(1)
    
    # Counters for summary
    added_count = 0
    updated_count = 0
    unchanged_count = 0
    
    try:
        # Load existing manifest
        with open(manifest_path, "r") as f:
            manifest_data = yaml.safe_load(f)
        
        # Ensure datasets section exists
        if "datasets" not in manifest_data:
            manifest_data["datasets"] = {}
        
        # Ensure manifest has a UUID (for backward compatibility)
        if "manifest_uuid" not in manifest_data:
            manifest_data["manifest_uuid"] = str(uuid.uuid4())
            logging.info(f"Generated new manifest UUID: {manifest_data['manifest_uuid']}")
        
        # Process each valid file
        for normalized_filename in valid_files:
            # Use the original path for file operations, but normalized name for manifest
            file_path = Path(normalized_filename)
            
            # Calculate file information
            logging.info(f"Analyzing file: {normalized_filename}")
            file_size = file_path.stat().st_size
            file_sha256 = calculate_sha256(file_path)
            current_time = datetime.utcnow().isoformat() + "Z"
            
            # Check if file already exists in manifest
            if normalized_filename in manifest_data["datasets"]:
                existing_entry = manifest_data["datasets"][normalized_filename]
                existing_sha256 = existing_entry.get("sha256", "")
                
                if file_sha256 == existing_sha256:
                    # File hasn't changed
                    logging.info(f"File {normalized_filename} is unchanged (SHA256 matches)")
                    unchanged_count += 1
                else:
                    # File has changed, update information but preserve UUID
                    logging.info(f"File {normalized_filename} has changed, updating information")
                    manifest_data["datasets"][normalized_filename].update({
                        "sha256": file_sha256,
                        "size_bytes": file_size,
                        "size_human": format_size(file_size),
                        "uploaded": current_time
                    })
                    updated_count += 1
            else:
                # New file entry (no longer needs individual UUID)
                manifest_data["datasets"][normalized_filename] = {
                    "sha256": file_sha256,
                    "size_bytes": file_size,
                    "size_human": format_size(file_size),
                    "uploaded": current_time,
                    "description": ""
                }
                logging.info(f"Added {normalized_filename} to manifest")
                added_count += 1
        
        # Write updated manifest if there were any changes
        if added_count > 0 or updated_count > 0:
            with open(manifest_path, "w") as f:
                yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)
        
        # Print summary
        if len(valid_files) > 1:
            logging.info(f"Summary: {added_count} added, {updated_count} updated, {unchanged_count} unchanged")
        
    except Exception as e:
        logging.error(f"Failed to process files: {e}")
        sys.exit(1)


@main.command()
@click.argument("filenames", nargs=-1)
@click.option("--remote", default="1", help="Remote server to use (e.g., 1 for remote@1, 2 for remote@2)")
@click.pass_context
def pull(ctx: click.Context, filenames: Tuple[str, ...], remote: str) -> None:
    """Pull files from remote server.
    
    Downloads files from the remote server using the manifest UUID as the directory.
    Files are downloaded to the current directory and verified against their SHA256 hashes.
    
    Args:
        ctx: Click context object.
        filenames: Tuple of specific filenames to pull. If empty, pulls all files.
        remote: Remote server identifier (e.g., '1' for 'remote@1').
        
    Raises:
        SystemExit: If no manifest exists, remote config missing, or operation fails.
    """
    manifest_path = Path("manifest.yml")
    
    # Check if manifest exists
    if not manifest_path.exists():
        logging.error("No manifest.yml found in current directory. Run 'dss init' first.")
        sys.exit(1)
    
    try:
        # Load manifest
        with open(manifest_path, "r") as f:
            manifest_data = yaml.safe_load(f)
        
        # Check for remote configuration
        remote_key = f"remote@{remote}"
        if remote_key not in manifest_data:
            logging.error(f"No {remote_key} configuration found in manifest")
            sys.exit(1)
        
        remote_config = manifest_data[remote_key]
        required_keys = ["uname", "url", "base_path"]
        for key in required_keys:
            if key not in remote_config:
                logging.error(f"Missing required remote configuration: {key}")
                sys.exit(1)
        
        # Extract remote configuration
        remote_user = remote_config["uname"]
        remote_url = remote_config["url"]
        remote_base_path = remote_config["base_path"]
        remote_port = remote_config.get("port", 22)  # Default SSH port
        
        # Get datasets from manifest
        datasets = manifest_data.get("datasets", {})
        if not datasets:
            logging.error("No datasets found in manifest")
            sys.exit(1)
        
        # Determine which files to pull
        files_to_pull = []
        if filenames:
            # Pull specific files
            for filename in filenames:
                if filename in datasets:
                    files_to_pull.append(filename)
                else:
                    logging.warning(f"File not found in manifest, skipping: {filename}")
        else:
            # Pull all files
            files_to_pull = list(datasets.keys())
        
        if not files_to_pull:
            logging.error("No files to pull")
            sys.exit(1)
        
        # Counters for summary
        pulled_count = 0
        unchanged_count = 0
        missing_count = 0
        manifest_updated = False
        
        # Get manifest UUID
        manifest_uuid = manifest_data.get("manifest_uuid")
        if not manifest_uuid:
            logging.error("No manifest UUID found in manifest")
            sys.exit(1)
        
        # Pull each file
        for filename in files_to_pull:
            file_info = datasets[filename]
            expected_sha256 = file_info.get("sha256", "")
            
            # Build remote path: base_path/manifest_uuid/filename
            remote_dir = f"{remote_base_path.rstrip('/')}/{manifest_uuid}"
            remote_file_path = f"{remote_dir}/{filename}"
            
            # Check if remote file exists using SSH ls command
            ssh_check_cmd = [
                "ssh",
                f"-p", str(remote_port),
                f"{remote_user}@{remote_url}",
                f"ls {remote_file_path}"
            ]
            
            result = subprocess.run(ssh_check_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.warning(f"Remote file not found: {remote_file_path}")
                missing_count += 1
                continue
            
            # Build rsync command to download
            local_file = Path(filename)
            rsync_cmd = [
                "rsync",
                "-avz",
                f"-e", f"ssh -p {remote_port}",
                f"{remote_user}@{remote_url}:{remote_file_path}",
                str(local_file)
            ]
            
            logging.info(f"Pulling {filename} from {remote_url}:{remote_file_path}")
            result = subprocess.run(rsync_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # File downloaded successfully, now check SHA256
                if local_file.exists():
                    local_sha256 = calculate_sha256(local_file)
                    if local_sha256 == expected_sha256:
                        logging.info(f"Successfully pulled: {filename} (SHA256 verified)")
                        unchanged_count += 1
                    else:
                        logging.warning(f"Pulled {filename} but SHA256 mismatch! Expected: {expected_sha256}, Got: {local_sha256}")
                        pulled_count += 1
                    
                    # Update dataset with remote path (relative to base_path) after successful pull
                    relative_path = f"{manifest_uuid}/{filename}"
                    manifest_data["datasets"][filename][remote_key] = relative_path
                    manifest_updated = True
                else:
                    logging.error(f"File downloaded but not found locally: {filename}")
            else:
                logging.error(f"Failed to pull {filename}: {result.stderr}")
        
        # Save updated manifest if any files were successfully pulled
        if manifest_updated:
            with open(manifest_path, "w") as f:
                yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)
            logging.debug("Updated manifest with remote paths")
        
        # Print summary
        if len(files_to_pull) > 1:
            logging.info(f"Pull summary: {pulled_count} changed, {unchanged_count} unchanged, {missing_count} missing")
        
    except Exception as e:
        logging.error(f"Failed to pull files: {e}")
        sys.exit(1)


@main.command()
@click.argument("filenames", nargs=-1)
@click.option("--remote", default="1", help="Remote server to use (e.g., 1 for remote@1, 2 for remote@2)")
@click.pass_context
def push(ctx: click.Context, filenames: Tuple[str, ...], remote: str) -> None:
    """Push files to remote server.
    
    Uploads files to the remote server using the manifest UUID as the directory.
    Creates the remote directory structure if it doesn't exist.
    
    Args:
        ctx: Click context object.
        filenames: Tuple of specific filenames to push. If empty, pushes all files.
        remote: Remote server identifier (e.g., '1' for 'remote@1').
        
    Raises:
        SystemExit: If no manifest exists, remote config missing, or operation fails.
    """
    manifest_path = Path("manifest.yml")
    
    # Check if manifest exists
    if not manifest_path.exists():
        logging.error("No manifest.yml found in current directory. Run 'dss init' first.")
        sys.exit(1)
    
    try:
        # Load manifest
        with open(manifest_path, "r") as f:
            manifest_data = yaml.safe_load(f)
        
        # Check for remote configuration
        remote_key = f"remote@{remote}"
        if remote_key not in manifest_data:
            logging.error(f"No {remote_key} configuration found in manifest")
            sys.exit(1)
        
        remote_config = manifest_data[remote_key]
        required_keys = ["uname", "url", "base_path"]
        for key in required_keys:
            if key not in remote_config:
                logging.error(f"Missing required remote configuration: {key}")
                sys.exit(1)
        
        # Extract remote configuration
        remote_user = remote_config["uname"]
        remote_url = remote_config["url"]
        remote_base_path = remote_config["base_path"]
        remote_port = remote_config.get("port", 22)  # Default SSH port
        
        # Get datasets from manifest
        datasets = manifest_data.get("datasets", {})
        if not datasets:
            logging.error("No datasets found in manifest")
            sys.exit(1)
        
        # Determine which files to push
        files_to_push = []
        if filenames:
            # Push specific files
            for filename in filenames:
                if filename in datasets:
                    files_to_push.append(filename)
                else:
                    logging.warning(f"File not found in manifest, skipping: {filename}")
        else:
            # Push all files
            files_to_push = list(datasets.keys())
        
        if not files_to_push:
            logging.error("No files to push")
            sys.exit(1)
        
        # Get manifest UUID
        manifest_uuid = manifest_data.get("manifest_uuid")
        if not manifest_uuid:
            logging.error("No manifest UUID found in manifest")
            sys.exit(1)
        
        # Track successful pushes for manifest updates
        manifest_updated = False
        
        # Push each file
        for filename in files_to_push:
            file_info = datasets[filename]
            
            # Check if local file exists
            local_file = Path(filename)
            if not local_file.exists():
                logging.error(f"Local file not found: {filename}")
                continue
            
            # Build remote path: base_path/manifest_uuid/filename
            remote_dir = f"{remote_base_path.rstrip('/')}/{manifest_uuid}"
            remote_file_path = f"{remote_dir}/{filename}"
            
            # Create remote directory first
            ssh_cmd = [
                "ssh",
                f"-p", str(remote_port),
                f"{remote_user}@{remote_url}",
                f"mkdir -p {remote_dir}"
            ]
            
            logging.info(f"Creating remote directory: {remote_dir}")
            result = subprocess.run(ssh_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Failed to create remote directory: {result.stderr}")
                continue
            
            # Build rsync command
            rsync_cmd = [
                "rsync",
                "-avz",
                f"-e", f"ssh -p {remote_port}",
                str(local_file),
                f"{remote_user}@{remote_url}:{remote_file_path}"
            ]
            
            logging.info(f"Pushing {filename} to {remote_url}:{remote_file_path}")
            result = subprocess.run(rsync_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info(f"Successfully pushed: {filename}")
                # Update dataset with remote path (relative to base_path)
                relative_path = f"{manifest_uuid}/{filename}"
                manifest_data["datasets"][filename][remote_key] = relative_path
                manifest_updated = True
            else:
                logging.error(f"Failed to push {filename}: {result.stderr}")
        
        # Save updated manifest if any files were successfully pushed
        if manifest_updated:
            with open(manifest_path, "w") as f:
                yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)
            logging.debug("Updated manifest with remote paths")
        
    except Exception as e:
        logging.error(f"Failed to push files: {e}")
        sys.exit(1)


@main.command()
@click.pass_context
def expand(ctx: click.Context) -> None:
    """Expand tar and tar.bz2 files in current directory.
    
    Finds all .tar and .tar.bz2 files in the current directory and extracts them.
    Skips files whose corresponding directories already exist.
    
    Args:
        ctx: Click context object.
        
    Raises:
        SystemExit: If no manifest exists in the current directory.
    """
    manifest_path = Path("manifest.yml")
    
    # Check if manifest exists
    if not manifest_path.exists():
        logging.error("No manifest.yml found in current directory.")
        sys.exit(1)
    
    # Find tar and tar.bz2 files in current directory
    tar_files = []
    for pattern in ["*.tar", "*.tar.bz2"]:
        tar_files.extend(glob.glob(pattern))
    
    if not tar_files:
        logging.info("No tar or tar.bz2 files found in current directory")
        return
    
    expanded_count = 0
    skipped_count = 0
    
    for tar_file in tar_files:
        tar_path = Path(tar_file)
        
        # Determine the directory name (remove .tar or .tar.bz2)
        if tar_file.endswith('.tar.bz2'):
            dir_name = tar_file[:-8]  # Remove .tar.bz2
        elif tar_file.endswith('.tar'):
            dir_name = tar_file[:-4]  # Remove .tar
        else:
            continue
        
        dir_path = Path(dir_name)
        
        # Check if directory already exists
        if dir_path.exists():
            logging.info(f"Directory {dir_name} already exists, skipping {tar_file}")
            skipped_count += 1
            continue
        
        # Extract the tar file
        try:
            logging.info(f"Expanding {tar_file} to {dir_name}")
            with tarfile.open(tar_path, 'r:*') as tar:
                tar.extractall(path='.')
            expanded_count += 1
            logging.info(f"Successfully expanded {tar_file}")
        except Exception as e:
            logging.error(f"Failed to expand {tar_file}: {e}")
    
    logging.info(f"Expand summary: {expanded_count} expanded, {skipped_count} skipped")


@main.command()
@click.pass_context
def compress(ctx: click.Context) -> None:
    """Compress directories to tar.bz2 files in current directory.
    
    Finds all directories in the current directory (excluding hidden and special dirs)
    and compresses them to .tar.bz2 files. Skips directories whose corresponding
    archive files already exist.
    
    Args:
        ctx: Click context object.
        
    Raises:
        SystemExit: If no manifest exists in the current directory.
    """
    manifest_path = Path("manifest.yml")
    
    # Check if manifest exists
    if not manifest_path.exists():
        logging.error("No manifest.yml found in current directory.")
        sys.exit(1)
    
    # Find directories in current directory (excluding hidden and special directories)
    directories = []
    for item in Path('.').iterdir():
        if item.is_dir() and not item.name.startswith('.') and item.name != '__pycache__':
            directories.append(item.name)
    
    if not directories:
        logging.info("No directories found in current directory")
        return
    
    compressed_count = 0
    skipped_count = 0
    
    for dir_name in directories:
        tar_file = f"{dir_name}.tar.bz2"
        tar_path = Path(tar_file)
        
        # Check if tar.bz2 file already exists
        if tar_path.exists():
            logging.info(f"Archive {tar_file} already exists, skipping {dir_name}")
            skipped_count += 1
            continue
        
        # Create the tar.bz2 file
        try:
            logging.info(f"Compressing {dir_name} to {tar_file}")
            with tarfile.open(tar_path, 'w:bz2') as tar:
                tar.add(dir_name, arcname=dir_name)
            compressed_count += 1
            logging.info(f"Successfully compressed {dir_name}")
        except Exception as e:
            logging.error(f"Failed to compress {dir_name}: {e}")
    
    logging.info(f"Compress summary: {compressed_count} compressed, {skipped_count} skipped")


if __name__ == "__main__":
    main()