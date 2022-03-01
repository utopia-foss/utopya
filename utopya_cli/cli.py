"""Defines the utopya CLI"""

import sys

import click

from .batch import batch
from .config import config
from .eval import evaluate
from .models import models
from .projects import projects
from .run import run

cli = click.Group(
    help=("The utopya CLI"),
)

cli.add_command(run)
cli.add_command(evaluate)
cli.add_command(batch)
cli.add_command(config)
cli.add_command(models)
cli.add_command(projects)
