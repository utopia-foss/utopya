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
    help=(
        "utopya: a versatile simulation runner and manager\n\n"
        "utopya's main feature is to configure, run, and evaluate computer "
        "simulations. "
        "In the minimalistic use case, utopya is a simple runner for an "
        "arbitrary executable. "
        "If complying with the full utopya interface, it provides a highly "
        "configurable feature set, including a hierarchical configuration "
        "structure, simulation monitoring, and coupling to an automated "
        "data processing pipeline for simulation output."
    ),
    epilog=(
        "Copyright (C) 2018 – 2022  utopya developers\n\n"
        "utopya is free software and comes with absolutely no warranty. "
        "You are welcome to redistribute it under the conditions specified in "
        "the LGPLv3+ license. "
        "For more information, visit:\n\n"
        "   utopia-project.org  |  gitlab.com/utopia-project/utopya"
    ),
)

cli.add_command(run)
cli.add_command(evaluate)
cli.add_command(batch)
cli.add_command(config)
cli.add_command(models)
cli.add_command(projects)
