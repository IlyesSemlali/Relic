"""Loads backups.yaml and resolves each backup's basedir/path/excludes.

See the "Configuration" section of the README for the YAML shape this
module reads.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

HOME_BACKUP_NAME = "home"


class BackupSpec(BaseModel):
    basedir: str = "~"
    # Always ends in "/" (set by load_config), so it's easy to concatenate
    # with basedir or another string without checking for a separator first.
    path: str
    excludes: list[str] = Field(default_factory=list)


class RelicConfig(BaseModel):
    backups: dict[str, BackupSpec]
    excludes: list[str] = Field(default_factory=list)

    def declared_backups(self) -> list[str]:
        """Backup names the user actually wrote in backups.yaml.

        Excludes the synthetic "home" backup: it always exists implicitly
        (see load_config) but isn't something a user declares themselves, so
        commands like `relic init --all` shouldn't try to loop over it.
        """
        return [name for name in self.backups if name != HOME_BACKUP_NAME]

    def is_declared(self, name: str) -> bool:
        return name in self.backups


def load_config(path: Path) -> RelicConfig:
    raw: dict = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text()) or {}

    backups: dict[str, BackupSpec] = {}
    for name, entry in (raw.get("backups") or {}).items():
        entry = entry or {}
        raw_path = entry.get("path") or name
        backups[name] = BackupSpec(
            basedir=entry.get("basedir") or "~",
            path=f"{raw_path}/",
            excludes=list(entry.get("excludes") or []),
        )

    # The "home" backup always exists and always wins over a user-declared
    # entry with the same name: it's how we back up "everything else under
    # $HOME" without the user having to list it explicitly.
    backups[HOME_BACKUP_NAME] = BackupSpec(basedir="~", path="./", excludes=[])

    return RelicConfig(backups=backups, excludes=list(raw.get("excludes") or []))


def _expand_home(value: str, home: str) -> str:
    return value.replace("~", home)


def resolve_basedir(config: RelicConfig, name: str, home: str) -> str:
    return _expand_home(config.backups[name].basedir, home)


def resolve_path(config: RelicConfig, name: str, home: str) -> str:
    return _expand_home(config.backups[name].path, home)


def resolve_fullpath(config: RelicConfig, name: str, home: str) -> str:
    spec = config.backups[name]
    full = _expand_home(f"{spec.basedir}/{spec.path}", home)
    # For the "home" backup, path is "./", so full ends up as "$HOME/./".
    # Strip that trailing "/./" so the fullpath is just plain $HOME.
    return re.sub(r"/./?$", "", full)


def resolve_excludes(config: RelicConfig, name: str, home: str) -> list[str]:
    """Build the list of exclude patterns to pass to `borg create` for one backup.

    Combines three sources: the global excludes, this backup's own excludes
    (made absolute by prefixing them with its fullpath), and every *other*
    backup's path. That last part matters most for "home": without it, the
    home backup would also recursively back up the "documents" backup's own
    tree, duplicating data that's already covered by its own archive.
    """
    spec = config.backups[name]
    full = resolve_fullpath(config, name, home)
    base = resolve_basedir(config, name, home)

    combined: list[str] = []
    combined.extend(config.excludes)
    combined.extend(full + exclude for exclude in spec.excludes)
    combined.extend(
        f"{other.basedir}/{other.path}"
        for other_name, other in config.backups.items()
        if other_name != name
    )

    def normalize(value: str) -> str:
        value = _expand_home(value, home)
        value = re.sub(r"/$", "", value)
        value = re.sub(r"/\.$", "", value)
        return value

    # Keep only patterns that make sense for this backup: relative patterns
    # (e.g. "*.tmp") always apply, absolute paths only apply if they fall
    # under this backup's basedir. Also drop a pattern equal to the basedir
    # itself, which would otherwise exclude everything.
    result: list[str] = []
    for value in (normalize(v) for v in combined):
        is_absolute = value.startswith("/")
        if not ((value.startswith(base) and is_absolute) or not is_absolute):
            continue
        if value == base:
            continue
        if value.startswith(base + "/"):
            value = value[len(base) + 1 :]
        result.append(value)
    return result
