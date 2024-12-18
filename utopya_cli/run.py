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
    "-J",
    "--join",
    "join_run",
    type=str,
    default=None,
    shell_complete=complete_run_dirs,
    help=(
        "If given, will not create a new run but join an existing one by "
        "creating a DistributedMultiverse. The option value should be the "
        "path or timestamp of the run directory to join working on. "
        "Alternatively, for `-J latest`, the latest run will be used. "
        "Note that the original Multiverse "
        "needs to have been started with --skippable (or with the meta config "
        "entry `skippable_universes` set to True)."
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
def run(ctx, *, join_run: str = None, **kwargs):
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
    if join_run is None:
        mv = model.create_mv(run_cfg_path=run_cfg, **update_dict)
        mv.run()
    else:
        run_dir = join_run if join_run != "latest" else None
        mv = model.create_distributed_mv(run_dir=run_dir)
        mv.join_run(num_workers=kwargs.get("num_workers"))

        # TODO Should a joined run be allowed to continue with plotting?!
        #      Pro: Parallel plotting. Con: Need to manage duplicates etc.

        _log.info("Not proceeding to evaluation for this joined run.")
        _log.remark(
            "To start evaluation separately, call:\n\n"
            "  utopya eval %s %s %s\n",
            mv.model_name,
            os.path.split(mv.dirs["run"])[-1],
            "" if not kwargs.get("cfg_set") else f"--cs {kwargs['cfg_set']}",
        )
        _log.progress("Exiting now ...\n")
        return

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
