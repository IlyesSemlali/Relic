import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Matches a local path (e.g. "/mnt/backups") or an ssh:// URL followed by a
# path (e.g. "ssh://user@host:22/backups"), so BORG_REPO can point at either
# a local directory or a remote Borg repository over SSH.
BORG_REPO_PATTERN = re.compile(
    r"^(ssh://[0-9a-z]*(@[0-9a-z]*)?(:[0-9]*)?)?(/[0-9A-Za-z]*)*$"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    borg_repo: str
    backup_config_file: Path = Path("~/.config/backups.yaml")
    borg_mount_path: Path = Path("~/Backups")

    @field_validator("borg_repo")
    @classmethod
    def _validate_borg_repo(cls, value: str) -> str:
        if not BORG_REPO_PATTERN.match(value):
            raise ValueError(f"BORG_REPO {value!r} doesn't match the expected pattern")
        return value

    @property
    def backup_config_path(self) -> Path:
        return self.backup_config_file.expanduser()

    @property
    def borg_mount_root(self) -> Path:
        return self.borg_mount_path.expanduser()

    def repo_url(self, backup_name: str) -> str:
        return f"{self.borg_repo}/{backup_name}"
