"""Implements the `utopya projects` subcommand"""

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
    help="Lists all registered projects",
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
    Echo.info("Loading utopya project list ...")

    from utopya.cfg import load_from_cfg_dir
    from utopya.tools import pformat

    projects = load_from_cfg_dir("projects")

    for project_name, project_info in projects.items():
        Echo.info(f"- {project_name}")
        if not long_mode:
            continue

        for k, v in project_info.items():
            Echo.remark(f"  {k:23s}: {v}")  # TODO adjust
        Echo.info("")


# .. utopya projects edit .....................................................


@projects.command(help="Edit the projects registry directly.")
def edit():
    """Edits the projects registry file"""
    Echo.info(f"Opening projects registry file for editing ...")
    Echo.warning("Take care not to corrupt the file!")
    from utopya.cfg import get_cfg_path

    if not click.confirm("Open file for editing?"):
        Echo.info("Not opening.")
        sys.exit(0)

    try:
        click.edit(
            filename=get_cfg_path("projects"),
            extension=".yml",
        )

    except Exception as exc:
        Echo.error("Editing projects registry file failed!", error=exc)
        sys.exit(1)

    Echo.success(f"Successfully edited projects registry file.")


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
    from utopya.cfg import load_from_cfg_dir, write_to_cfg_dir

    Echo.info(f"Removing project registry entry '{project_name}' ...")

    if not skip_confirmation and not click.confirm("Are you sure?"):
        Echo.info("Not removing.")
        sys.exit(0)

    projects = load_from_cfg_dir("projects")

    if project_name not in projects:
        Echo.error(f"There is no project named '{project_name}' registered!")
        Echo.info(f"Registered projects:  {', '.join(projects)}")
        sys.exit(1)

    del projects[project_name]
    write_to_cfg_dir("projects", projects)
    Echo.success(f"Successfully removed project entry '{project_name}'.")


# .. utopya projects register .................................................


@projects.command(
    name="register",
    help="Register a project or validate an existing one.",
)
@click.argument("project_name")
@click.option(
    "--base-dir",
    type=click.File(exists=True, dir_okay=False, resolve_path=True),
    help="This project's base directory.",
)
@click.option(
    "--info-file",
    default=None,
    type=click.File(exists=True, dir_okay=False, resolve_path=True),
    help="A file that contains additional project information.",
)
@click.option(
    "--validate",
    is_flag=True,
    default=False,
)
def register_project(
    *,
    project_name: str,
    base_dir: str,
    info_file: str,
    validate: bool,
):
    """Registers a project"""
    from utopya.cfg import load_from_cfg_dir, write_to_cfg_dir

    Echo.info(f"Registering project '{project_name}' ...")

    # TODO
