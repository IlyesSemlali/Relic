# Relic

Relic is a Borg wrapper that will help you create standard backups the smartest way possible (if you find something no so smart please create an issue, so we can work on that !)

## Features

- Exclude paths
- Exclusion patterns
- Backups Routing

## Configuration

## Terminology

### Backups

A backup is a configuration that will result in mutliple snapshots of the same list of paths that will be pushed to a dedicated repository

### Routing

You can configure Relic to spread backups accross multiple repositories (thus increasing the fault tolerance), or simply to back up a set of path in one place, and another in a different place.
