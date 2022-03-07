"""Implements the `utopya models` subcommand tree of the CLI"""

import sys
from typing import Tuple

import click

from ._shared import OPTIONS, add_options
from ._utils import Echo

models = click.Group(
    name="models",
    help="Show available models and register new ones.",
)


# -- Locally relevant utility functions ---------------------------------------


def _evaluate_fstr_for_list(*, fstr: str, model_names: str, sep: str) -> str:
    """Evaluates a format string using the information from a list of model
    names.

    Args:
        fstr (str): The format string to evaluate for each model name
        model_names (str): A splittable string of model names
        sep (str): The separator used to split the ``model_names`` string
    """
    return sep.join(fstr.format(model_name=m) for m in model_names.split(sep))


# -- Utility commands ---------------------------------------------------------
# .. utopya models ls .........................................................


@models.command(
    name="ls",
    help="Lists all registered models",
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
@add_options(OPTIONS["label"])
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
        click.edit(
            filename=utopya.MODELS[model_name].registry_file_path,
            extension=".yml",
        )

    except Exception as exc:
        Echo.error("Editing model registry file failed!", error=exc)
        sys.exit(1)

    Echo.success(f"Successfully edited registry file of '{model_name}' model.")


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


# .. utopya models info .......................................................
# TODO Expand to show more information


@models.command(
    help=(
        "Shows model information.\n"
        "\n"
        "Currently, this only shows the available configuration set names."
    )
)
@click.argument("model_name")
@add_options(OPTIONS["label"])
def info(*, model_name: str, label: str):
    import utopya
    from utopya.tools import make_columns

    _log = utopya._getLogger("utopya_cli")

    model = utopya.Model(name=model_name, bundle_label=label)

    _log.info("Fetching available config sets ...")
    cfg_sets = model.default_config_sets
    if cfg_sets:
        _log.note(
            "Have %d config sets available for model '%s':\n%s",
            len(cfg_sets),
            model.name,
            make_columns(cfg_sets),
        )

    else:
        _log.note(
            "There are no config sets available for model '%s'.", model.name
        )

    _log.remark(
        "To add config sets, create subdirectories containing run.yml and/or "
        "eval.yml files in one of the search directories listed above.",
    )


# .. utopya models copy .......................................................
# TODO Implement


@models.command(
    help=("Copies a model implementation.\n\nThis is not implemented yet!")
)
@click.argument("model_name")
@add_options(OPTIONS["label"])
@click.option(
    "--new-name",
    prompt=True,
    help="Name of the new model. If not given, will prompt for it.",
)
@click.option(
    "--target-project",
    prompt=True,
    help=(
        "Name of the utopya project to copy the new model to. If not given, "
        "will prompt for it. "
        "Note that this project needs to be known by utopya; "
        "use `utopya projects register` to register it first."
    ),
)
@click.option(
    "--dry-run",
    flag_value=True,
    help=(
        "Perform a dry run: No copy or write operations will be carried out."
    ),
)
@click.option(
    "--skip-exts",
    show_default=True,
    default="pyc",
    callback=lambda c, _, val: val.split(),
    help=(
        "File extensions to skip. "
        "To pass multiple values, use quotes and separate individual "
        "extensions using spaces. There should not be any leading dots!"
    ),
)
@click.option(
    "--register",
    flag_value=True,
    help=("If given, will also register the newly created model."),
)
def copy(
    *,
    model_name: str,
    label: str,
    new_name: str,
    target_project: str,
    dry_run: bool,
    skip_exts: str,
    register: bool,
):
    raise NotImplementedError("copy")  # TODO


# -- Registration -------------------------------------------------------------
# .. utopya models register ...................................................

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
    "--project-name",
    type=click.STRING,
    default=None,
    help="Name of the project this model is part of.",
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
    project_name: str,
):
    """Registers a new model"""
    Echo.progress(f"Registering model '{model_name}' (label: '{label}')...")
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
        project_name=project_name,
    )

    import utopya

    try:
        utopya.MODELS.register_model_info(
            model_name,
            exists_action=exists_action,
            **bundle_kwargs,
        )

    except Exception as exc:
        Echo.error("Registration failed!", error=exc)
        sys.exit(1)

    else:
        Echo.success(f"Successully registered model '{model_name}'.")


# .. utopya models register batch .............................................


