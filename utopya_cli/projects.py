"""Implements the `utopya projects` subcommand"""

import click

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
    import utopya

    if long_mode:
        click.echo(utopya.MODELS.info_str_detailed)
    else:
        click.echo(utopya.MODELS.info_str)
