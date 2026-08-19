"""Thin subprocess wrapper around the `borg` CLI.

Each function here shells out to one `borg` subcommand and turns a non-zero
exit code into a BorgError, so the rest of the app doesn't need to know
about subprocess.CompletedProcess or borg's own output format.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


class BorgError(RuntimeError):
    pass


def _env() -> dict[str, str]:
    # Relic always creates repos with --encryption none, so it should never
    # get stuck on borg's interactive "unknown unencrypted repository"
    # confirmation prompt when a repo is accessed for the first time.
    return {**os.environ, "BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK": "yes"}


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, env=_env(), **kwargs)


def check_repo(repo_url: str) -> bool:
    result = _run(
        ["borg", "check", "--bypass-lock", "--repository-only", repo_url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def repo_exists(repo_url: str) -> bool:
    result = _run(
        ["borg", "check", repo_url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def init_repo(repo_url: str) -> None:
    result = _run(
        ["borg", "init", "--encryption", "none", repo_url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise BorgError(f"couldn't create {repo_url} repo")


def create_archive(
    repo_url: str,
    archive_name: str,
    *,
    cwd: Path,
    path: str,
    excludes: list[str],
) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt") as exclude_file:
        exclude_file.write("\n".join(excludes))
        exclude_file.flush()
        result = _run(
            [
                "borg",
                "create",
                "--stats",
                "--list",
                "--compression",
                "lzma",
                f"{repo_url}::{archive_name}",
                "--exclude-from",
                exclude_file.name,
                path,
            ],
            cwd=cwd,
        )
    if result.returncode != 0:
        raise BorgError(f"couldn't create archive {repo_url}::{archive_name}")


def list_archives(repo_url: str) -> list[str]:
    result = _run(
        ["borg", "list", "--json", repo_url], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise BorgError(f"couldn't fetch archives list for {repo_url}")
    data = json.loads(result.stdout)
    return [archive["name"] for archive in data["archives"]]


def last_archive(repo_url: str) -> str | None:
    result = _run(
        ["borg", "list", repo_url, "--last", "1", "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BorgError(f"couldn't fetch last archive for {repo_url}")
    archives = json.loads(result.stdout)["archives"]
    return archives[0]["name"] if archives else None


def print_archive_details(repo_url: str, archive_name: str) -> None:
    result = _run(["borg", "info", f"{repo_url}::{archive_name}"])
    if result.returncode != 0:
        raise BorgError(f"couldn't fetch details for {archive_name}")


def is_mounted(mount_path: Path) -> bool:
    result = _run(["mount"], capture_output=True, text=True)
    return str(mount_path) in result.stdout


def mount_repo(repo_url: str, mount_path: Path) -> None:
    mount_path.mkdir(parents=True, exist_ok=True)
    if is_mounted(mount_path):
        return
    result = _run(["borg", "mount", repo_url, str(mount_path)])
    if result.returncode != 0:
        raise BorgError(f"couldn't mount {repo_url}")


def unmount_repo(mount_path: Path) -> None:
    result = _run(["borg", "umount", str(mount_path)])
    if result.returncode != 0:
        raise BorgError(f"couldn't unmount {mount_path}")


def extract(
    repo_url: str,
    archive_name: str,
    *,
    cwd: Path,
    path: str | None = None,
    verbose: bool = False,
    list_files: bool = False,
) -> None:
    args = ["borg", "extract"]
    if verbose:
        args.append("--verbose")
    if list_files:
        args.append("--list")
    args.append(f"{repo_url}::{archive_name}")
    if path:
        args.append(path)
    result = _run(args, cwd=cwd)
    if result.returncode != 0:
        raise BorgError(f"couldn't restore from {repo_url}::{archive_name}")
