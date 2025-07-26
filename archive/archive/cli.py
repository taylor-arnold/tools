"""Command line interface for archive - Dataset archive tools.

This module provides a CLI for managing data archives with manifest files.
It supports file tracking, remote synchronization, and archive operations.
"""

import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path

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
        format="%(message)s",
    )


def ensure_gitignore(local_ref_path: str) -> None:
    """
    Ensures that the specified `local_ref_path` is listed in the .gitignore file
    in the current working directory. If the file does not exist, it is created
    with `local_ref_path` as its content. If it exists but does not contain the
    path, the path is appended.

    Args:
        local_ref_path (str): The path to be added to the .gitignore file.
    """
    gitignore_path = Path(".gitignore")
    local_path_entry = local_ref_path.strip()

    if gitignore_path.exists():
        with gitignore_path.open("r+", encoding="utf-8") as file:
            lines = [line.strip() for line in file.readlines()]
            if local_path_entry not in lines:
                file.write(f"\n{local_path_entry}\n")
    else:
        with gitignore_path.open("w", encoding="utf-8") as file:
            file.write(f"{local_path_entry}\n")



def process_archive_files(cmd: list[str]):
    archive_files = []

    for root, _, files in os.walk(os.getcwd()):
        if 'archive.yml' in files:
            archive_files.append(os.path.join(root, 'archive.yml'))

    for archive_path in archive_files:
        path_rel = os.path.relpath(archive_path, os.getcwd())
        dir_path = os.path.dirname(archive_path)
        try:
            result = subprocess.run(
                cmd,
                cwd=dir_path,
                check=True,
                capture_output=True,
                text=True
            )
            click.echo(
                f"{Fore.GREEN}Success pushing {path_rel}{Style.RESET_ALL}"
            )
        except subprocess.CalledProcessError as e:
            click.echo(
                f"{Fore.RED}Error pushing {path_rel}{Style.RESET_ALL}"
            )

    click.echo(f"\nTotal archive.yml files found: {len(archive_files)}")


