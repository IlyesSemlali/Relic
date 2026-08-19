"""Thin wrapper around the `fzf` binary for interactive selection."""

import subprocess


def select(choices: list[str], *, multi: bool = False, border_label: str | None = None) -> list[str]:
    if not choices:
        return []

    args = ["fzf"]
    if multi:
        args.append("-m")
    if border_label:
        args.append(f"--border-label={border_label}")

    result = subprocess.run(args, input="\n".join(choices), capture_output=True, text=True)
    # fzf exits 130 on ctrl-c/esc and 1 when no match/nothing selected.
    if result.returncode not in (0, 1, 130):
        return []

    output = result.stdout.strip("\n")
    return output.split("\n") if output else []


def select_one(choices: list[str], *, border_label: str | None = None) -> str | None:
    selected = select(choices, border_label=border_label)
    return selected[0] if selected else None
