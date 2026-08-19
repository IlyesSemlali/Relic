# Relic

Relic is a Borg wrapper that will help you create standard backups the smartest way possible (if you find something no so smart please create an issue, so we can work on that !)

## Features

- Exclude paths
- Exclusion patterns
- Backups Routing

## Configuration

Relic reads `~/.config/backups.yaml` (override with `$BACKUP_CONFIG_FILE`) and requires
`$BORG_REPO` to point at the root holding one Borg repo per backup:

```yaml
backups:
  documents:
    basedir: ~        # optional, defaults to ~
    path: Documents    # optional, defaults to the backup's key
    excludes:
      - "*.cache/"
excludes:
  - "*.DS_Store"
```

An implicit `home` backup (`basedir: ~`, `path: .`) always exists, backing up everything
under `$HOME` except the trees already covered by other declared backups.

`$BORG_MOUNT_PATH` (defaults to `~/Backups`) is used as the mount point for interactive
restores.

## Usage

```
relic init <name> | --all
relic create <name> | --all
relic list [<name>] [--interactive]
relic restore <name> [<archive>] [<path>] [--all]
```

## Terminology

### Backups

A backup is a configuration that will result in mutliple snapshots of the same list of paths that will be pushed to a dedicated repository

### Routing

You can configure Relic to spread backups accross multiple repositories (thus increasing the fault tolerance), or simply to back up a set of path in one place, and another in a different place.