@click.group()
@click.version_option(version=__version__)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """archive - Dataset archive tools.

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
@click.option('--refpath', default='', help='Optional reference path')
@click.pass_context
def init(ctx: click.Context, refpath: str) -> None:
    """Initialize a new manifest file.

    Creates a new archive.yml file in the current directory with a unique UUID.

    Args:
        ctx: Click context object.

    Raises:
        SystemExit: If manifest already exists or creation fails.
    """
    manifest_path = Path("archive.yml")

    if manifest_path.exists():
        click.echo(f"Manifest file already exists: {manifest_path}")
        sys.exit(1)

    # Create empty manifest structure with manifest-level UUID
    manifest_uuid = str(uuid.uuid4())
    manifest_data = {}

    # Try to load default remote configurations
    config_path = Path.home() / ".config" / "archive" / "remote"
    if config_path.exists():
        try:
            with open(config_path) as f:
                remote_configs = yaml.safe_load(f)

            if remote_configs and isinstance(remote_configs, dict):
                # Add remote configurations to manifest
                for remote_key, remote_config in remote_configs.items():
                    if remote_key.startswith("remote@"):
                        if refpath:
                            remote_config['local_ref_path'] = refpath
                        remote_config["base_path"] = str(
                            Path(remote_config["base_path"]) / str(uuid.uuid4())
                        ) + "/"
                        manifest_data[remote_key] = remote_config
                click.echo(
                    f"Loaded {len([k for k in remote_configs.keys() if k.startswith('remote@')])} remote configurations from config"
                )
            else:
                logging.debug("Config file is empty or invalid format")
        except Exception as e:
            click.echo(f"Failed to load remote config from {config_path}: {e}")
    else:
        logging.debug(f"No remote config found at {config_path}")

    try:
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

        click.echo(
            f"Initialized new manifest: {manifest_path} (UUID: {manifest_uuid})"
        )

    except Exception as e:
        logging.error(f"Failed to create manifest file: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--remote",
    default="1",
    help="Remote server to use (e.g., 1 for remote@1, 2 for remote@2)",
)
@click.pass_context
def push(ctx: click.Context, remote: str) -> None:
    manifest_path = Path("archive.yml")

    # Check if manifest exists
    if not manifest_path.exists():
        click.echo(
            "No archive.yml found in current directory. Run 'archive init' first."
        )
        sys.exit(1)

    try:
        # Load manifest
        with open(manifest_path) as f:
            manifest_data = yaml.safe_load(f)

        # Check for remote configuration
        remote_key = f"remote@{remote}"
        if remote_key not in manifest_data:
            click.echo(f"No {remote_key} configuration found in manifest")
            sys.exit(1)

        remote_config = manifest_data[remote_key]
        required_keys = ["uname", "url", "base_path"]
        for key in required_keys:
            if key not in remote_config:
                click.echo(f"Missing required remote configuration: {key}")
                sys.exit(1)

        # Extract remote configuration
        remote_user = remote_config["uname"]
        remote_url = remote_config["url"]
        remote_base_path = remote_config["base_path"]
        remote_port = remote_config.get("port", 22)

        # Extract local configuration
        local_ref_path = remote_config["local_ref_path"]

        # Make sure directory is in .gitignore
        if local_ref_path:
            ensure_gitignore(local_ref_path)

        # Get remote filepath
        if not remote_base_path.endswith("/"):
            remote_base_path += "/"

        # Make sure directory exists on remote host
        ssh_cmd = [
            "ssh",
            "-p",
            f"{remote_port}",
            f"{remote_user}@{remote_url}",
            f"mkdir -p {remote_base_path}",
        ]
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)

        # Build the rsync command
        rsync_cmd = [
            "rsync",
            "-avz",
            "-e",
            f"ssh -p {remote_port}",
            '--exclude=".[!.]*"',
            f"{str(Path.cwd() / local_ref_path) + '/'}",
            f"{remote_user}@{remote_url}:{remote_base_path}",
        ]

        click.echo(f"Pushing data to {remote_url}:{remote_base_path}")
        result = subprocess.run(rsync_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            click.echo(f"{result.stdout}")
        else:
            click.echo(f"Failed to push to: {result.stderr}")

    except Exception as e:
        logging.error(f"Failed to push: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--remote",
    default="1",
    help="Remote server to use (e.g., 1 for remote@1, 2 for remote@2)",
)
@click.option(
    "--filename",
    default="",
    help="Optional filename to grab",
)
@click.pass_context
def pull(ctx: click.Context, remote: str, filename: str) -> None:
    manifest_path = Path("archive.yml")

    # Check if manifest exists
    if not manifest_path.exists():
        click.echo(
            "No archive.yml found in current directory. Run 'archive init' first."
        )
        sys.exit(1)

    try:
        # Load manifest
        with open(manifest_path) as f:
            manifest_data = yaml.safe_load(f)

        # Check for remote configuration
        remote_key = f"remote@{remote}"
        if remote_key not in manifest_data:
            click.echo(f"No {remote_key} configuration found in manifest")
            sys.exit(1)

        remote_config = manifest_data[remote_key]
        required_keys = ["uname", "url", "base_path"]
        for key in required_keys:
            if key not in remote_config:
                click.echo(f"Missing required remote configuration: {key}")
                sys.exit(1)

        # Extract remote configuration
        remote_user = remote_config["uname"]
        remote_url = remote_config["url"]
        remote_base_path = remote_config["base_path"]
        remote_port = remote_config.get("port", 22)

        # Extract local configuration
        local_ref_path = remote_config["local_ref_path"]

        # Make sure directory is in .gitignore
        if local_ref_path:
            ensure_gitignore(local_ref_path)

        # Get remote filepath
        if not remote_base_path.endswith("/"):
            remote_base_path += "/"

        # Determine what to grab on remote host
        files_to_grab = f"{remote_user}@{remote_url}:{remote_base_path}"
        if filename:
            files_to_grab += filename

        # Build the rsync command
        rsync_cmd = [
            "rsync",
            "-avz",
            "-e",
            f"ssh -p {remote_port}",
            '--exclude=".[!.]*"',
            files_to_grab,
            f"{str(Path.cwd() / local_ref_path) + '/'}",
        ]

        click.echo(f"Pulling data from {remote_url}:{remote_base_path}")
        result = subprocess.run(rsync_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            click.echo(f"{result.stdout}")
        else:
            click.echo(f"Failed to pull from: {result.stderr}")

    except Exception as e:
        logging.error(f"Failed to pull: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--remote",
    default="1",
    help="Remote server to use (e.g., 1 for remote@1, 2 for remote@2)",
)
@click.pass_context
def list(ctx: click.Context, remote: str) -> None:
    manifest_path = Path("archive.yml")

    # Check if manifest exists
    if not manifest_path.exists():
        click.echo(
            "No archive.yml found in current directory. Run 'archive init' first."
        )
        sys.exit(1)

    try:
        # Load manifest
        with open(manifest_path) as f:
            manifest_data = yaml.safe_load(f)

        # Check for remote configuration
        remote_key = f"remote@{remote}"
        if remote_key not in manifest_data:
            click.echo(f"No {remote_key} configuration found in manifest")
            sys.exit(1)

        remote_config = manifest_data[remote_key]
        required_keys = ["uname", "url", "base_path"]
        for key in required_keys:
            if key not in remote_config:
                click.echo(f"Missing required remote configuration: {key}")
                sys.exit(1)

        # Extract remote configuration
        remote_user = remote_config["uname"]
        remote_url = remote_config["url"]
        remote_base_path = remote_config["base_path"]
        remote_port = remote_config.get("port", 22)

        # Extract local configuration
        local_ref_path = remote_config["local_ref_path"]

        # Get remote filepath
        if not remote_base_path.endswith("/"):
            remote_base_path += "/"

        # Build the ssh command
        ssh_check_cmd = [
            "ssh",
            "-p",
            str(remote_port),
            f"{remote_user}@{remote_url}",
            f"ls -lh {remote_base_path}",
        ]

        click.echo(f"Pulling data from {remote_url}:{remote_base_path}")
        result = subprocess.run(ssh_check_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            click.echo(f"{result.stdout}")
        else:
            click.echo(f"Failed to pull from: {result.stderr}")

    except Exception as e:
        logging.error(f"Failed to pull: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--remote",
    default="1",
    help="Remote server to use (e.g., 1 for remote@1, 2 for remote@2)",
)
@click.pass_context
def validate(ctx: click.Context, remote: str) -> None:

    try:
        process_archive_files(['archive', 'push'])
    except Exception as e:
        logging.error(f"Failed to pull: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
