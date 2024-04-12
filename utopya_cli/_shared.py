"""Defines arguments that are shared across various parts of the CLI"""

import glob
import os
from typing import Dict, List, Union

import click

# -----------------------------------------------------------------------------
# Variables
#
# NOTE Some of these are duplicated rather than imported to save on utopya
#      import time...

UTOPYA_CFG_DIR: str = os.path.expanduser("~/.config/utopya")
"""Directory where utopya stores its metadata"""

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

DEFAULT_RUN_DIR_SEARCH_PATHS: str = [
    "~/utopya_output",
    "~/utopia_output",
]
"""Default directory paths to search for model run directories in.

This can be overwritten via the utopya package configuration file and its
entry ``cli.run_dir_search_paths``.
"""


# .............................................................................

INTERACTIVE_MODE_PROHIBITED_ARGS = (
    "run_cfg",
    "run_dir",
    "label",
    "set_params",
    "cluster_mode",
    "show_data_tree",
    "use_data_tree_cache",
    "load_parallel",
)
"""Argument names that may NOT be given in the interactive plotting prompt"""


# -----------------------------------------------------------------------------
# Shell completion


def complete_from_cfg_dir(
    ctx, param, incomplete: str, *, dirpath: str, glob_str: str = "*.yml"
) -> List[str]:
    """Reads the filenames from a directory and uses that to return a list of
    strings that offer

    This is meant for completing queries where a name is required that has an
    equivalent representation as a registry file in a utopya config directory.
    """
    return sorted(
        [
            os.path.splitext(os.path.basename(f))[0]
            for f in glob.glob(os.path.join(dirpath, incomplete + glob_str))
        ],
        key=str.casefold,
    )


def complete_model_names(*args) -> List[str]:
    """Completes model names using :py:func:`.complete_from_cfg_dir`."""
    return complete_from_cfg_dir(*args, dirpath=UTOPYA_CFG_SUBDIRS["models"])


def complete_project_names(*args) -> List[str]:
    """Completes project names using :py:func:`.complete_from_cfg_dir`."""
    return complete_from_cfg_dir(*args, dirpath=UTOPYA_CFG_SUBDIRS["projects"])


def complete_run_dirs(
    ctx, param, incomplete: str, *, extra_search_dirs: list = []
) -> List[str]:
    """Completes run directories for the selected model name.

    As the run directory is determined via the run configuration, there is no
    certainty on the location of run directories. Instead, the canonical
    locations where the simulation output is stored forms the basis for the
    completion.
    The search directories can be configured in the utopya package config file
    using the ``cli.run_dir_search_paths`` key:

    .. code-block:: yaml

        # ~/.config/utopya/utopya_cfg.yml
        ---
        cli:
          run_dir_search_paths:
            - ~/utopya_output
            - ~/utopia_output
            # ... can add more here ...

    .. todo::

        Auto-complete local paths as well, starting from CWD.
    """
    from dantro.tools import load_yml

    # Need the model name
    model_name = ctx.params["model_name"]

    # Get search directories from config and assemble model output directories
    cli_cfg = {}
    if os.path.exists(UTOPYA_CFG_FILE_PATHS["utopya"]):
        cli_cfg = load_yml(UTOPYA_CFG_FILE_PATHS["utopya"]).get("cli", {})

    search_dirs = cli_cfg.get(
        "run_dir_search_paths", DEFAULT_RUN_DIR_SEARCH_PATHS
    )
    search_dirs += extra_search_dirs
    model_out_dirs = [
        os.path.join(os.path.expanduser(d), model_name) for d in search_dirs
    ]

    # Aggregate candidate directory names, then sort and filter them
    candidates = []
    for model_out_dir in model_out_dirs:
        if not os.path.isdir(model_out_dir):
            continue

        candidates += [
            os.path.basename(p)
            for p in glob.glob(os.path.join(model_out_dir, "*"))
            if os.path.isdir(p)
        ]

    # TODO Fall back to auto-completion of local paths, if possible

    return [
        p for p in reversed(sorted(candidates)) if p.startswith(incomplete)
    ]


# -----------------------------------------------------------------------------
# Shared options


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


def default_none(ctx, _, value) -> Union[None, tuple]:
    """For use in ``multiple=True`` with ``nargs=-1`` where None is desired
    for a default value instead of an empty tuple.
    Pass this to the ``callback`` argument of an argument or an option.
    """
    if len(value) == 0:
        return None
    return value


