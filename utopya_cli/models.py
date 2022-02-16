"""Implements the `utopya models` subcommand tree of the CLI"""

import sys
from typing import Tuple

import click

from ._utils import Echo

models = click.Group(
    name="models",
    help="Show available models and register new ones",
)


# -- Utility commands ---------------------------------------------------------
# .. utopya models ls .........................................................


@models.command(
    name="ls",
    help="Lists registered models",
)
@click.option(
    "-l",
    "--long",
    "long_mode",
    is_flag=True,
    help="Show more detailed information.",
)
def list_models(long_mode: bool):
    import utopya

    if long_mode:
        click.echo(utopya.MODELS.info_str_detailed)
    else:
        click.echo(utopya.MODELS.info_str)


# .. utopya models rm .........................................................


@models.command(
    name="rm",
    help="Removes info bundles from individual models",
)
@click.argument("model_name")
@click.option(
    "--label",
    type=str,
    default=None,
    help="The label of the info bundle to remove from the registry entry",
)
@click.option(
    "-a",
    "--all",
    "remove_all",
    is_flag=True,
    help="If set, removes all info bundles and deletes the registry entry",
)
def remove_model_or_bundle(*, model_name: str, label: str, remove_all: bool):
    import utopya

    if not remove_all:
        if not label:
            _avail = ", ".join(utopya.MODELS[model_name].keys())
            Echo.info(f"Available bundles for model '{model_name}':  {_avail}")
            label = click.prompt("Which bundle would you like to remove?")

        Echo.info(
            f"Removing info bundle '{label}' for model '{model_name}'..."
        )
        utopya.MODELS[model_name].pop(label)
        Echo.success(
            f"Info bundle labelled '{label}' removed "
            f"from registry entry of model '{model_name}'."
        )

    else:
        Echo.info(f"Removing registry entry for model '{model_name}'...")
        if not click.confirm("Are you sure?"):
            Echo.info("Not removing anything.")
            sys.exit(0)

        utopya.MODELS.remove_entry(model_name)
        Echo.success(f"Registry entry for model '{model_name}' removed.")


# .. utopya models edit .......................................................


@models.command(help="Edit the model registry entry")
@click.argument("model_name")
def edit(*, model_name: str):
    """Edits the model registry entry of the given model"""
    Echo.info(f"Opening '{model_name}' model's registry file for editing ...")
    import utopya

    Echo.warning("Take care not to corrupt the file!")
    if not click.confirm("Open file for editing?"):
        Echo.info("Not opening.")
        sys.exit(0)

    try:
        click.edit(filename=utopya.MODELS[model_name].registry_file_path)

    except Exception as exc:
        Echo.error("Editing model registry file failed!", error=exc)
        sys.exit(1)

    Echo.success(f"Successully edited registry file of '{model_name}' model.")


# .. utopya models set-default ................................................


@models.command(help="Sets the default info bundle to use for a model")
@click.argument("model_name")
@click.argument("label")
def set_default(*, model_name: str, label: str):
    """Sets the default info bundle to use for a certain model"""
    Echo.info(
        f"Setting the info bundle labelled '{label}' as the default "
        f"for '{model_name}' ..."
    )

    import utopya

    utopya.MODELS[model_name].default_label = label
    Echo.success(f"Successully set default label for model '{model_name}'.")


# -- Registration -------------------------------------------------------------
# .. utopya models register ...................................................
# TODO Add an option to register a model from some kind of "manifest file"
# TODO Add batch registration, allowing to register many models per call

register = click.Group(
    name="register",
    help="Register new models, either individually or in a batch.",
)
models.add_command(register)

# .. utopya models register single ............................................


