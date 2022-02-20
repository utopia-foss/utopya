"""Defines the utopya CLI"""

import sys

import click

from .batch import batch
from .config import config
from .models import models
from .projects import projects


@click.group(
    help=("The utopya CLI"),
)
def cli():
    pass


cli.add_command(batch)
cli.add_command(config)
cli.add_command(models)
cli.add_command(projects)
