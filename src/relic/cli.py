from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError

from . import borg, config as config_mod, fzf, logs, naming, restore as restore_mod
from .settings import Settings

app = typer.Typer(
    help="Relic - a Borg wrapper that helps create standard backups the smartest way possible.",
    no_args_is_help=True,
)


def _load() -> tuple[Settings, config_mod.RelicConfig, str]:
    try:
        settings = Settings()
    except ValidationError as exc:
        for err in exc.errors():
            logs.error("backup", f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}")
        raise typer.Exit(1)
    cfg = config_mod.load_config(settings.backup_config_path)
    home = str(Path.home())
    return settings, cfg, home


def _require_declared(cfg: config_mod.RelicConfig, name: str) -> None:
    if not cfg.is_declared(name):
        logs.error("backup", f"{name} not declared")
        raise typer.Exit(1)


@app.command()
def init(
    name: Optional[str] = typer.Argument(None, help="Backup name to initialize a repo for"),
    all_: bool = typer.Option(False, "--all", "-a", help="Initialize every declared backup's repo"),
) -> None:
    """Initiate a new borg repo (or every declared repo with --all)."""
    settings, cfg, _ = _load()

    if all_ and name:
        logs.error("backup", "pass either a backup name or --all, not both")
        raise typer.Exit(1)
    if not all_ and not name:
        logs.error("backup", "no backup was specified")
        raise typer.Exit(1)

    targets = cfg.declared_backups() if all_ else [name]

    for target in targets:
        _require_declared(cfg, target)
        repo_url = settings.repo_url(target)

        if borg.repo_exists(repo_url):
            logs.info("backup", f'the "{target}" repo already exists')
            continue

        try:
            borg.init_repo(repo_url)
            logs.info("backup", f'successfully created the "{target}" repo')
        except borg.BorgError as exc:
            logs.error("backup", str(exc))
            raise typer.Exit(1)


@app.command()
def create(
    name: Optional[str] = typer.Argument(None, help="Backup name to create an archive for"),
    all_: bool = typer.Option(False, "--all", "-a", help="Create an archive for every declared backup"),
) -> None:
    """Create a new backup archive."""
    settings, cfg, home = _load()

    if all_:
        targets = cfg.declared_backups()
    else:
        if not name:
            logs.error("backup", "no backup was specified")
            raise typer.Exit(1)
        targets = [name]

    for target in targets:
        if target != config_mod.HOME_BACKUP_NAME:
            _require_declared(cfg, target)

        repo_url = settings.repo_url(target)
        if not borg.check_repo(repo_url):
            logs.error("backup", "couldn't connect to host")
            raise typer.Exit(1)

        basedir = Path(config_mod.resolve_basedir(cfg, target, home))
        path = config_mod.resolve_path(cfg, target, home)
        excludes = config_mod.resolve_excludes(cfg, target, home)
        archive_name = naming.default_archive_name()

        try:
            borg.create_archive(repo_url, archive_name, cwd=basedir, path=path, excludes=excludes)
            logs.info("backup", f"successfully created archive {repo_url}::{archive_name}")
        except borg.BorgError as exc:
            logs.error("backup", str(exc))
            raise typer.Exit(1)


@app.command(name="list")
def list_(
    name: Optional[str] = typer.Argument(None, help="Backup to list archives for (defaults to all declared backups)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Pick an archive with fzf and show its details"),
) -> None:
    """List backups and their archives."""
    settings, cfg, _ = _load()

    if name:
        _require_declared(cfg, name)
        repo_url = settings.repo_url(name)
        archives = borg.list_archives(repo_url)

        if interactive:
            chosen = fzf.select_one(archives, border_label="Backups")
            if chosen:
                borg.print_archive_details(repo_url, chosen)
            return

        typer.echo(f"{name}:")
        for archive in archives:
            typer.echo(f"  {archive}")
        return

    if interactive:
        choices: list[str] = []
        index: dict[str, tuple[str, str]] = {}
        for backup in cfg.declared_backups():
            for archive in borg.list_archives(settings.repo_url(backup)):
                label = f"{backup}::{archive}"
                choices.append(label)
                index[label] = (backup, archive)

        chosen = fzf.select_one(choices, border_label="Backups")
        if chosen:
            backup, archive = index[chosen]
            borg.print_archive_details(settings.repo_url(backup), archive)
        return

    for backup in cfg.declared_backups():
        typer.echo(f"{backup}:")
        for archive in borg.list_archives(settings.repo_url(backup)):
            typer.echo(f"  {archive}")


@app.command()
def restore(
    name: str = typer.Argument(..., help="Backup to restore from"),
    archive: Optional[str] = typer.Argument(None, help="Archive name (defaults to the last archive, or picked interactively)"),
    path: Optional[str] = typer.Argument(None, help="Path to restore, relative to the backup's basedir"),
    all_: bool = typer.Option(False, "--all", "-a", help="Restore the whole backed-up tree instead of a single path"),
) -> None:
    """Restore a path (or the whole tree with --all) from a backup archive."""
    settings, cfg, home = _load()

    if name != config_mod.HOME_BACKUP_NAME:
        _require_declared(cfg, name)

    repo_url = settings.repo_url(name)
    if not borg.check_repo(repo_url):
        logs.error("backup", "couldn't connect to host")
        raise typer.Exit(1)

    basedir = Path(config_mod.resolve_basedir(cfg, name, home))

    if all_:
        archive_name = archive or borg.last_archive(repo_url)
        if not archive_name:
            logs.error("backup", f"no archive found in {repo_url}")
            raise typer.Exit(1)
        backup_path = config_mod.resolve_path(cfg, name, home)

    elif archive and path:
        archive_name = archive
        backup_path = path

    else:
        mount_path = settings.borg_mount_root / name
        found = restore_mod.find_archived_path(repo_url, mount_path)
        if not found:
            logs.error("backup", "couldn't determine archive and path")
            raise typer.Exit(1)

        backup_path, candidate_archives = found
        if len(candidate_archives) == 1:
            archive_name = candidate_archives[0]
        else:
            archive_name = fzf.select_one(candidate_archives, border_label="Archive")

        if not archive_name:
            logs.error("backup", "couldn't determine archive and path")
            raise typer.Exit(1)

    try:
        restore_mod.restore_path(repo_url, archive_name, basedir, backup_path)
        logs.info("backup", f"successfully restored {backup_path} from {repo_url}::{archive_name}")
    except borg.BorgError as exc:
        logs.error("backup", str(exc))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
