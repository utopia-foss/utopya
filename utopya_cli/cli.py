"""Defines the utopya CLI"""

import sys

import click

from .config import config
from .models import models


@click.group(help="The utopya CLI")
def cli():
    pass


cli.add_command(models)
cli.add_command(config)

# -- TODO: migrate to their own module ----------------------------------------


@cli.group(help="Manage projects")
def projects():
    pass