@register.command(
    name="from-list",
    help=(
        "Register multiple models by providing aligned lists of their names, "
        "the paths to their executables and their source directories. "
        "Any additional information is attempted to be extracted from the "
        "corresponding model source directory or a potentially existing model "
        "information file.\n"
        "Note that the arguments need to be separable lists, where the "
        "`--separator` argument determines the separation string. "
        "Also, arguments probably need to be put into quotes and spaces need "
        "to be escaped."
    ),
)
@click.argument("model_names", type=click.STRING)
@click.option(
    "--executables",
    type=click.STRING,
    help=(
        "A list of paths pointing to the model executables. "
        "Paths may be given as relative to the --base-executable-dir. "
        "If all paths match a pattern, consider using the "
        "--executable-fstr argument instead. "
        "One of these arguments *needs* to be given."
    ),
)
@click.option(
    "--source-dirs",
    type=click.STRING,
    help=(
        "A list of paths pointing to the model source directories. "
        "Paths may be given as relative to the --base-source-dir. "
        "If all paths match a pattern, consider using the "
        "--source-dir-fstr argument instead."
    ),
)
@click.option(
    "--base-executable-dir",
    type=click.Path(file_okay=False, exists=True, resolve_path=True),
    help="If given, relative executable paths are interpreted against this.",
)
@click.option(
    "--base-source-dir",
    type=click.Path(file_okay=False, exists=True, resolve_path=True),
    help=(
        "If given, relative source directory paths are interpreted against "
        "this."
    ),
)
@click.option(
    "--executable-fstr",
    type=click.STRING,
    help=(
        "A format string that can be used instead of the --executables "
        "argument and is evaluated for each entry in MODEL_NAMES."
    ),
)
@click.option(
    "--source-dir-fstr",
    type=click.STRING,
    help=(
        "A format string that can be used instead of the --source-dirs "
        "argument and is evaluated for each entry in MODEL_NAMES."
    ),
)
@click.option(
    "--py-tests-dir-fstr",
    type=click.STRING,
    help=(
        "A format string that can be used to set the models python tests "
        "directory."
    ),
)
@click.option(
    "--py-plots-dir-fstr",
    type=click.STRING,
    help=(
        "A format string that can be used to set the models python tests "
        "directory."
    ),
)
@click.option(
    "--separator",
    default=";",
    help=(
        "By which separator to split the --model-names, --executables, and "
        "--source-dirs arguments. Default: ';'"
    ),
)
@click.option(
    "--label",
    type=click.STRING,
    default="set_via_cli",
    help=(
        "Label to identify the info bundles with; if not given, will use a "
        "default value. This allows registering multiple versions of a model "
        "under the same name."
    ),
)
@click.option(
    "--project-name",
    type=click.STRING,
    default=None,
    help="Name of the project these models are part of.",
)
@click.option(
    "--exists-action",
    default="validate",
    type=click.Choice(("skip", "raise", "validate", "overwrite")),
    help=(
        "Which action to take upon an existing bundle with the same label. "
        "By default, validates the to-be-added information with a potentially "
        "existing bundle; this will fail if the to-be-added bundle does not "
        "compare equal to an existing bundle with the same label."
    ),
)
def register_from_list(
    *,
    model_names: str,
    executables: str,
    source_dirs: str,
    executable_fstr: str,
    source_dir_fstr: str,
    separator: str,
    **kwargs,
):
    if executable_fstr:
        if executables:
            Echo.error(
                "Arguments --executable-fstr and --executables are mutually "
                "exclusive! Make sure to only pass one of them."
            )
            sys.exit(1)

        executables = _evaluate_fstr_for_list(
            model_names=model_names, fstr=executable_fstr, sep=separator
        )

    elif not executables:
        Echo.error("Missing argument --executables or --executable-fstr!")
        sys.exit(1)

    if source_dir_fstr:
        if source_dirs:
            Echo.error(
                "Arguments --source-dir-fstr and --source-dirs are mutually "
                "exclusive! Make sure to only pass one of them."
            )
            sys.exit(1)

        source_dirs = _evaluate_fstr_for_list(
            model_names=model_names, fstr=source_dir_fstr, sep=separator
        )

    # Everything ok, can start registering
    import utopya
    from utopya.model_registry._registration import register_models_from_list

    try:
        register_models_from_list(
            registry=utopya.MODELS,
            model_names=model_names,
            executables=executables,
            source_dirs=source_dirs,
            separator=separator,
            **kwargs,
            _log=Echo,
        )

    except Exception as exc:
        Echo.error("Registration failed!", error=exc)
        raise
        sys.exit(1)


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
        "existing bundle; this will fail if the to-be-added bundle does not "
        "compare equal to an existing bundle with the same label."
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
    num_files = len(manifest_files)

    if custom_model_name and num_files != 1:
        Echo.error(
            "A model name can only be specified if only a single "
            f"manifest file is given (got {num_files}). "
        )
        Echo.info(
            "Either remove the `--model-name` argument or make sure to pass "
            "only a single manifest file."
        )
        sys.exit(1)

    # All checks done, let's go
    Echo.info(f"Parsing information from {num_files} manifest file(s) ...")
    import utopya

    for i, manifest_file in enumerate(manifest_files):
        Echo.progress(
            f"\nRegistering model from manifest file {i + 1} / {num_files} ..."
        )
        Echo.remark(f"File:  {manifest_file}")

        bundle_kwargs = utopya.tools.load_yml(manifest_file)

        # Handle custom model name or label
        model_name = bundle_kwargs.pop("model_name")
        if custom_model_name:
            Echo.note(f"Using custom model name '{custom_model_name}' ...")
            model_name = custom_model_name

        label = bundle_kwargs.pop("label", "from_manifest_file")
        if custom_label:
            Echo.note(f"Using custom label '{custom_label}' ...")
            label = custom_label

        # Also add path to manifest file in the paths dict, such that the
        # info bundle knows about it. Then register.
        utopya.tools.add_item(
            manifest_file,
            add_to=bundle_kwargs,
            key_path=("paths", "model_info"),
        )
        try:
            utopya.MODELS.register_model_info(
                model_name,
                label=label,
                exists_action=exists_action,
                extract_model_info=False,  # already done here
                **bundle_kwargs,
            )

        except Exception as exc:
            Echo.error("Registration failed!", error=exc)
            sys.exit(1)

        Echo.info(
            f"Successfully registered model information for '{model_name}', "
            f"labelled '{label}':"
        )
        Echo.remark(utopya.tools.pformat(utopya.MODELS[model_name][label]))

    Echo.success(f"Model information registered successully.")
