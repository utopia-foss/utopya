"""Implements the `utopya projects` subcommand"""

import os
import sys

import click

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
    from utopya.tools import pformat

    Echo.info("\n--- Utopya Projects ---")
    for project_name, project in PROJECTS.items():
        Echo.info(f"- {project_name}")
        if not long_mode:
            continue

        for k, v in project.data.dict().items():
            if isinstance(v, dict):
                Echo.remark(f"  {k:15s}")
                for sk, sv in v.items():
                    Echo.remark(f"    .{sk:12s} : {sv}")
            else:
                Echo.remark(f"  {k:15s} : {v}")
        Echo.info("")


# .. utopya projects edit .....................................................


@projects.command(help="Edit a project's registry file directly.")
@click.argument("project_name")
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
@click.argument("project_name")
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
def register(**kwargs):
    """Registers a project or validates an existing one"""
    from utopya import PROJECTS

    try:
        PROJECTS.register(**kwargs)

    except Exception as exc:
        Echo.error("Project registration failed!", error=exc)
        raise
        sys.exit(1)
