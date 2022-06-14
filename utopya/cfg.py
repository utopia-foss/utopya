"""Module that coordinates utopya's persistent config directory"""

import logging
import os

from ._yaml import load_yml, write_yml

log = logging.getLogger(__name__)

# Some globally relevant variables --------------------------------------------

UTOPYA_CFG_DIR = os.path.expanduser("~/.config/utopya")
"""Path to the persistent utopya configuration directory"""

UTOPYA_CFG_FILE_NAMES = dict(
    user="user_cfg.yml",
    utopya="utopya_cfg.yml",
    batch="batch_cfg.yml",
)
"""Names and paths of valid configuration entries"""

UTOPYA_CFG_FILE_PATHS = {
    k: os.path.join(UTOPYA_CFG_DIR, fname)
    for k, fname in UTOPYA_CFG_FILE_NAMES.items()
}
"""Absolute configuration file paths"""

UTOPYA_CFG_SUBDIR_NAMES = dict(
    models="models",
    projects="projects",
)
"""Names and paths of valid configuration subdirectories"""

UTOPYA_CFG_SUBDIRS = {
    k: os.path.join(UTOPYA_CFG_DIR, dirname)
    for k, dirname in UTOPYA_CFG_SUBDIR_NAMES.items()
}
"""Absolute configuration file paths"""
"""Names and paths of valid configuration directories"""

PROJECT_INFO_FILE_SEARCH_PATHS = (
    ".utopya_project.yml",
    ".utopya-project.yml",
)
"""Potential names of project info files, relative to base directory"""


# -----------------------------------------------------------------------------


def get_cfg_path(cfg_name: str) -> str:
    """Returns the absolute path to the specified configuration file"""
    try:
        return UTOPYA_CFG_FILE_PATHS[cfg_name]

    except KeyError as err:
        _avail = ", ".join(UTOPYA_CFG_FILE_NAMES.keys())
        raise ValueError(
            f"No configuration entry '{cfg_name}' available! "
            f"Possible keys: {_avail}"
        ) from err


def load_from_cfg_dir(cfg_name: str) -> dict:
    """Load a configuration file; returns empty dict if no file exists.

    Args:
        cfg_name (str): The name of the configuration to read

    Returns:
        dict: The configuration as read from the config directory; if no file
            is available, will return an empty dict.
    """
    cfg_fpath = get_cfg_path(cfg_name)
    try:
        d = load_yml(cfg_fpath)

    except FileNotFoundError:
        log.debug(
            "No '%s' configuration file exists at %s ! Returning empty.",
            cfg_name,
            cfg_fpath,
        )
        return dict()

    # If the yaml object is None for whatever reason, return an empty dict
    if d is None:
        return dict()
    return d


def write_to_cfg_dir(cfg_name: str, obj: dict):
    """Writes a YAML represetation of the given object to the configuration
    directory. Always overwrites a possibly existing file.

    Args:
        cfg_name (str): The configuration name
        obj (dict): The yaml-representable object that is to be written;
            usually a dict.
    """
    write_yml(obj, path=get_cfg_path(cfg_name))
