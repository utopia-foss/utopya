"""This is the legacy command line interface for utopya"""

import argparse
import sys
import time
import traceback
from typing import Tuple

# Define helper functions -----------------------------------------------------


def parse_update_args(
    args: argparse.Namespace, *, mode: str
) -> Tuple[dict, dict]:
    """Parses the given namespace, extracting update dictionaries for the
    Multiverse and the plots configuration

    Args:
        args (argparse.Namespace): The arguments to extract info from
        mode (str): The mode argument. Can be ``run`` or ``eval``

    Returns:
        Tuple[dict, dict]: Multiverse update config and plots update config
    """
    # Set an empty update dict. It will hold adjustments to the given configs
    update_dict = {}
    update_plots_cfg = {}
    # NOTE The following updates to the update_dict rely on it being mutable

    # In debug mode, set a number of configuration keys
    if args.debug:
        # Set model log level to DEBUG
        add_item(
            "debug",
            add_to=update_dict,
            key_path=["parameter_space", "log_levels", "model"],
        )

        # Let PlotManager raise exceptions
        add_item(
            True, add_to=update_dict, key_path=["plot_manager", "raise_exc"]
        )

        # Let WorkerManager raise exceptions
        add_item(
            "raise",
            add_to=update_dict,
            key_path=["worker_manager", "nonzero_exit_handling"],
        )

    # Arguments relevant only in run mode
    if mode == "run":
        # If a model_note was given, add it to the paths
        if args.note:
            add_item(
                args.note, add_to=update_dict, key_path=["paths", "model_note"]
            )

        # The WorkerManager's non-zero exit handling, if in debug mode
        if args.sim_errors:
            add_item(
                args.sim_errors,
                add_to=update_dict,
                key_path=["worker_manager", "nonzero_exit_handling"],
            )

        # Disabling parameter validation
        if args.skip_validation:
            add_item(
                False, add_to=update_dict, key_path=["perform_validation"]
            )

        # Number of simulation steps
        # NOTE Error checking happens in Multiverse (also for write_* args)
        if args.num_steps is not None:
            add_item(
                args.num_steps,
                add_to=update_dict,
                key_path=["parameter_space", "num_steps"],
            )

        # The root-level write_every parameter
        if args.write_every is not None:
            add_item(
                args.write_every,
                add_to=update_dict,
                key_path=["parameter_space", "write_every"],
            )

        # The root-level write_start parameter
        if args.write_start is not None:
            add_item(
                args.write_start,
                add_to=update_dict,
                key_path=["parameter_space", "write_start"],
            )

        # Set seeds to a parameter dimension object
        if args.num_seeds is not None:
            add_item(
                args.num_seeds,
                value_func=lambda v: ParamDim(default=42, range=[v]),
                add_to=update_dict,
                key_path=["parameter_space", "seed"],
                is_valid=lambda v: bool(v > 1),
                ErrorMsg=lambda v: ValueError(
                    "Argument --num-seeds "
                    "needs to be > 1, "
                    "was {}.".format(v)
                ),
            )

            # Make it, by default, perform a sweep
            add_item(True, add_to=update_dict, key_path=["perform_sweep"])

        # Set the perform_sweep parameter
        if args.single:
            add_item(False, add_to=update_dict, key_path=["perform_sweep"])

        elif args.sweep:
            add_item(True, add_to=update_dict, key_path=["perform_sweep"])

        # Set the cluster mode flag
        if args.cluster_mode:
            add_item(True, add_to=update_dict, key_path=["cluster_mode"])

        # Set general configuration entries
        if args.set_model_params:
            # Make sure the parameter space entry is available
            if not update_dict.get("parameter_space"):
                update_dict["parameter_space"] = dict()

            # Make sure the model-related entry is available
            if not update_dict["parameter_space"].get(args.model_name):
                update_dict["parameter_space"][args.model_name] = dict()

            add_from_kv_pairs(
                *args.set_model_params,
                add_to=update_dict["parameter_space"][args.model_name],
            )

        if args.set_params:
            # Make sure the parameter space entry is available
            if not update_dict.get("parameter_space"):
                update_dict["parameter_space"] = dict()

            add_from_kv_pairs(
                *args.set_params, add_to=update_dict["parameter_space"]
            )

    # Adjustments relevant only in eval mode
    elif mode == "eval":
        # Can add eval-specific arugments here
        pass

    else:
        raise ValueError("Bad mode '{}'! Needs be: run or eval".format(mode))

    # Evaluate arguments that apply to both run and eval modes
    if args.load_parallel is not None:
        add_item(
            args.load_parallel,
            add_to=update_dict,
            key_path=["data_manager", "load_cfg", "data", "parallel"],
        )

    if args.cluster_mode:
        add_item(True, add_to=update_dict, key_path=["cluster_mode"])

    if args.set_cfg:
        add_from_kv_pairs(*args.set_cfg, add_to=update_dict)

    if args.update_plots_cfg:
        try:
            add_from_kv_pairs(*args.update_plots_cfg, add_to=update_plots_cfg)
        except ValueError:
            update_plots_cfg = load_yml(*args.update_plots_cfg)

    return update_dict, update_plots_cfg


