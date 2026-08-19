# Relic

A Borg wrapper for creating standardized backups with less ceremony.

## Installation

```bash
uv tool install .                                                 # from a local clone
uv tool install --editable .                                      # while developing
uv tool install git+ssh://git@github.com/IlyesSemlali/Relic.git   # from any machine
```

First time using `uv tool install`? Run `uv tool update-shell` once to put it on your `PATH`.

## Configuration

Relic reads `~/.config/backups.yaml` (override with `$BACKUP_CONFIG_FILE`). `$BORG_REPO`
must point at where repos live — one per backup, at `$BORG_REPO/<name>`.

```yaml
backups:
  documents:
    basedir: ~          # default: ~
    path: Documents      # default: the backup's key
    excludes:
      - "*.cache/"
excludes:
  - "*.DS_Store"          # applies to every backup
```

An implicit `home` backup (`~`, `.`) always exists, covering whatever isn't claimed by
another declared backup. `$BORG_MOUNT_PATH` (default `~/Backups`) is where repos get
mounted for interactive restores.

## Usage

```
relic init    <name> | --all
relic create  <name> | --all
relic list    [<name>] [--interactive]
relic restore <name> [<archive>] [<path>] [--all]
```

## Glossary

- **Backup** — a name, a `basedir`/`path` to back up, and optional `excludes`.
- **Repository** — where a backup's archives live: `$BORG_REPO/<name>`.
- **Archive** — one snapshot, named `<hostname>-<date>-<seconds since midnight>`.
- **Excludes** — patterns skipped when backing up: global ones, the backup's own, and every
  other backup's path (so `home` doesn't re-back-up what a specific backup already covers).
