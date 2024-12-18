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
        "Perform a simulation run and evaluate its outputs.\n"
        "\n"
        "Starts a simulation of the ``MODEL_NAME`` model, allowing to pass "
        "a custom ``RUN_CFG`` and otherwise manipulating the meta "
        "configuration. Subsequently, the simulation output is fed into the "
        "evaluation pipeline."
    ),
)
@click.argument("model_name", shell_complete=complete_model_names)
@click.argument(
    "run_cfg",
    required=False,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@add_options(OPTIONS["model_selection"])  # --label, --cfg-set
#
# -- Update the meta configuration
#
@click.option(
    "--validate/--no-validate",
    "validate",
    default=None,
    help=(
        "If given, sets whether there will be parameter validation. "
        "If not given, will use the default specified in the meta config."
    ),
)
@click.option(
    "--run-mode",
    default=None,
    type=click.Choice(("single", "sweep")),
    help=(
        "Forces a single simulation or a sweep. If not given, will use the "
        "value specified in the meta configuration."
    ),
)
@click.option(
    "--no-work",
    "worker_perform_task",
    default=True,
    is_flag=True,
    help=(
        "Whether to call WorkerTask or NoWorkTask. NoWorkerTask only creates "
        "configurations, but does not spawn a worker. No-work implies no-eval."
    ),
)
@click.option(
    "--note",
    default=None,
    type=str,
    help=(
        "A suffix that is appended to the name of the run output directory; "
        "this can be useful to give a name to a certain simulation run."
    ),
)
@click.option(
    "-N",
    "--num-steps",
    default=None,
    type=str,
    help=(
        "Sets the number of simulation steps. Needs to be an integer. Metric "
        "suffixes ``(k, M, G, T)`` can be used to denote large numbers, e.g "
        "``1.23M`` translating to ``1230000``, and scientific notation is "
        "also supported (applying integer rounding)."
    ),
)
@click.option(
    "--write-every",
    "--we",
    default=None,
    type=str,
    help=(
        "Sets the ``write_every`` parameter, controlling how frequently model "
        "data is written. "
        "Can be given in the same formats as ``--num-steps``."
    ),
)
@click.option(
    "--write-start",
    "--ws",
    default=None,
    type=str,
    help=(
        "Sets the ``write_start`` parameter, specifying the first time step "
        "at which data is written. After that step, data is written every "
        "``write_every`` th step."
        "Can be given in the same formats as ``--num-steps``."
    ),
)
@click.option(
    "--num-seeds",
    default=None,
    type=click.IntRange(min=1),
    help=(
        "Creates a parameter dimension for the seeds with the given number "
        "of seed values. This also sets the ``perform_sweep`` parameter to "
        "True, such that a sweep is invoked."
    ),
)
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
@click.option(
    "--skippable/--not-skippable",
    "skippable_universes",
    default=None,
    help=(
        "If given, will overwrite the default value for `skippable_universes` "
        "in the meta-configuration. Skippable universes allow that a run can "
        "be joined from another machine using `utopya join-run`, with the "
        "disadvantage that the run is now distributed across machines..."
    ),
)
@click.option(
    "--set-model-params",
    "--mp",
    multiple=True,
    callback=default_none,
    help=(
        "Sets entries in the model configuration, i.e. inside of the "
        "``parameter_space.<model_name>`` entry of the meta configuration. "
        "Example: ``--mp some.param=42`` sets the ``param`` entry in ``some`` "
        "to ``42``. Specify ``DELETE`` as value to remove an entry. "
        "Repeat the ``--mp`` option to set multiple values."
    ),
)
@click.option(
    "--set-pspace-params",
    "--pp",
    multiple=True,
    callback=default_none,
    help=(
        "Like ``--set-model-params`` but attaching to the ``parameter_space`` "
        "entry of the meta configuration. "
        "Repeat the ``--pp`` option to set multiple values."
        "These arguments are parsed after ``--set-pspace-params`` and "
        "``--set-model-params`` such that they can overwrite any of the "
        "previously defined arguments."
    ),
)
@click.option(
    "--set-params",
    "-p",
    multiple=True,
    callback=default_none,
    help=(
        "Like ``--set-model-params`` but attaching to the root level of the "
        "meta configuration. "
        "These arguments are parsed after ``--set-pspace-params`` and "
        "``--set-model-params`` such that they can overwrite any of the "
        "previously defined arguments."
    ),
)
#
# -- Evaluation
#
@click.option(
    "--eval/--no-eval",
    "perform_eval",
    default=None,
    help=(
        "If given, overwrites the default behavior of whether the simulation "
        "run should be followed by the evaluation routine (data loading "
        "and plotting) or not. "
        "The default can also be set in the model info file. "
        "If no default is given there, will attempt evaluation."
    ),
)
@add_options(OPTIONS["load"])
@add_options(OPTIONS["eval"])
@add_options(OPTIONS["debug_flag"])  # --debug
@add_options(OPTIONS["cluster_mode"])  # --cluster-mode
#
#
#
@click.pass_context
def run(ctx, **kwargs):
    """Invokes a model simulation run and subsequent evaluation"""
    import utopya
    from utopya.tools import pformat

    from ._utils import parse_run_and_plots_cfg, parse_update_dicts
    from .eval import _load_and_eval

    _log = utopya._getLogger("utopya")  # TODO How best to do this?!

    # Preparations . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    _log.info("Parsing additional command line arguments ...")
    update_dict, update_plots_cfg = parse_update_dicts(
        _mode="run", **kwargs, _log=_log
    )

    if update_dict:
        _log.note("Updates to meta configuration:\n\n%s", pformat(update_dict))

    model = utopya.Model(
        name=kwargs["model_name"],
        bundle_label=kwargs["label"],
    )

    run_cfg, plots_cfg = parse_run_and_plots_cfg(
        model=model,
        run_cfg=kwargs["run_cfg"],
        plots_cfg=kwargs["plots_cfg"],
        cfg_set=kwargs["cfg_set"],
        _log=_log,
    )
    kwargs["plots_cfg"] = plots_cfg
    kwargs["update_plots_cfg"] = update_plots_cfg

    # Running the simulation . . . . . . . . . . . . . . . . . . . . . . . . .
    mv = model.create_mv(run_cfg_path=run_cfg, **update_dict)
    mv.run()

    # Check whether to start evaluation routine
    perform_eval = model.info_bundle.eval_after_run
    _perform_eval = kwargs.pop("perform_eval")
    if _perform_eval is not None:
        perform_eval = _perform_eval

    if perform_eval is False:
        _log.note("Evaluation routine was not enabled for this model.")
        _log.remark("Use --eval / --no-eval to overwrite model defaults.")
        _log.progress("Exiting now ...\n")
        return

    # Loading and evaluating . . . . . . . . . . . . . . . . . . . . . . . . .
    _load_and_eval(
        _log=_log,
        ctx=ctx,
        mv=mv,
        **kwargs,
    )


# -----------------------------------------------------------------------------
# -- EXPERIMENTAL interface ---------------------------------------------------
# -----------------------------------------------------------------------------


@click.command(
    "run-existing",
    help=(
        "[EXPERIMENTAL] (Re-)Run universes of an existing simulation run.\n"
        "\n"
        "Restores a run of MODEL_NAME from the given RUN_DIR. "
        "Subsequently, individual universes can be (re-)run.\n"
        "\n"
        "Note that this feature is currently experimental, meaning that the "
        "interface may still change a lot."
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
        "to be added. To supply multiple, use the -u option multiple times. "
        "If no universes are specified, a run on all universes is performed."
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
        "Set this option to re-run universes that were previously run. "
        "Cannot be used together with --skip-existing."
    ),
)
@click.option(
    "-s",
    "--skip-existing",
    "skip_existing_output",
    default=False,
    is_flag=True,
    help=(
        "Whether to skip universes with existing output. "
        "Set this option to complete universes from a previous run. "
        "Cannot be used together with --uni or --clear-existing."
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
    skip_existing_output: bool,
):
    """Repeats a model simulation in parts or entirely"""
    import utopya

    _log = utopya._getLogger("utopya")

    model = utopya.Model(name=model_name, bundle_label=label)
    mv = model.create_distributed_mv(run_dir=run_dir)

    if universes:
        if skip_existing_output:
            raise RuntimeError(
                "Option --skip-existing cannot be set together "
                "with a list of universes to perform."
            )

        mv.run_selection(
            uni_id_strs=universes,
            num_workers=num_workers,
            clear_existing_output=clear_existing_output,
        )
    else:
        if skip_existing_output and clear_existing_output:
            raise RuntimeError(
                "Options --skip-existing and --clear-existing are exclusive "
                "but both were set."
            )

        mv.run(
            num_workers=num_workers,
            clear_existing_output=clear_existing_output,
            skip_existing_output=skip_existing_output,
        )

    _log.note("Evaluation routine is not possible for repeated run.")
    _log.remark(
        "For evaluation, call:\n  utopya eval %s %s\n",
        model_name,
        os.path.basename(run_dir),
    )
    _log.progress("Exiting now ...\n")


# -----------------------------------------------------------------------------


@click.command(
    "join-run",
    help=(
        "[EXPERIMENTAL] Join a currently-running simulation.\n"
        "\n"
        "Initializes MODEL_NAME from RUN_DIR and joins in working on "
        "the remaining simulation tasks.\n"
        "\n"
        "Note that this feature is currently experimental, meaning that the "
        "interface may still change a lot."
    ),
)
@click.argument("model_name", shell_complete=complete_model_names)
@click.argument(
    "run_dir",
    shell_complete=complete_run_dirs,
    required=False,
)
@add_options(OPTIONS["label"])
@add_options(OPTIONS["num_workers"])  # -W, --num-workers
#
#
#
@click.pass_context
def join_run(
    ctx,
    run_dir,
    model_name: str,
    label: str,
    num_workers: int,
):
    """Repeats a model simulation in parts or entirely"""
    import utopya

    _log = utopya._getLogger("utopya")

    model = utopya.Model(name=model_name, bundle_label=label)
    mv = model.create_distributed_mv(run_dir=run_dir)

    mv.join_run(num_workers=num_workers)

    _log.info("Not proceeding to evaluation for this joined run.")
    _log.remark(
        "Once the run is complete, call:\n\n  utopya eval %s %s\n",
        model_name,
        os.path.basename(mv.dirs["run"]),
    )
    _log.progress("Exiting now ...\n")
