"""Implements the utopya run CLI subtree"""

import sys

import click

from ._shared import OPTIONS, add_options
from ._utils import Echo


@click.command(
    help=(
        "Perform a simulation run and evaluate its outputs.\n"
        "\n"
        "Starts a simulation of the MODEL_NAME model, allowing to pass "
        "a custom RUN_CFG and otherwise manipulating the meta configuration. "
        "Subsequently, the simulation output is fed into the evaluation "
        "pipeline."
    ),
)
@click.argument("model_name")
@click.argument(
    "run_cfg",
    required=False,
    default=None,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "--cfg-set",
    "--cs",
    default=None,
    help=(
        "If the chosen model provides configuration sets, use the config "
        "files from the chosen set for the `run_cfg` and `--plots-cfg` "
        "arguments. Note that the specific arguments still take precedence "
        "over the values from the config sets; to use default paths, "
        "specify empty strings (`''`) for those arguments."
    ),
)
@click.option(
    "--label",
    default=None,
    help=(
        "For model names that have multiple info bundles registered, a "
        "label is needed to unambiguously select the desired one. "
        "Alternatively, use the `utopya models set-default` CLI command "
        "to set a default label for a model."
    ),
)
#
# -- Update the meta configuration
#
@click.option(
    "-d", "--debug", count=True, help=("The debug level.")  # TODO Expand
)
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
        "suffixes (k, M, G, T) can be used to denote large numbers, e.g "
        "`1.23M` translating to `1230000`, and scientific notation is also "
        "supported (applying integer rounding)."
    ),
)
@click.option(
    "--write-every",
    "--we",
    default=None,
    type=str,
    help=(
        "Sets the `write_every` parameter, controlling how frequently model "
        "data is written. "
        "Can be given in the same formats as --num-steps."
    ),
)
@click.option(
    "--write-start",
    "--ws",
    default=None,
    type=str,
    help=(
        "Sets the `write_start` parameter, specifying the first time step "
        "at which data is written. After that step, data is written every "
        "`write_every`th step."
        "Can be given in the same formats as --num-steps."
    ),
)
@click.option(
    "--num-seeds",
    default=None,
    type=click.IntRange(min=1),
    help=(
        "Creates a parameter dimension for the seeds with the given number "
        "of seed values. This also sets the `perform_sweep` parameter to "
        "True, such that a sweep is invoked."
    ),
)
@click.option(
    "--set-model-params",
    "--mp",
    multiple=True,
    help=(
        "Sets entries in the model configuration, i.e. inside of the "
        "`parameter_space.<model_name>` entry of the meta configuration. "
        "Example: --mp some.param=42 sets the 'param' entry in 'some' to 42. "
        "Repeat the --mp option to set multiple values."
    ),
)
@click.option(
    "--set-pspace-params",
    "--pp",
    multiple=True,
    help=(
        "Like --set-model-params but attaching to the root level of the meta "
        "configuration. "
        "Repeat the --pp option to set multiple values."
        "These arguments are parsed after --set-pspace-params and "
        "--set-model-params such that they can overwrite any of the "
        "previously defined arguments."
    ),
)
@click.option(
    "--set-params",
    "-p",
    multiple=True,
    help=(
        "Like --set-model-params but attaching to the root level of the meta "
        "configuration. "
        "These arguments are parsed after --set-pspace-params and "
        "--set-model-params such that they can overwrite any of the "
        "previously defined arguments."
    ),
)
#
# -- Evaluation
#
@click.option(
    "--no-eval",
    flag_value=True,
    help="If given, no evaluation will be carried out.",
)
@add_options(OPTIONS["load"])
@add_options(OPTIONS["eval"])
#
#
#
def run(**kwargs):
    """Invokes a model simulation run and subsequent evaluation"""
    for k, v in kwargs.items():
        print(f"  {k:>21s} :  {v}")

    import utopya
    from utopya.exceptions import ValidationError
    from utopya.tools import pformat

    from ._utils import parse_run_and_plots_cfg, parse_update_args

    _log = utopya._getLogger("utopya_cli")  # TODO How best to do this?!

    # Preparations . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    _log.info("Parsing additional command line arguments ...")
    update_dict, update_plots_cfg = parse_update_args(_mode="run", **kwargs)

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
        _log=_log,  # TODO Check if working
    )

    try:
        mv = model.create_mv(run_cfg_path=run_cfg, **update_dict)

    except ValidationError as err:
        _log.error("%s", err)
        _log.critical("Exiting now ...")
        sys.exit(1)

    # Running the simulation . . . . . . . . . . . . . . . . . . . . . . . . .
    mv.run()
    _log.success("Simulation run finished.\n")

    if kwargs["no_eval"]:
        _log.progress("Received --no-eval. Exiting now.")
        return

    # Loading data into the data tree and (optionally) showing it . . . . . . .
    if not kwargs["use_data_tree_cache"]:
        mv.dm.load_from_cfg()

    else:
        if not mv.dm.tree_cache_exists:
            mv.dm.load_from_cfg()
            mv.dm.dump()

        else:
            _log.hilight("Restoring tree from cache file ...")
            mv.dm.restore()

    if kwargs["show_data_tree"] == "full":
        _log.info(mv.dm.tree)

    elif kwargs["show_data_tree"] == "condensed":
        _log.info(mv.dm.tree_condensed)

    # Plotting . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    if not kwargs["interactive"]:
        mv.pm.plot_from_cfg(
            plots_cfg=plots_cfg,
            plot_only=kwargs["plot_only"] if kwargs["plot_only"] else None,
            **update_plots_cfg,
        )

        if kwargs["reveal_output"] and mv.pm.common_out_dir:
            click.launch(mv.pm.common_out_dir)

        _log.success("All done.\n")
        return

    # TODO
    raise NotImplementedError("interactive plotting")
