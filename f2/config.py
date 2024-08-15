from pathlib import Path

from platformdirs import user_config_dir


def _config_root() -> Path:
    root_dir = Path(user_config_dir("f2commander"))
    if not root_dir.exists():
        root_dir.mkdir()
    return root_dir


def user_has_accepted_license():
    """Whether user has accepted the license or not yet"""
    return (_config_root() / "user_has_accepted_license").is_file()


def set_user_has_accepted_license():
    (_config_root() / "user_has_accepted_license").touch()
