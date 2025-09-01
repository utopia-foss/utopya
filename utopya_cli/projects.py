"""Implements the `utopya projects` subcommand"""

import glob
import os
import sys

import click

from ._shared import complete_project_names
from ._utils import Echo

projects = click.Group(
    name="projects",
    help="Show available projects and register new ones.",
)


# .. utopya projects ls .......................................................


@projects.command(
    name="ls",
    help="Lists all registered projects.",
)
@click.option(
    "-l",
    "--long",
    "long_mode",
    is_flag=True,
    help="Show more detailed information.",
)
def list_projects(long_mode: bool):
    """Lists available projects"""
    Echo.progress("Loading utopya project list ...")

    from utopya import PROJECTS

    Echo.info("\n--- Utopya Projects ---")
    for project_name, project in PROJECTS.items():
        Echo.info(f"- {project_name}")
        if not long_mode:
            continue

        for k, v in project.data.model_dump().items():
            if isinstance(v, dict):
                Echo.remark(f"  {k:15s}")
                for sk, sv in v.items():
                    Echo.remark(f"    .{sk:12s} : {sv}")
            else:
                Echo.remark(f"  {k:15s} : {v}")
        Echo.info("")


# .. utopya projects edit .....................................................


@projects.command(help="Edit a project's registry file directly.")
@click.argument("project_name", shell_complete=complete_project_names)
def edit(project_name: str):
    """Edits a project registry file"""
    import utopya
    from utopya.exceptions import MissingEntryError

    Echo.progress(
        f"Opening '{project_name}' project's registry file for editing ..."
    )
    Echo.caution("Take care not to corrupt the file!")

    if not click.confirm("Open file for editing?"):
        Echo.info("Not opening.")
        sys.exit(0)

    # Try to get the file path, which may fail if the project is not loadable
    try:
        filename = utopya.PROJECTS[project_name].registry_file_path

    except MissingEntryError as err:
        if project_name not in utopya.PROJECTS._load_errors:
            Echo.error(err)
            sys.exit(1)

        # Use a different approach to determine the file name
        from utopya.cfg import UTOPYA_CFG_SUBDIRS

        filename = os.path.join(
            UTOPYA_CFG_SUBDIRS["projects"], f"{project_name}.yml"
        )

    # Now open for editing
    try:
        click.edit(filename=filename, extension=".yml")

    except Exception as exc:
        Echo.error("Editing project registry file failed!", error=exc)
        sys.exit(1)

    Echo.success(f"Successfully edited project registry file.")


# .. utopya projects rm .......................................................


@projects.command(
    name="rm",
    help="Remove a project.",
)
@click.argument("project_name", shell_complete=complete_project_names)
@click.option(
    "-y",
    "skip_confirmation",
    is_flag=True,
    help="If given, will skip the confirmation prompt.",
)
def remove(
    *,
    project_name: str,
    skip_confirmation: bool,
):
    """Removes an entry from the project registry file"""
    from utopya import PROJECTS
    from utopya.exceptions import MissingEntryError

    Echo.progress(f"Removing project registry entry '{project_name}' ...")

    if not skip_confirmation and not click.confirm("Are you sure?"):
        Echo.info("Not removing.")
        sys.exit(0)

    try:
        PROJECTS.remove_entry(project_name)
    except MissingEntryError as err:
        Echo.error(err)
        sys.exit(1)

    Echo.success(f"Successfully removed project entry '{project_name}'.")


# .. utopya projects register .................................................


@projects.command(
    name="register",
    help=(
        "Register a project or validate an existing one.\n"
        "\n"
        "Required arguments are the base directory of the project."
    ),
)
@click.argument(
    "base_dir",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
@click.option(
    "--info-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help=(
        "A file that contains all additional project information like "
        "the project name, relevant paths, or other metadata. "
        "If not given, will search for some candidate files relative to "
        "``BASE_DIR``, e.g. ``.utopya-project.yml``."
    ),
)
@click.option(
    "--custom-name",
    "custom_project_name",
    type=str,
    help=(
        "A custom project name that may differ from the one given in the "
        "project info file."
    ),
)
@click.option(
    "--require-matching-names",
    is_flag=True,
    help=(
        "If set, requires that an optionally given ``--custom-name`` and the "
        "name set in the project info file match exactly."
    ),
)
@click.option(
    "--exists-action",
    default="validate",
    type=click.Choice(("raise", "validate", "overwrite", "update")),
    help="What to do if a project of the same name is already registered.",
)
@click.option(
    "--with-models",
    "register_models",
    is_flag=True,
    default=False,
    help=(
        "If set, will additionally register all models in the project's model "
        "directory by recursively looking for their manifest files (ending in "
        "``_info.yml``)."
    ),
)
@click.option(
    "--label",
    "custom_label",
    type=click.STRING,
    default=None,
    help=(
        "If given, this label will be used instead of the one given in the "
        "manifest file(s) for model registration. "
        "If no custom label is given and the manifest file does not define "
        "one either, the default will be ``from_manifest_file``."
    ),
)
@click.option(
    "--set-default",
    "set_as_default",
    is_flag=True,
    default=None,
    help=("Whether to set the registered model(s) as default."),
)
def register(
    *,
    register_models: bool,
    custom_label: str,
    set_as_default: bool,
    exists_action: str,
    **kwargs,
):
    """Registers a project or validates an existing one.

    This also includes the option to additionally register all models
    contained in the project's models directory."""
    import utopya
    from utopya import PROJECTS

    from .models import _register_from_manifest

    try:
        project = PROJECTS.register(exists_action=exists_action, **kwargs)

    except Exception as exc:
        Echo.error("Project registration failed!", error=exc)
        raise
        sys.exit(1)

    if not register_models:
        return

    # Look for model info files
    Echo.progress("\nLooking for models to also be registered ...")
    models_dir = project.paths.models_dir
    Echo.remark("Models directory:\n  %s", models_dir)

    manifest_files = glob.glob(
        os.path.join(models_dir, "**", "*_info.yml"), recursive=True
    )
    num_files = len(manifest_files)
    Echo.note(
        "Found %d manifest file%s.", num_files, "s" if num_files != 1 else ""
    )

    # Register
    for i, manifest_file in enumerate(manifest_files):
        Echo.progress(
            f"\nRegistering model from manifest file {i + 1} / {num_files} ..."
        )
        Echo.remark(f"File:  {manifest_file}")

        try:
            model_name, label = _register_from_manifest(
                manifest_file,
                set_as_default=set_as_default,
                custom_project_name=project.project_name,
                custom_label=custom_label,
                exists_action=exists_action,
            )

        except Exception as exc:
            Echo.error("Model registration failed!", error=exc)
            sys.exit(1)

        Echo.info(
            f"Successfully registered model information for '{model_name}':"
        )
        Echo.remark(utopya.tools.pformat(utopya.MODELS[model_name][label]))

    Echo.success(
        f"Project '{project.project_name}' and {i+1} accompanying model(s) "
        "registered successully."
    )
