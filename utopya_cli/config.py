"""Implements the `utopya config` subcommand tree of the CLI"""

import os
import sys
from typing import Tuple

import click

from ._utils import Echo, set_entries_from_kv_pairs


@click.command(
    help=(
        "Read and modify the utopya configuration.\n"
        "\n"
        "Configuration entries are grouped into multiple categories, which "
        "each category corresponding to a YAML file within the utopya "
        "config directory."
        "The ``utopya config`` command allows revealing the configuration "
        "file, opening it in an editor, or setting values directly via the "
        "command line interface.\n"
        "\n"
        "Entries within these configuration files can be set using the "
        "``--set`` and ``KV_PAIRS`` argument, expecting ``key=value`` pairs. "
        "The key may be a dot-separated string of keys for dict traversal, "
        "like ``foo.bar.baz``. "
        "To delete entries, set the value to ``DEL``. For example:\n"
        "\n"
        "    ``utopya config user --get --set foo.bar=spam bar.baz=DEL``\n"
        "\n"
        "This will set the user configuration entry ``foo.bar``, delete the "
        "entry ``bar.baz``, and then retrieve the new configuration. "
        "To include spaces, put the whole key-value pair into quotes "
        "(``'key=value'``); everything after the ``=`` is parsed as a string "
        "anyway."
        "If the configuration file does not exist, it will be created."
    )
)
@click.argument(
    "cfg_name",
    type=click.Choice(
        (
            "user",
            "utopya",
            "batch",
        )  # TODO load these from utopya if import time allows
    ),
)
@click.argument(
    "kv_pairs",
    default=None,
    nargs=-1,
    type=str,
)
@click.option(
    "-R",
    "--reveal",
    is_flag=True,
    help=(
        "Reveals the location of the configuration files, then exits. "
        "If the config file does not yet exist, deploys an empty file at "
        "the expected location."
    ),
)
@click.option(
    "--set",
    "set_entry",
    is_flag=True,
    help=(
        "Set entries in the specified configuration, using the KV_PAIRS. "
        "This option is mutually exclusive with the ``--edit`` option."
    ),
)
@click.option(
    "--edit",
    is_flag=True,
    help=(
        "Open the selected config file in an editor. "
        "This option is mutually exclusive with the ``--set`` option."
    ),
)
@click.option(
    "--get",
    "get_entry",
    is_flag=True,
    help=(
        "Retrieve all entries from the specified configuration. This is "
        "always invoked *after* the ``--set`` command was executed (if given)."
    ),
)
@click.option(
    "--accept-yaml/--no-yaml",
    "allow_yaml",
    is_flag=True,
    default=True,
    help=(
        "Whether to accept YAML syntax for parsing the values in ``KV_PAIRS`` "
        "(default: ``true``). "
        "This allows specifying list- or dict-like values. In case this "
        "results in a dict, the object at the specified key will be "
        "recursively updated"
    ),
)
def config(
    *,
    cfg_name: str,
    kv_pairs: Tuple[str],
    reveal: bool,
    set_entry: bool,
    edit: bool,
    get_entry: bool,
    allow_yaml: bool,
):
    """Sets and reads configuration entries"""

    if not reveal and not get_entry and not (set_entry or edit):
        Echo.error(
            "Need at least one of the options "
            "--get, --set, --edit, or --reveal!"
        )
        Echo.help(exit=1)

    elif set_entry and edit:
        Echo.error("Can only pass one of --set or --edit, not both!")
        Echo.help(exit=1)

    elif set_entry and not kv_pairs:
        Echo.error("Got --set option but the KV_PAIRS argument is missing!")
        Echo.help(exit=1)

    from utopya.cfg import get_cfg_path, load_from_cfg_dir, write_to_cfg_dir

    # -- Reveal
    # NOTE The launch command is only invoked if not in a test context
    if reveal:
        cfg_fpath = get_cfg_path(cfg_name)
        Echo.info(f"Revealing '{cfg_name}' config file ...")
        Echo.remark(f"  Location:  {cfg_fpath}")

        if not os.path.exists(cfg_fpath):
            write_to_cfg_dir(cfg_name, {})

        rv = 0
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            rv = click.launch(cfg_fpath, locate=True)
        sys.exit(rv)

    # -- Writing/editing entries
    if set_entry:
        Echo.note(
            f"Setting '{cfg_name}' config values from key-value pairs ..."
        )
        cfg = load_from_cfg_dir(cfg_name)  # empty dict if file is missing
        set_entries_from_kv_pairs(
            *kv_pairs, add_to=cfg, _log=Echo, allow_yaml=allow_yaml
        )
        write_to_cfg_dir(cfg_name, cfg)
        Echo.progress(
            "Set %d entr%s in '%s' configuration.\n",
            len(kv_pairs),
            "ies" if len(kv_pairs) != 1 else "y",
            cfg_name,
        )

    elif edit:
        Echo.note(f"Opening editor with '{cfg_name}' config file ...")
        try:
            click.edit(filename=get_cfg_path(cfg_name), extension=".yml")

        except Exception as exc:
            Echo.error(f"Editing config file '{cfg_name}' failed!", error=exc)
            sys.exit(1)

        else:
            Echo.success(f"Config file '{cfg_name}' edited successfully.")

    # -- Reading entries
    if get_entry:
        from utopya.tools import pformat

        Echo.note(
            "Reading '%s' config (%s) ...", cfg_name, get_cfg_path(cfg_name)
        )
        cfg = load_from_cfg_dir(cfg_name)
        Echo.info(
            "\n--- {} Configuration ---\n\n{}".format(
                cfg_name.replace("_", " ").title(), pformat(cfg)
            )
        )
