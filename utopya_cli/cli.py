"""Defines the utopya CLI"""

import sys

import click

from .models import *


@click.group()
def utopya():
    pass


utopya.add_command(models)

# -- TODO: migrate to their own module ----------------------------------------


@utopya.group(help="Manage projects")
def projects():
    pass
