"""Defines the utopya CLI"""

import sys

import click

from .models import *


@click.group(help="The utopya CLI")
def cli():
    pass


cli.add_command(models)

# -- TODO: migrate to their own module ----------------------------------------


@cli.group(help="Manage projects")
def projects():
    pass
