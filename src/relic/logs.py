"""Small colored logging helpers, built on top of rich."""

from rich.console import Console

_out = Console()
_err = Console(stderr=True)


def info(scope: str, message: str) -> None:
    _out.print(f"[magenta][{scope}][/magenta][bold] - [white]{message}[/white][/bold]")


def error(scope: str, message: str) -> None:
    _err.print(f"[magenta][{scope}][/magenta][bold] - [red]{message}[/red][/bold]")
