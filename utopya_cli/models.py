"""Implements the `utopya models` subcommand tree of the CLI"""

import sys

import click

from ._utils import Echo


@click.group(help="Show available models and register new ones")
def models():
    pass


# .. utopya models ls .........................................................


@models.command(
    name="ls",
    help="Lists registered models",
)
@click.option(
    "-l/--long", is_flag=True, help="Show more detailed information."
)
def list_models(l: bool):
    import utopya

    if l:
        click.echo(utopya.MODELS.info_str_detailed)
    else:
        click.echo(utopya.MODELS.info_str)


# .. utopya models rm .........................................................


@models.command(
    name="rm",
    help="Removes individual info bundles or whole model registry entries",
)
@click.argument("model_name")
@click.option("--all")
def remove_model_or_bundle():
    Echo.progress("Removing ...")
    raise NotImplementedError("removing models or bundles")


# .. utopya models edit .......................................................


@models.command(help="Edit the model registry entry")
@click.argument("model_name")
def edit(*, model_name: str):
    """Edits the model registry entry of the given model"""
    Echo.info(f"Opening '{model_name}' model's registry file for editing ...")
    Echo.warning("Take care not to corrupt the file!")
    if not click.confirm("Continue?"):
        Echo.info("Not continuing.")
        sys.exit(0)

    import utopya

    try:
        click.edit(filename=utopya.MODELS[model_name].registry_file_path)

    except Exception as exc:
        Echo.failure("Editing model registry file failed!", error=exc)
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


# .. utopya models register ...................................................
# TODO Add an option to register a model from some kind of "manifest file"
# TODO Add batch registration, allowing to register many models per call


@models.command(
    help="Register a new model or update an existing one",
)
@click.argument("model_name")
@click.option(
    "--executable",
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the model executable",
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
    help="Path to the model's default configuration file",
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
    "--overwrite",
    is_flag=True,
    default=False,
    help="If set, will allow overwriting an info bundle with the same label",
)
@click.option(
    "--validate/--no-validate",
    is_flag=True,
    default=True,
    help=(
        "Whether to validate the given information against a potentially "
        "existing info bundle with the same label. By default, this is "
        "enabled, making it simpler to validate that an info bundle is part "
        "of the model registry entry."
    ),
)
def register(
    *,
    model_name: str,
    executable: str,
    source_dir: str,
    default_cfg: str,
    label: str,
    set_default: bool,
    overwrite: bool,
    validate: bool,
):
    """Registers a new model"""
    Echo.info(f"Registering model '{model_name}' (label: {label})...")
    Echo.remark(f"  executable:        {executable}")
    Echo.remark(f"  source directory:  {source_dir}")
    Echo.remark(f"  default config:    {default_cfg}")

    bundle_kwargs = dict(
        label=label,
        overwrite=overwrite,
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
            exists_action=None if not validate else "validate",
            **bundle_kwargs,
        )

    except Exception as exc:
        Echo.error("Failed registering model!", error=exc)
        sys.exit(1)

    else:
        Echo.success(f"Successully registered model {model_name}.")
