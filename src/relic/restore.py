"""Interactive path lookup, and safely restoring a path from an archive."""

from __future__ import annotations

import re
from pathlib import Path

from . import borg, fzf


def find_archived_path(repo_url: str, mount_path: Path) -> tuple[str, list[str]] | None:
    """Mount the repo, let the user fzf-pick a path that existed in some
    archive, and return (path, [archive names containing that path]).
    """
    borg.mount_repo(repo_url, mount_path)
    try:
        # Mounting a repo exposes every archive as a subdirectory of
        # mount_path, e.g. "<mount_path>/<archive_name>/documents/notes.txt".
        # Strip that "<mount_path>/<archive_name>/" prefix from each entry so
        # the same file appearing in several archives collapses to one
        # candidate: "documents/notes.txt".
        prefix_re = re.compile(rf"^{re.escape(str(mount_path))}/[A-Za-z0-9_-]+/")
        candidates: set[str] = set()
        for entry in mount_path.rglob("*"):
            text = str(entry)
            stripped, matched = prefix_re.subn("", text, count=1)
            if matched and stripped != str(mount_path):
                candidates.add(stripped)

        chosen = fzf.select_one(sorted(candidates, reverse=True), border_label="Archived Files")
        if not chosen:
            return None

        # Now do the reverse lookup: which archive directories actually
        # contain the chosen path? Those are the archives the user can
        # restore it from.
        mount_prefix = f"{mount_path}/"
        suffix = f"/{chosen}"
        archives: list[str] = []
        for entry in mount_path.rglob("*"):
            text = str(entry)
            if text == chosen:
                rel = text
            elif text.endswith(suffix):
                rel = text[: -len(suffix)]
            else:
                continue
            if rel.startswith(mount_prefix):
                archives.append(rel[len(mount_prefix) :])

        seen: set[str] = set()
        unique_archives = [a for a in archives if not (a in seen or seen.add(a))]
        return chosen, unique_archives
    finally:
        borg.unmount_repo(mount_path)


def restore_path(repo_url: str, archive_name: str, basedir: Path, backup_path: str) -> None:
    # Backup paths may carry a trailing slash (e.g. "documents/", "./"); strip
    # it so the pre-restore sibling is a rename of the target, not a file
    # created inside it.
    backup_path = backup_path.rstrip("/") or "."
    target = basedir / backup_path
    if target.exists() or target.is_symlink():
        sibling = target.with_name(f"{target.name}.pre-restore-{archive_name}")
        target.rename(sibling)
    borg.extract(repo_url, archive_name, cwd=basedir, path=backup_path, list_files=True)