# .............................................................................

OPTIONS = dict()

# -- Model selection
OPTIONS["label"] = (
    click.option(
        "--label",
        default=None,
        help=(
            "For model names that have multiple info bundles registered, a "
            "label is needed to unambiguously select the desired one. "
            "Alternatively, use the ``utopya models set-default`` CLI command "
            "to set a default label for a model."
        ),
    ),
)

OPTIONS["model_selection"] = (
    click.option(
        "--cfg-set",
        "--cs",
        default=None,
        help=(
            "If the chosen model provides configuration sets, use the config "
            "files from the chosen set for the run and plots config. "
            "Note that the specific arguments still take precedence over the "
            "values from the config sets; to use default paths, "
            "specify empty strings (``''``) for those arguments."
        ),
    ),
) + OPTIONS["label"]

# -- Universal flags
OPTIONS["debug_flag"] = (
    click.option(
        "-d",
        "--debug",
        count=True,
        help=(
            "The debug level."
            # TODO Expand
        ),
    ),
)
OPTIONS["cluster_mode"] = (
    click.option(
        "--cluster-mode",
        flag_value=True,
        default=None,
        help="Enables cluster mode.",
    ),
)
OPTIONS["num_workers"] = (
    click.option(
        "-W",
        "--num-workers",
        default=None,
        type=click.IntRange(min=-os.cpu_count() + 1, max=+os.cpu_count()),
        help=(
            "Shortcut for meta-config entry ``worker_manager.num_workers``, "
            "which sets the number of worker processes. "
            "Can be an integer; if negative, will deduce the number from the "
            "number of available CPUs."
        ),
    ),
)

# -- Data loading options
OPTIONS["load"] = (
    click.option(
        "-P",
        "--load-parallel",
        flag_value=True,
        default=None,
        help=("If given, will force loading data in parallel."),
    ),
    click.option(
        "--use-data-tree-cache",
        "--tc",
        flag_value=True,
        default=None,
        help=(
            "If set, uses tree file caching: If no cache file exists, creates "
            "one after loading all data; if a tree file already exists, uses "
            "that to restore the data tree. This may bring a speed-up if the "
            "creation of the data tree takes a long time."
        ),
    ),
    click.option(
        "--show-data-tree",
        type=click.Choice(("full", "condensed", "none")),
        default="condensed",
        show_default=True,
        help="Controls which kind of data tree should be shown after loading.",
    ),
)


# -- Evaluation options
OPTIONS["eval"] = (
    click.option(
        "--plots-cfg",
        default=None,
        type=click.Path(exists=True, dir_okay=False, resolve_path=True),
        help=(
            "If given, uses the plots configuration file found at this path "
            "instead of the defaults for the model."
        ),
    ),
    click.option(
        "-u",
        "--update-plots-cfg",
        multiple=True,
        callback=default_none,
        help=(
            "Sets entries in the selected plots config. "
            "Example: ``-u my_plot.some_param=42`` sets the ``some_param`` "
            "entry in the plot configuration named ``my_plot``. "
            "Repeat the ``-u`` option to set multiple values."
        ),
    ),
    click.option(
        "--plot-only",
        "--po",
        "plot_only",
        multiple=True,
        callback=default_none,
        help=(
            "If given, will plot only those entries of the plot configuration "
            "that match the names given here. This can also be used to "
            "activate plots that are disabled in the specified plot "
            "configuration. Note that simple name globbing is supported, but "
            "the argument needs to be put into quotes to not conflict with "
            "the globbing done by the shell. "
            "Repeat the ``--po`` option to denote multiple ``plot_only`` "
            "arguments."
        ),
    ),
    click.option(
        "-i",
        "--interactive",
        flag_value=True,
        help=(
            "If set, the CLI will not exit after plotting finished, but allow "
            "to continue plotting in an interactive session. "
            "This option is useful for creating multiple plots in an "
            "iterative fashion, especially if data loading time is large. "
            "Note that all Multiverse-related configuration options can not "
            "be changed during the session and have to be set beforehand."
        ),
    ),
    click.option(
        "-R",
        "--reveal-output",
        flag_value=True,
        help="If set, opens the output directory after plotting finished.",
    ),
)
