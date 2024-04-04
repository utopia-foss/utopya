"""Implements the utopya run-existing CLI subtree"""

import os

import click

from ._shared import (
    OPTIONS,
    add_options,
    complete_model_names,
    complete_run_dirs,
)


@click.command(
    help=(
        "(Re-)Run universes of an existing simulation run.\n"
        "\n"
        "Restores a run of ``MODEL_NAME`` from the given RUN_DIR. "
        "Subsequently, individual universes can be (re-)run."
    ),
)
@click.argument("model_name", shell_complete=complete_model_names)
@click.argument(
    "run_dir",
    shell_complete=complete_run_dirs,
    required=True,
)
@add_options(OPTIONS["label"])
@click.option(
    "-u",
    "--uni",
    "--universe",
    "universes",
    multiple=True,
    type=str,
    help=(
        "Which universes to run (e.g.: 00154). Note that leading zeros need "
        "to be added. To supply multiple, use the -u option multiple times."
    ),
)
@click.option(
    "-c",
    "--clear-existing",
    "clear_existing_output",
    default=False,
    is_flag=True,
    help=(
        "Whether to clear existing output files from universes. "
        "Set this option to re-run universes that were previously run."
    ),
)
@add_options(OPTIONS["num_workers"])  # -W, --num-workers
#
#
#
@click.pass_context
def run_existing(
    ctx,
    run_dir,
    model_name: str,
    label: str,
    universes: list,
    num_workers: int,
    clear_existing_output: bool,
    **kwargs,
):
    """Repeats a model simulation in parts or entirely"""
    import utopya

    _log = utopya._getLogger("utopya")

    model = utopya.Model(name=model_name, bundle_label=label)
    mv = model.create_distributed_mv(run_dir=run_dir)

    if universes:
        mv.run_selection(
            uni_id_strs=universes,
            num_workers=num_workers,
            clear_existing_output=clear_existing_output,
        )
    else:
        raise NotImplementedError("Cannot run all universes again (yet).")

    _log.note("Evaluation routine is not possible for repeated run.")
    _log.remark(
        "For evaluation, call:\n  utopya eval %s %s\n",
        model_name,
        os.path.basename(run_dir),
    )
    _log.progress("Exiting now ...\n")