@register.command(
    name="single",
    help="Register a single new model or update an existing one.",
)
@click.argument("model_name")
@click.option(
    "-e",
    "--executable",
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the model executable.",
)
@click.option(
    "--source-dir",
    default=None,
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, resolve_path=True
    ),
    help=(
        "Path to the directory that contains the model's source files; "
        "this can be used to automatically extract model-related information "
        "like the default model configuration or plot-related configurations."
    ),
)
@click.option(
    "--default-cfg",
    default=None,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the model's default configuration file.",
)
@click.option(
    "--label",
    type=click.STRING,
    default="set_via_cli",
    help=(
        "Label to identify the info bundle with; if not given, will use a "
        "default value. This allows registering multiple versions of a model "
        "under the same name."
    ),
)
@click.option(
    "--exists-action",
    default="validate",
    type=click.Choice(("skip", "raise", "validate", "overwrite")),
    help=(
        "Which action to take upon an existing bundle with the same label. "
        "By default, validates the to-be-added information against a "
        "potentially existing bundle."
    ),
)
def register_single(
    *,
    model_name: str,
    executable: str,
    source_dir: str,
    default_cfg: str,
    label: str,
    exists_action: str,
):
    """Registers a new model"""
    Echo.info(f"Registering model '{model_name}' (label: {label})...")
    Echo.remark(f"  executable:        {executable}")
    Echo.remark(f"  source directory:  {source_dir}")
    Echo.remark(f"  default config:    {default_cfg}")

    bundle_kwargs = dict(
        label=label,
        paths=dict(
            executable=executable,
            default_cfg=default_cfg,
            source_dir=source_dir,
        ),
    )

    import utopya

    try:
        utopya.MODELS.register_model_info(
            model_name,
            exists_action=exists_action,
            **bundle_kwargs,
        )

    except Exception as exc:
        Echo.error("Failed registering model!", error=exc)
        sys.exit(1)

    else:
        Echo.success(f"Successully registered model {model_name}.")


# .. utopya models register from-manifest .....................................


@register.command(
    name="from-manifest",
    help=(
        "Register one or many models using manifest files: YAML files that "
        "contains all relevant model information; see documentation for a "
        "valid manifest file format."
    ),
)
@click.argument(
    "manifest_files",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "--model-name",
    "custom_model_name",
    type=click.STRING,
    default=None,
    help=(
        "If only a single manifest file is given, this option can be used to "
        "specify the model name, ignoring the one given in the manifest file."
    ),
)
@click.option(
    "--label",
    "custom_label",
    type=click.STRING,
    default=None,
    help=(
        "If given, this label will be used instead of the one given in the "
        "manifest file(s). "
        "If no custom label is given and the manifest file does not define "
        "one either, the default will be 'from_manifest_file'."
    ),
)
@click.option(
    "--exists-action",
    default="validate",
    type=click.Choice(("skip", "raise", "validate", "overwrite")),
    help=(
        "Which action to take upon an existing bundle with the same label. "
        "By default, validates the to-be-added information with a potentially "
        "existing "
    ),
)
def register_from_manifest(
    *,
    manifest_files: Tuple[str],
    custom_model_name: str,
    custom_label: str,
    exists_action: str,
):
    """Registers one or many models using manifest files"""
    if custom_model_name and len(manifest_files) != 1:
        Echo.error(
            "A model name can only be specified if only a single "
            f"manifest file is given (got {len(manifest_files)}). "
        )
        Echo.info(
            "Either remove the `--model-name` argument or make sure to pass "
            "only a single manifest file."
        )
        sys.exit(1)

    # All checks done, let's go
    Echo.info(
        f"Parsing information from {len(manifest_files)} manifest file(s) ..."
    )
    import utopya

    for manifest_file in manifest_files:
        bundle_kwargs = utopya.tools.load_yml(manifest_file)

        # Handle custom model name or label
        # TODO Communicate
        model_name = bundle_kwargs.pop("model_name")
        if custom_model_name:
            model_name = custom_model_name

        label = bundle_kwargs.pop("label", "from_manifest_file")
        if custom_label:
            label = custom_label

        # Store manifest file in paths dict
        utopya.tools.add_item(
            manifest_file,
            add_to=bundle_kwargs,
            key_path=("paths", "model_info"),
        )

        # Can now register
        utopya.MODELS.register_model_info(
            model_name,
            label=label,
            exists_action=exists_action,
            **bundle_kwargs,
        )

        Echo.progress(
            f"Registered model information for '{model_name}', "
            f"labelled '{label}':"
        )
        Echo.remark(utopya.tools.pformat(bundle_kwargs) + "\n")

    Echo.success(f"Model information registered successully.")


# .. utopya models register batch .............................................
# TODO
