"""Implements the utopya run CLI subtree"""

import os

import click

from ._shared import (
    OPTIONS,
    add_options,
    complete_model_names,
    complete_run_dirs,
    default_none,
)
from ._utils import Echo


@click.command(
    help=(
        "(Re-)Run universes of an existing simulation.\n"
        "\n"
        "Restores a simulation of the ``MODEL_NAME`` model. Subsequently, "
        "individual tasks (universes) can be (re-)run."
    ),
)
@click.argument("model_name", shell_complete=complete_model_names)
@click.argument(
    "simulation_path",
    shell_complete=complete_run_dirs,
    required=True,
    # type=click.Path(exists=True, dir_okay=True, resolve_path=True),
)
@click.option(
    "--universe",
    "--uni",
    multiple=True,
    type=str,
)
@add_options(OPTIONS["label"])
#
# -- Update the worker manager
#
@click.option(
    "-W",
    "--num-workers",
    default=None,
    type=click.IntRange(min=-os.cpu_count() + 1, max=+os.cpu_count()),
    help=(
        "Shortcut for meta-config entry ``worker_manager.num_workers``, which "
        "sets the number of worker processes. "
        "Can be an integer; if negative, will deduce the number from the "
        "number of available CPUs."
    ),
)
#
#
#
@click.pass_context
def run_existing(ctx, **kwargs):
    """Repeats a model simulation in parts or entirely"""
    import utopya
    from utopya.tools import pformat

    from ._utils import parse_run_and_plots_cfg, parse_update_dicts
    from .eval import _load_and_eval

    _log = utopya._getLogger("utopya")  # TODO How best to do this?!

    # Preparations . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    _log.info("Parsing additional command line arguments ...")

    model = utopya.Model(
        name=kwargs["model_name"],
        bundle_label=kwargs["label"],
    )

    mv = model.create_distributed_mv(run_dir=kwargs["simulation_path"])

    # Running the simulation . . . . . . . . . . . . . . . . . . . . . . . . .
    mv.run_selection(
        uni_id_strs=kwargs["universe"], num_workers=kwargs["num_workers"]
    )

    _log.note("Evaluation routine is not possible for repeated run.")
    _log.remark("Please call a separate eval task.")
    _log.progress("Exiting now ...\n")
    return
