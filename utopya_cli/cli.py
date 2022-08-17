"""Defines the utopya CLI"""

import click

from .batch import batch
from .config import config
from .eval import evaluate
from .models import models
from .projects import projects
from .run import run
from .test import run_test as test

SUBCOMMANDS = [
    run,
    evaluate,
    test,
    batch,
    config,
    models,
    projects,
]

cli = click.Group(
    help=(
        "**utopya**: a versatile simulation runner and manager\n\n"
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

for subcommand in SUBCOMMANDS:
    cli.add_command(subcommand)
