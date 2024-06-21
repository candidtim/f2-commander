import os
import shlex
import shutil
from typing import List

# TODO: better lookup (cross-platform) and user configuration


def editor() -> List[str] | None:
    """Try to find an editor. Returns a command as a splitted list of arguments,
    or None if no viable alternative is found. Prefers $EDITOR when possible."""

    editor = os.getenv("EDITOR")
    if editor:
        parts = shlex.split(editor)
        if shutil.which(parts[0]):
            return parts

    for cmd in ("vi", "nano", "edit"):
        if shutil.which(cmd):
            return [cmd]

    return None


def viewer(or_editor: bool = True) -> List[str] | None:
    """Try to find a viewer. Returns a command as a splitted list of arguments,
    or None if no viable alternative is found. Use editor if no viewer is found."""

    for cmd in ("less", "more"):
        if shutil.which(cmd):
            return [cmd]

    return editor() if or_editor else None


def shell() -> List[str] | None:
    """Try to find a shell executable. Returns a command as a splitted list of
    arguments, or None if no viable alternative is found."""

    for cmd in ("zsh", "fish", "bash", "sh", "powershell.ext", "cmd.exe"):
        if shutil.which(cmd):
            return [cmd]

    return None
