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


# .. utopya models register ...................................................
# TODO Add an option to register a model from a manifest file


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
    "--default-cfg",
    required=True,
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
    "--set-default",
    is_flag=True,
    default=False,
    help="If set, will mark this info bundle as the default.",
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
    default_cfg: str,
    label: str,
    set_default: bool,
    overwrite: bool,
    validate: bool,
):
    """Registers a new model"""
    Echo.progress(f"Registering model '{model_name}' (label: {label})...")
    Echo.info(f"  executable:      {executable}")
    Echo.info(f"  default config:  {default_cfg}")

    bundle_kwargs = dict(
        label=label,
        overwrite=overwrite,
        set_as_default=set_default,
        paths=dict(binary=executable, default_cfg=default_cfg)
        # TODO rename `binary` to `executable`
        # TODO pass additional paths and metadata
    )

    import utopya

    try:
        utopya.MODELS.register_model_info(
            model_name,
            exists_action=None if not validate else "validate",
            **bundle_kwargs,
        )

    except Exception as exc:
        Echo.failure("Failed registering model!", error=exc)
        sys.exit(1)

    else:
        Echo.success(f"Successully registered model {model_name}.")