def parse_run_and_plots_cfg(
    args: argparse.Namespace,
    *,
    model: "utopya.Model",
    _interactive_mode: bool = False,
) -> Tuple[str, str]:
    """Extracts paths to the run configuration and plots configuration by
    looking at the given arguments and the model's configuration sets.

    If ``_interactive_mode`` is given, will not read the run configuration but
    only the plots configuration where it would be confusing to have the
    corresponding log message appear. Also, this will not lead to system exit
    if parsing failed.
    """
    run_cfg_path = args.run_cfg_path
    plots_cfg = args.plots_cfg

    if args.cfg_set and (run_cfg_path is None or plots_cfg is None):
        log.info("Looking up config set '%s' ...", args.cfg_set)
        try:
            cfg_set = model.get_config_set(args.cfg_set)

        except ValueError as err:
            if _interactive_mode:
                raise
            log.error(err)
            sys.exit(1)

        # Explicitly given arguments take precedence. Also, the config set may
        # not contain a run or eval configuration.
        if run_cfg_path is None and cfg_set.get("run"):
            if not _interactive_mode:
                run_cfg_path = cfg_set["run"]
                log.note("  Using run.yml from config set.")
            else:
                log.remark("  Not using run.yml in interactive plotting mode.")

        if plots_cfg is None and cfg_set.get("eval"):
            plots_cfg = cfg_set["eval"]
            log.note("  Using eval.yml from config set.")

    return run_cfg_path, plots_cfg


def handle_interactive_plotting_exception(
    exc: Exception, *, args, context: str, remark: str = None
):
    """Helper function to handle exceptions during interactive plotting"""
    if args.debug:
        log.error("An exception occured during %s!\n", context)
        traceback.print_exc()
        log.note("Remove --debug flag to hide traceback.")
    else:
        log.error(
            "An exception occured during %s!\n\n%s: %s\n",
            context,
            exc.__class__.__name__,
            str(exc),
        )
        log.note("Add --debug flag to show traceback or --help for CLI help.")

    if remark:
        log.remark("%s", remark)
    log.warning("Remaining in interactive plotting mode ...")


