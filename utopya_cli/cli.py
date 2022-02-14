"""Defines the utopya CLI"""

import click

from ._utils import *


@click.group()
def utopya():
    pass


# -- models subcommands -------------------------------------------------------


@utopya.group(help="Show available models and register new ones")
def models():
    pass


# .............................................................................


@models.command(
    name="ls",
    help="Lists registered models",
)
def list_models():
    click.echo("Registered models:\n  ...")


# .............................................................................


@models.command(
    name="register",
    help="Register a new model or validate an existing one",
)
@click.argument("model_name")
@click.option(
    "--executable",
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "--default-cfg",
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "--validate/--no-validate",
    is_flag=True,
    default=True,
    help=(
        "Whether to validate the given information against a potentially "
        "existing info bundle with the same label"
    ),
)
@click.option(
    "--label",
    type=click.STRING,
    default=None,
    help="Label to attach to the info bundle",
)
def register_model(
    *,
    model_name: str,
    executable: str,
    default_cfg: str,
    label: str,
    validate: bool,
):
    """Registers a new model"""
    Echo.progress(f"Registering model '{model_name}' ...")
    Echo.info(f"  executable:      {executable}")
    Echo.info(f"  default config:  {default_cfg}")

    bundle_kwargs = dict(
        label=label, paths=dict(binary=executable, default_cfg=default_cfg)
    )
    # TODO rename `binary` to `executable`

    import utopya

    try:
        utopya.MODELS.register_model_info(
            model_name,
            exists_action=None if not validate else "validate",
            **bundle_kwargs,
        )

    except Exception as exc:
        Echo.failure("Failed registering model!", error=exc)

    else:
        Echo.success(f"Successully registered model {model_name}.")


# -- projects subcommands -----------------------------------------------------


@utopya.group(help="Manage projects")
def projects():
    pass


# -- run & eval subcommands ---------------------------------------------------

# TODO ...
