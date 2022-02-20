"""Implements the `utopya config` subcommand tree of the CLI"""

import sys
from typing import Tuple

import click

from ._utils import Echo


@click.command(
    help=(
        "Set or read utopya configuration entries.\n"
        "\n"
        "Configuration entries are grouped into multiple categories. "
        "Within those categories, individual entries can be set using the "
        "KV_PAIRS argument, expecting key=value pairs. "
        "The key may be a dot-separated string of keys for dict traversal, "
        "like `foo.bar.baz`. "
        "To delete entries, set the value to `DEL`. For example:\n"
        "\n"
        "    utopya config user --get --set foo.bar=spam bar.baz=DEL\n"
        "\n"
        "This will set the user configuration entry `foo.bar`, delete the "
        "entry `bar.baz`, and then retrieve the new configuration. "
        "To include spaces, put the whole key-value pair into quotes "
        "('key=value'); everything after the `=` is parsed as a string "
        "anyway.\n"
        ""
        "\n"
        "If the configuration file does not exist, it will be created."
    )
)
@click.argument(
    "cfg_name",
    type=click.Choice(
        (
            "user",
            "utopya",
            "projects",
            "batch",
            "external_module_paths",
            "plot_module_paths",
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
    "--get",
    "get_entry",
    is_flag=True,
    help=(
        "Retrieve all entries from the specified configuration. This is "
        "always invoked *after* the --set command was executed (if given)."
    ),
)
@click.option(
    "--set",
    "set_entry",
    is_flag=True,
    help=("Set entries in the specified configuration."),
)
@click.option(
    "--accept-yaml/--no-yaml",
    "allow_yaml",
    is_flag=True,
    default=True,
    help=(
        "Whether to accept YAML syntax for parsing values (default: true). "
        "This allows specifying list- or dict-like values. In case this "
        "results in a dict, the object at the specified key will be "
        "recursively updated"
    ),
)
@click.option(
    "--deploy-default",
    is_flag=True,
    help=(
        "Deploy an empty or default configuration file to ~/.config/utopya, "
        "if it does not already exist. "
        "For the user configuration, deploys a file (with all entries "
        "disabled) to ~/.config/utopya/user_cfg.yml, "
        "prompting for confirmation if a file already exists at that location."
    ),
)
def config(
    *,
    cfg_name: str,
    kv_pairs: Tuple[str],
    get_entry: bool,
    set_entry: bool,
    deploy_default: bool,
    allow_yaml: bool,
):
    """Sets and reads configuration entries"""
    from ._config import deploy_user_cfg, set_entries_from_kv_pairs

    # -- Deploying default files
    if deploy_default:
        if cfg_name != "user":
            # TODO
            raise NotImplementedError("Can only deploy user config for now.")

        deploy_user_cfg()
        sys.exit()

    if not get_entry and not set_entry:
        Echo.error("Missing --set and/or --get argument.")
        sys.exit(1)

    # -- Reading and writing entries
    from utopya.cfg import get_cfg_path, load_from_cfg_dir, write_to_cfg_dir
    from utopya.tools import pformat

    cfg = load_from_cfg_dir(cfg_name)  # empty dict if file is missing

    if set_entry:
        Echo.note(
            f"Setting '{cfg_name}' config values from key-value pairs ..."
        )
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

    if get_entry:
        Echo.note(
            "Reading '%s' config (%s) ...", cfg_name, get_cfg_path(cfg_name)
        )
        Echo.info(
            "\n--- {} Configuration ---\n\n{}".format(
                cfg_name.replace("_", " ").title(), pformat(cfg)
            )
        )