# -----------------------------------------------------------------------------
# Define the CLI --------------------------------------------------------------
# Top level parsers
parser = argparse.ArgumentParser(
    description="Welcome to the Utopia command line interface.",
    epilog="Utopia — Comprehensive Modelling Framework for Complex Environmental "
    "Systems\nCopyright (C) 2016 – 2021  Utopia Developers\n\n"
    "This program comes with ABSOLUTELY NO WARRANTY.\n"
    "This is free software, and you are welcome to redistribute it\n"
    "under certain conditions. Please refer to the copyright notice\n"
    "(COPYING.md) and license texts (LICENSE and LICENSE.LESSER) in\n"
    "the source code repository for details:\n"
    "https://ts-gitlab.iup.uni-heidelberg.de/utopia/utopia",
    # we want to set line breaks ourselves
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

subparsers = parser.add_subparsers(dest="mode")

p_models = subparsers.add_parser(
    "models", help="view and manipulate the model registry"
)
p_cfg = subparsers.add_parser(
    "config", help="set user-specific config options"
)
p_run = subparsers.add_parser("run", help="perform a simulation run")
p_eval = subparsers.add_parser(
    "eval",
    help="load a finished Utopia run and perform " "only the evaluation",
)
p_batch = subparsers.add_parser(
    "batch",
    help="run and evaluate multiple simulations " "from a batch configuration",
)


# subcommand: models ..........................................................
p_models_sp = p_models.add_subparsers(dest="models_mode")

pm_ls = p_models_sp.add_parser("ls", help="list registered models")
pm_info = p_models_sp.add_parser("info", help="show model information")
pm_reg = p_models_sp.add_parser(
    "register", help="add a new model to the model registry"
)
pm_edit = p_models_sp.add_parser(
    "edit", help="edit an existing model registry entry"
)
pm_rm = p_models_sp.add_parser("rm", help="remove a model registry entry")
pm_cp = p_models_sp.add_parser(
    "copy", help="create a new model by copying an " "existing one"
)

# sub-subcommand: model registration  . . . . . . . . . . . . . . . . . . . . .
# Main arguments
pm_reg.add_argument(
    "model_name",
    help="Name of the model to register. Supports --separator argument.",
)
pm_reg.add_argument(
    "--executable",
    required=True,
    help="Path to the executable that is to be associated with this model. If "
    "--base-executable-dir is given, this may be a relative path. "
    "Supports --separator argument.",
)

# Directories; useful for registration via CMake and in combination with --sep
pm_reg_dir = pm_reg.add_argument_group("directory paths")
pm_reg_dir.add_argument(
    "--src-dir",
    help="Path to the model source directoy. If given, it is attempted to "
    "locate the configuration files in this directory and custom paths "
    "may be specified as relative to this directory. If --base-src-dir "
    "was given, this directory may be specified in relative terms. "
    "Supports --separator.",
)
pm_reg_dir.add_argument(
    "--base-src-dir",
    help="Shared base path to source directory; if given, --src-dir may be "
    "relative.",
)
pm_reg_dir.add_argument(
    "--base-executable-dir",
    help="Shared base path to binary directory; if given, --bin-path may be "
    "a relative path",
)

# Config files
pm_reg_cfg = pm_reg.add_argument_group(
    "configuration files",
    description="Paths to model-related YAML config files",
)
pm_reg_cfg.add_argument(
    "--model-cfg",
    help="Path to the (default) model configuration. If --src-dir was given, "
    "it may be given relative to it. The path given here has precedence "
    "over a potentially auto-detected path within --src-dir.",
)
pm_reg_cfg.add_argument(
    "--plots-cfg",
    help="Path to the default plots configuration. If --src-dir was given, "
    "it may be given relative to it. The path given here has precedence "
    "over a potentially auto-detected path within --src-dir.",
)
pm_reg_cfg.add_argument(
    "--base-plots-cfg",
    help="Path to the base plots configuration. If --src-dir was given, "
    "it may be given relative to it. The path given here has precedence "
    "over a potentially auto-detected path within --src-dir.",
)

pm_reg_prj = pm_reg.add_argument_group("project information")
pm_reg_prj.add_argument(
    "--project-name",
    help="Name of the Utopia project this model belongs to. If using the "
    "--separator argument, all models are associated with this project.",
)
pm_reg_prj.add_argument(
    "--update-project-info",
    action="store_true",
    help="If given, will allow the update of project information.",
)
pm_reg_prj.add_argument(
    "--project-base-dir", help="Path to the base directory of the project"
)
pm_reg_prj.add_argument(
    "--project-models-dir", help="Path to the models directory of the project"
)
pm_reg_prj.add_argument(
    "--project-python-model-tests-dir",
    help="Path to the python tests directory of the project",
)
pm_reg_prj.add_argument(
    "--project-python-model-plots-dir",
    help="Path to the python plots directory of the project",
)


# Modifiers
pm_reg.add_argument(
    "--label",
    help="The label under which this configuration will be stored in the "
    "model registry. Useful if there will be multiple configuration "
    "bundles for the same model name.",
)
pm_reg.add_argument(
    "--overwrite-label",
    action="store_true",
    help="Whether a labelled model info bundle that already exists in the "
    "registry entry may be overwritten.",
)
pm_reg.add_argument(
    "--separator",
    help="If set, this allows the model_name, --bin-path, and --src-dir "
    "arguments to be lists that are separated by the given string. Note "
    "that in such a case ONLY these arguments are considered; all others "
    "are ignored. Spaces need to be escaped.",
)
pm_reg.add_argument(
    "--exists-action",
    default=None,
    choices=["skip", "raise", "clear", "validate"],
    help="Action to take on the _model_ already existing; this controls the "
    "behaviour with respect to the bundle information that is to be "
    "added.",
)


# sub-subcommand: edit model registry entry  . . . . . . . . . . . . . . . . .
# TODO Implement properly / or delete?
pm_edit.add_argument(
    "model_name", help="Name of the model whose registry entry to edit."
)


# sub-subcommand: list model registry entries . . . . . . . . . . . . . . . . .
# TODO Make more options available (low priority)
pm_ls.add_argument(
    "-l", "--long", action="store_true", help="List in long format."
)

# sub-subcommand: list model registry entries . . . . . . . . . . . . . . . . .
# TODO Make more options available (low priority)
pm_info.add_argument(
    "model_name", help="Name of the model to retrieve the info for"
)


# sub-subcommand: remove model registry entries . . . . . . . . . . . . . . . .
pm_rm.add_argument(
    "model_names", nargs="*", help="Names of the models to remove"
)
pm_rm.add_argument(
    "--all",
    action="store_true",
    help="Remove the registry entries for all currently registered models.",
)


# sub-subcommand: copy a model . . . . . . . . . . . . . . . . . . . . . . . .
pm_cp.add_argument("model_name", help="Name of the models to copy")
pm_cp.add_argument(
    "--new-name",
    nargs="?",
    help="Name of the new model. If not given, will prompt for it.",
)
pm_cp.add_argument(
    "--target-project",
    nargs="?",
    help="Name of the Utopia project to copy the new model to. If not given, "
    "will prompt for it. "
    "Note that this project needs to be known to the Utopia Frontend, "
    "i.e. registered in the ~/.config/utopia/projects.yml file. If this "
    "is not the case, update the project you want to create the new "
    "model in and reconfigure it; this should register it.",
)
pm_cp.add_argument(
    "--non-interactive",
    action="store_true",
    help="If given, will not use any prompts. This requires for all arguments "
    "to be specified directly.",
)
pm_cp.add_argument(
    "--dry-run",
    action="store_true",
    help="If given, performs a dry run: No copy or write operations will be "
    "carried out.",
)
pm_cp.add_argument(
    "--skip-exts",
    nargs="+",
    default=[".pyc"],
    help="File extensions to skip. These need to have a leading dot! If "
    "nothing is given, skips the following extensions:  .pyc",
)


# subcommand: config ..........................................................
# the name of the config to manipulate
p_cfg.add_argument(
    "cfg_name",
    choices=[
        "user",
        "utopya",
        "batch",
        "external_module_paths",
        "plot_module_paths",
        "projects",
    ],
    help="The name of the configuration entry that is to be manipulated.",
)

p_cfg.add_argument(
    "--set",
    nargs="+",
    help="Set entries in the specified configuration. Expected arguments are "
    "key=value pairs, where the key may be a dot-separated string of "
    "keys for dict traversal. If the configuration file does not exist, "
    "it will be created.",
)
p_cfg.add_argument(
    "--get",
    action="store_true",
    help="Retrieve all entries from the specified configuration. This is "
    "always invoked _after_ the --set command was executed (if given).",
)

p_cfg.add_argument(
    "--deploy",
    action="store_true",
    help="Deploy an empty or default configuration file to ~/.config/utopia/, "
    "if it does not already exist. For the user configuration, deploys a "
    "file (with all entries disabled) to ~/.config/utopia/user_cfg.yml, "
    "asking for input if a file already exists at that location.",
)


# subcommand: run .............................................................
p_run.add_argument("model_name", help="Name of the model to run")
p_run.add_argument(
    "run_cfg_path",
    default=None,
    nargs="?",
    help="Path to the run configuration. If not given, the default model "
    "configuration is used.",
)

# configuration sets
p_run.add_argument(
    "--cfg-set",
    "--cs",
    nargs="?",
    help="If the chosen model provides configuration sets, use the config "
    "files from the chosen set for the `run_cfg_path` and `--plots-cfg` "
    "arguments. Note that the specific arguments still take precedence "
    "over the values from the config sets; to use default paths, "
    'specify `""` for those arguments.',
)

# run mode
p_run_mode = p_run.add_mutually_exclusive_group()
p_run_mode.add_argument(
    "-s",
    "--single",
    action="store_true",
    help="If given, forces a single simulation. If a parameter space was "
    "configured, uses the default location.",
)
p_run_mode.add_argument(
    "-p",
    "--sweep",
    action="store_true",
    help="If given, forces a parameter sweep. Fails if no parameter space was "
    "configured.",
)

# updating specific meta configuration entries
p_run_upd = p_run.add_argument_group("update meta-configuration")
p_run_upd.add_argument(
    "--note",
    default=None,
    nargs="?",
    help="Overwrites the `paths->model_note` entry which is used in creation "
    "of the run directory path.",
)
p_run_upd.add_argument(
    "-d",
    "--debug",
    action="store_true",
    help="If given, sets a number of configuration parameters which make "
    "debugging of the model and the associated plotting scripts easier, "
    "e.g. by lowering the model log level to DEBUG and creating "
    "tracebacks for exceptions in the python scripts. Note that the "
    "--sim-errors flag takes precedence over what is set here.",
)
p_run_upd.add_argument(
    "--sim-errors",
    default=None,
    nargs="?",
    choices=["ignore", "warn", "warn_all", "raise"],
    help="Controls the value of the WorkerManager's `nonzero_exit_handling` "
    "flag which defines how errors in simulations are handled.",
)
p_run_upd.add_argument(
    "--skip-validation",
    action="store_true",
    help="If given, no parameter validation will be performed. Useful to set "
    "if the parameter space volume is very large (>10k).",
)

p_run_upd.add_argument(
    "-N",
    "--num-steps",
    default=None,
    nargs="?",
    type=str,
    help="Sets the number of simulation steps. Needs to be an integer. Metric "
    "suffixes (k, M, G, T) can be used to denote large numbers, e.g "
    "`1.23M` translating to `1230000`, and scientific notation is also "
    "supported (applying integer rounding).",
)
p_run_upd.add_argument(
    "--write-every",
    default=None,
    nargs="?",
    type=str,
    help="Sets the root-level `write_every` parameter, controlling how "
    "frequently model data is written. Can be given in the same formats "
    "as `num_steps`.",
)
p_run_upd.add_argument(
    "--write-start",
    default=None,
    nargs="?",
    type=str,
    help="Sets the root-level `write_start` parameter, specifying the first "
    "time step at which data is written. After that time, data is "
    "written every `write_every`th step. Can be given in the same "
    "formats as `num_steps`.",
)
p_run_upd.add_argument(
    "--num-seeds",
    default=None,
    nargs="?",
    type=int,
    help="Creates a parameter dimension for the seeds with the given number "
    "of seed values. This also sets the `perform_sweep` parameter to "
    "True, such that a sweep is invoked.",
)

# arguments for generically updating meta configuration keys
p_run_upd.add_argument(
    "--set-params",
    default=None,
    nargs="+",
    type=str,
    help="Sets key-value pairs in the `parameter_space` entry of the meta "
    "configuration. Example: foo.bar=42 sets the 'bar' entry in the "
    "'foo' dict to 42. Note that multiple parameter can be set at once "
    "by separating them with a space; if a space needs to be in the "
    "argument value, put the strings into '...' or \"...\".",
)
p_run_upd.add_argument(
    "--set-cfg",
    default=None,
    nargs="+",
    type=str,
    help="Like --set-params but attaching to the root level of the meta "
    "configuration. This function is carried out after --set-params, "
    "such that it can overwrite any of the previously defined arguments.",
)
p_run_upd.add_argument(
    "--set-model-params",
    default=None,
    nargs="+",
    type=str,
    help="Like --set-params but attaching to the level of the currently "
    "selected model within the parameter space. This function is carried "
    "out before --set-params, meaning that --set-params can overwrite "
    "values set using this argument.",
)

# plotting
p_run_plt = p_run.add_argument_group("plotting")
p_run_plt.add_argument(
    "--plots-cfg",
    default=None,
    nargs="?",
    help="If given, uses the plots configuration file found at this path "
    "instead of the defaults of the model.",
)
p_run_plt.add_argument(
    "-P",
    "--load-parallel",
    default=None,
    const=True,
    nargs="?",
    type=int,
    help="If given, will force loading data in parallel. If an integer is "
    "given, will use that many processes for loading. Can also be used "
    "to enforce non-parallel loading by setting to 1. Regardless of the "
    "argument value, this will overwrite any potentially existing "
    "data_manager.load_cfg.data.parallel entry in the meta-config.",
)
p_run_plt.add_argument(
    "--update-plots-cfg",
    default=None,
    nargs="+",
    help="Sets key-value pairs in the `plots_cfg` entry of the plots meta "
    "configuration. Example: plot_foo.bar=42 sets the 'bar' entry in the "
    "'plot_foo' dict to 42. Note that multiple parameter can be set at "
    "once by separating them with a space; if a space needs to be in the "
    "argument value, put the strings into '...' or \"...\".",
)
p_run_plt.add_argument(
    "--no-plot",
    action="store_true",
    help="If set, no plots will be created. To perform plots a later point, "
    "use the `utopia eval` subcommand.",
)
p_run_plt.add_argument(
    "-i",
    "--interactive",
    action="store_true",
    help="If set, the CLI will not exit after plotting finished, but allow to "
    "continue plotting in an interactive session. This option is useful "
    "for creating multiple plots in an iterative fashion, especially if "
    "data loading time is large. Note that all Multiverse-related "
    "configuration options can not be changed during the session.",
)
p_run_plt.add_argument(
    "--plot-only",
    "--po",
    default=None,
    nargs="*",
    help="If given, will plot only those entries of the plot configuration "
    "that match the names given here. This can also be used to activate "
    "plots that are disabled in the specified plot configuration.",
)
p_run_plt.add_argument(
    "-R",
    "--reveal-output",
    action="store_true",
    help="If set, opens the output directory after plotting finished.",
)

# misc
p_run.add_argument(
    "--use-data-tree-cache",
    "--tc",
    action="store_true",
    help="If set, uses tree file caching: If no cache file exists, creates "
    "one after loading all data; if a tree file already exists, uses "
    "that to restore the data tree. This may bring a speed-up if the "
    "creation of the data tree takes a long time.",
)
p_run.add_argument(
    "--suppress-data-tree",
    action="store_true",
    help="If set, loading of data will not print out the data tree.",
)
p_run.add_argument(
    "--full-data-tree",
    action="store_true",
    help="If set, loading of data will print out the full data tree instead "
    "of a condensed one.",
)
p_run.add_argument(
    "--cluster-mode", action="store_true", help="Enables cluster mode."
)


# subcommand: eval ............................................................
p_eval.add_argument(
    "model_name",
    help="Name of the model to evaluate. This is used to find the output "
    "directory",
)
p_eval.add_argument(
    "run_dir_path",
    default=None,
    nargs="?",
    help="Path to the run directory that is to be loaded. It can be a "
    "relative or absolute path, or the timestamp (including model note, "
    "if present) of the directory. If not given, the directory with the "
    "most recent timestamp is used.",
)

# configuration sets
p_eval.add_argument(
    "--cfg-set",
    "--cs",
    nargs="?",
    help="If the chosen model provides configuration sets, use the config "
    "files from the chosen set for the `--plots-cfg` and "
    "`--run-cfg-path` arguments. Note that the specific arguments still "
    "take precedence over the values from the config sets; to use "
    'default paths, specify `""` for those arguments.',
)

# plot configuration
p_eval_plt = p_eval.add_argument_group("plotting")
p_eval_plt.add_argument(
    "--plots-cfg",
    default=None,
    nargs="?",
    help="If given, uses the plots configuration file found at this path "
    "instead of the defaults of the model.",
)
p_eval_plt.add_argument(
    "--update-plots-cfg",
    default=None,
    nargs="+",
    help="Sets key-value pairs in the `plots_cfg` entry of the plots meta "
    "configuration. Example: plot_foo.bar=42 sets the 'bar' entry in "
    "the 'plot_foo' dict to 42. Note that multiple parameter can be set "
    "at once by separating them with a space; if a space needs to be in "
    "the argument value, put the strings into '...' or \"...\".",
)
p_eval_plt.add_argument(
    "--plot-only",
    "--po",
    default=None,
    nargs="*",
    help="If given, will plot only those entries of the plot configuration "
    "that match the names given here. This can also be used to activate "
    "plots that are disabled in the specified plot configuration.",
)
p_eval_plt.add_argument(
    "-i",
    "--interactive",
    action="store_true",
    help="If set, the CLI will not exit after plotting finished, but allow to "
    "continue plotting in an interactive session. This option is useful "
    "for creating multiple plots in an iterative fashion, especially if "
    "data loading time is large. Note that all FrozenMultiverse-related "
    "configuration options can not be changed during the session.",
)
p_eval_plt.add_argument(
    "-R",
    "--reveal-output",
    action="store_true",
    help="If set, opens the output directory after plotting finished.",
)
p_eval_plt.add_argument(
    "-d",
    "--debug",
    action="store_true",
    help="If given, configures the PlotManager such that it raises exceptions "
    "instead of warning (and proceeding to plot). If given while in "
    "interactive plotting mode, a traceback is printed but interactive "
    "plotting mode is _not_ quit.",
)

# misc
p_eval.add_argument(
    "-P",
    "--load-parallel",
    default=None,
    const=True,
    nargs="?",
    type=int,
    help="If given, will force loading data in parallel. If an integer is "
    "given, will use that many processes for loading. Can also be used "
    "to enforce non-parallel loading by setting to 1. Regardless of the "
    "argument value, this will overwrite any potentially existing "
    "data_manager.load_cfg.data.parallel entry in the meta-config.",
)
p_eval.add_argument(
    "--run-cfg-path",
    default=None,
    nargs="?",
    help="Path to the run configuration. Can be used to change the "
    "configuration of DataManager and PlotManager.",
)
p_eval.add_argument(
    "--set-cfg",
    default=None,
    nargs="+",
    type=str,
    help="Sets key-value pairs in the meta configuration. Example: foo.bar=42 "
    "sets the 'bar' entry in the 'foo' dict to 42. Note that multiple "
    "parameter can be set at once by separating them with a space; if a "
    "space needs to be in the argument value, put the strings into '...' "
    'or "...".',
)
p_eval.add_argument(
    "--use-data-tree-cache",
    "--tc",
    action="store_true",
    help="If set, uses tree file caching: If no cache file exists, creates "
    "one after loading all data; if a tree file already exists, uses "
    "that to restore the data tree. This may bring a speed-up if the "
    "creation of the data tree takes a long time.",
)
p_eval.add_argument(
    "--suppress-data-tree",
    action="store_true",
    help="If set, loading of data will not print out the data tree.",
)
p_eval.add_argument(
    "--full-data-tree",
    action="store_true",
    help="If set, loading of data will print out the full data tree instead "
    "of a condensed one.",
)
p_eval.add_argument(
    "--cluster-mode",
    action="store_true",
    help="Enables cluster mode. Note that for plotting, this information is "
    "not yet taken into account!",
)


# subcommand: batch ...........................................................
p_batch.add_argument("batch_cfg_path", help="Path to batch configuration file")
p_batch.add_argument(
    "-d",
    "--debug",
    action="store_true",
    help="If set, an error in an individual task will stop all other tasks.",
)
p_batch.add_argument(
    "-s",
    "--single-worker",
    action="store_true",
    help="If set, will use 'task' parallelization level instead of 'batch'. "
    "Effectively, the batch tasks will be worked on sequentially. "
    "This option can also be useful for debugging or when encountering "
    "memory issues.",
)
p_batch.add_argument(
    "--note",
    default=None,
    nargs="?",
    help="Overwrites the `paths->model_note` entry which is used in creation "
    "of the batch run directory path.",
)


# CLI defined now.
# -----------------------------------------------------------------------------


def cli():
    # Parse the arguments now. Exit directly, if no mode subcommand was given.
    args = parser.parse_args()

    if args.mode is None:
        parser.print_help()
        sys.exit()

    # If continuing further, need some imports
    from dantro.logging import getLogger

    log = getLogger(__name__)  # TODO Make this controllable!

    from dantro.tools import make_columns as _make_columns
    from paramspace import ParamDim

    import utopya
    from utopya.cfg import get_cfg_path, load_from_cfg_dir, write_to_cfg_dir
    from utopya.cltools import (
        add_from_kv_pairs,
        copy_model_files,
        deploy_user_cfg,
        prompt_for_new_plot_args,
        register_models,
    )
    from utopya.parameter import ValidationError
    from utopya.tools import add_item, load_yml, open_folder, pformat

    # Batch subcommand ........................................................
    if args.mode == "batch":
        import os

        from utopya.batch import BatchTaskManager

        # Assemble update arguments
        kws = dict()
        if args.debug:
            kws["debug"] = args.debug

        if args.single_worker:
            kws["parallelization_level"] = "task"

        if args.note:
            kws["paths"] = dict(note=args.note)

        # Here we go ...
        btm = BatchTaskManager(batch_cfg_path=args.batch_cfg_path, **kws)

        print("")
        btm.perform_tasks()

        log.success("Batch work all finished now, yay! :)\n")
        sys.exit()

    # Config subcommand .......................................................
    if args.mode == "config":
        if args.cfg_name == "user" and args.deploy:
            deploy_user_cfg()
            sys.exit()

        elif args.deploy:
            raise NotImplementedError("Can only deploy user config for now.")

        # Need at least one of the get or set arguments
        if not args.get and not args.set:
            raise ValueError("Missing --set and/or --get argument.")

        # For all the following, need a configuration
        cfg = load_from_cfg_dir(args.cfg_name)  # empty dict if file is missing

        if args.set:
            add_from_kv_pairs(*args.set, add_to=cfg)
            write_to_cfg_dir(args.cfg_name, cfg)
            log.info(
                "Set %d entr%s in '%s' configuration.",
                len(args.set),
                "ies" if len(args.set) != 1 else "y",
                args.cfg_name,
            )

        if args.get:
            log.info(
                "Reading '%s' configuration file from:\n  %s",
                args.cfg_name,
                get_cfg_path(args.cfg_name),
            )
            print(
                "\n--- {} Configuration ---\n{}"
                "".format(
                    args.cfg_name.replace("_", " ").title(), pformat(cfg)
                )
            )
        # Done here.
        sys.exit()

    # Models subcommand .......................................................

    if args.mode == "models":
        if args.models_mode == "register":
            register_models(args, registry=utopya.MODELS)

        elif args.models_mode == "edit":
            raise NotImplementedError("utopia models edit")

        elif args.models_mode == "rm":
            model_names = args.model_names
            if args.all:
                model_names = list(utopya.MODELS.keys())

            if not model_names:
                log.info("No models registered. Cannot remove anything.")
                sys.exit()

            log.info(
                "Removing model registry entries for the following "
                "models:\n  %s",
                ", ".join(model_names),
            )

            for model_name in model_names:
                utopya.MODELS.remove_entry(model_name)

        elif args.models_mode == "copy":
            copy_model_files(
                model_name=args.model_name,
                new_name=args.new_name,
                target_project=args.target_project,
                skip_exts=args.skip_exts,
                use_prompts=not args.non_interactive,
                dry_run=args.dry_run,
            )

        elif args.models_mode == "info":
            model = utopya.Model(name=args.model_name)

            # Config sets
            log.info("Fetching available config sets ...")
            cfg_sets = model.default_config_sets
            log.note(
                "Have %d config sets available for model '%s':\n%s",
                len(cfg_sets),
                model.name,
                _make_columns(cfg_sets),
            )

        else:
            # Mode: ls or None
            if getattr(args, "long", False):
                info_str = utopya.MODELS.info_str_detailed

            else:
                info_str = utopya.MODELS.info_str

            print(info_str, end="\n\n")

        # End here.
        sys.exit()

    # Run & eval subcommands ..................................................
    # Prepare arguments for Multiverse . . . . . . . . . . . . . . . . . . . .

    log.info("Parsing additional command line arguments ...")
    update_dict, update_plots_cfg = parse_update_args(args, mode=args.mode)

    # Finished with generating the update dict; give some info on it
    if update_dict:
        log.note("Updates to meta configuration:\n\n%s", pformat(update_dict))

    # Preparations finished now.

    # Create Model and perform the run  . . . . . . . . . . . . . . . . . . . .
    # Instantiate a Model object to take care of the rest
    model = utopya.Model(name=args.model_name)
    # TODO Do bundle selection here

    # Prepare the run and plots configuration
    run_cfg_path, plots_cfg = parse_run_and_plots_cfg(args, model=model)

    # Distinguish by CLI mode whether to create Multiverse or FrozenMultiverse
    if args.mode == "run":
        # Create the Multiverse object
        # If parameter validation failed, suppress the traceback
        try:
            mv = model.create_mv(run_cfg_path=run_cfg_path, **update_dict)

        except ValidationError as err:
            log.error("%s", err)
            log.critical("Exiting now ...")
            sys.exit(1)

        # ... and run the simulation
        mv.run()
        log.success("Simulation run finished.\n")

        # Only need to continue if plots are to be created
        if args.no_plot:
            log.progress("Received --no-plot. Exiting now.")
            sys.exit()

    elif args.mode == "eval":
        # Create frozen Multiverse; supplies similar interface as Multiverse
        mv = model.create_frozen_mv(
            run_dir=args.run_dir_path, run_cfg_path=run_cfg_path, **update_dict
        )

    else:
        raise ValueError("Unexpected CLI mode: {}".format(args.mode))

    # Loading  . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # This can be done either without the tree cache (loading directly from
    # the files specified by the configuration) or with the tree cache, in
    # which case the first invocation needs to dump the cache file and any
    # subsequent invocation needs to restore it.
    if not args.use_data_tree_cache:
        mv.dm.load_from_cfg()

    else:
        if not mv.dm.tree_cache_exists:
            mv.dm.load_from_cfg()
            mv.dm.dump()

        else:
            log.hilight("Restoring tree from cache file ...")
            mv.dm.restore()

    # Show the tree now
    if not bool(args.suppress_data_tree):
        if bool(args.full_data_tree):
            print(mv.dm.tree)
        else:
            print(mv.dm.tree_condensed)

    # Plotting . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    if not getattr(args, "interactive", False):
        mv.pm.plot_from_cfg(
            plots_cfg=plots_cfg, plot_only=args.plot_only, **update_plots_cfg
        )

        if args.reveal_output and mv.pm.common_out_dir:
            open_folder(mv.pm.common_out_dir)

        log.success("All done.\n")
        sys.exit()

    # Interactive Plotting . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Carry over all argvs relevant for the eval subparser.
    # For convenience, drop a potentially given run directory path argument,
    # which would have to be removed from the argument list manually otherwise.
    argv = [
        arg for arg in sys.argv[2:] if arg != getattr(args, "run_dir_path", "")
    ]

    # ... and drop some other flags and combinations of shortcuts of flags
    # that will no longer be necessary.
    # NOTE This is a rather rudimentary approach and will probably not remove
    #      *all* possibly offending arguments. It's purely for convenience at
    #      this point. If there are remaining argv that are not parseable, the
    #      parser in interactive plotting mode will complain and the input can
    #      be adjusted at that point.
    argv = [
        arg
        for arg in argv
        if arg
        not in (
            "--single",
            "-s",
            "--sweep",
            "-p",
            "--note",
            "--interactive",
            "-i",
            "--use-data-tree-cache",
            "--tc",
            "--suppress-data-tree",
            "--full-data-tree",
            "--load-parallel",
            "-P",
            "-iP",
            "-Pi",
        )
    ]

    # While in interactive mode, the following loop is carried out repeatedly.
    # A counter variable is used to label successive output directories.
    iap_session = 0

    while args.interactive:
        print("")
        log.hilight("--- Interactive plotting session %d ---", iap_session)

        # Unless this is the very first session, need to prompt for new args.
        if iap_session > 0:
            # Provide some information on where the data is from; which is
            # useful if this is a very long session
            log.remark(
                "Currently selected data directory:\n  %s", mv.dm.dirs["data"]
            )

            log.note("Use Control+C to exit.")

            try:
                argv, args = prompt_for_new_plot_args(
                    old_argv=argv, old_args=args, parser=p_eval
                )

            except KeyboardInterrupt:
                # Ask for confirmation before quitting the plotting session.
                # This is to prohibit accidentally exiting the session, which
                # is especially relevant if loading data took a long time.
                print("\n")
                log.warning("Really exit interacive plotting?")
                log.note(
                    "Confirm with Control+C ... or wait to remain in "
                    "interactive plotting mode."
                )

                # Want a small unexitable delay period before confirmation in
                # order to not exit on double key-strokes.
                t_delay = 0.7
                for i in range(int(t_delay * 20)):
                    try:
                        time.sleep(t_delay / 20)
                    except KeyboardInterrupt:
                        pass

                try:
                    for i in range(3):
                        log.caution("%d ...", 3 - i)
                        time.sleep(1)

                except KeyboardInterrupt:
                    break

                log.success("Remaining in interactive plotting mode ...")
                continue

            except EOFError:
                # EOFError is invoked by builtins.input when the input is read
                # from a stream that is not the standard input stream
                # In this case, can't have a confirmation
                break

            except (ValueError, SystemExit):
                # ... just prompt again; error message was already shown
                continue

        # Get updated configurations
        try:
            _, plots_cfg = parse_run_and_plots_cfg(
                args, model=model, _interactive_mode=True
            )
            _, update_plots_cfg = parse_update_args(args, mode="eval")

        except Exception as exc:
            handle_interactive_plotting_exception(
                exc, args=args, context="parsing of new PlotManager arguments"
            )
            continue

        if update_plots_cfg:
            log.note(
                "Updates to plot configuration:\n\n%s",
                pformat(update_plots_cfg),
            )

        # Create a new PlotManager and increment the session counter. Use a
        # custom output directory (inside the regular eval directory) and
        # include the session number into it.
        try:
            mv.renew_plot_manager(
                out_dir="session{:03d}/".format(iap_session),
                raise_exc=args.debug,
            )

        except Exception as exc:
            handle_interactive_plotting_exception(
                exc,
                args=args,
                context="PlotManager renewal",
                remark=(
                    "Inspect the traceback for details and check that all "
                    "involved plot configuration files are using valid YAML."
                ),
            )
            continue

        finally:
            iap_session += 1
            print("")

        # Now, try to plot:
        try:
            mv.pm.plot_from_cfg(
                plots_cfg=plots_cfg,
                plot_only=args.plot_only,
                **update_plots_cfg,
            )

        except KeyboardInterrupt:
            print("")
            log.caution("Interrupted current plotting session.")
            log.warning("Remaining in interactive plotting mode ...")
            continue

        except Exception as exc:
            handle_interactive_plotting_exception(
                exc, args=args, context="interactive plotting"
            )
            continue

        # Done plotting, allow to show the output
        if args.reveal_output and mv.pm.common_out_dir:
            try:
                open_folder(mv.pm.common_out_dir)

            except Exception as exc:
                # This may fail for certain paths; it should not lead to the
                # plotting session being interrupted.
                handle_interactive_plotting_exception(
                    exc, args=args, context="opening of output directory"
                )
                continue

        # End of while loop

    # If this point is reached, interactive plotting was exited
    print("\n")
    log.success("Left interactive plotting mode.\n")
