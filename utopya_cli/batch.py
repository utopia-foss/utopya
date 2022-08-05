"""Implements the `utopya batch` subcommand"""

import click

from ._utils import Echo

# -----------------------------------------------------------------------------


@click.command(
    help=(
        "Run and evaluate multiple simulations.\n"
        "\n"
        "Which batch tasks are to be performed is determined using a "
        "batch configuration file."
    ),
)
@click.argument(
    "batch_cfg_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    default=False,
    help="If set, an error in an individual task will stop all other tasks.",
)
@click.option(
    "-s",
    "--single-worker",
    is_flag=True,
    default=False,
    help="If set, will use 'task' parallelization level instead of 'batch'. "
    "Effectively, the batch tasks will be worked on sequentially. "
    "This option can also be useful for debugging or when encountering "
    "memory issues.",
)
@click.option(
    "--note",
    default=None,
    type=str,
    help=(
        "Overwrites the ``paths.note`` entry which is used in creation of the "
        "batch run directory path."
    ),
)
def batch(
    batch_cfg_path: str,
    debug: bool,
    single_worker: bool,
    note: str,
):
    from utopya.batch import BatchTaskManager

    kws = dict()
    if debug:
        kws["debug"] = debug

    if single_worker:
        kws["parallelization_level"] = "task"

    if note:
        kws["paths"] = dict(note=note)

    btm = BatchTaskManager(batch_cfg_path=batch_cfg_path, **kws)
    btm.perform_tasks()

    Echo.success("Batch work all finished now, yay! :)\n")
