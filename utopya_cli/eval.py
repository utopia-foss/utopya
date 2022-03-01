"""Implements the utopya eval CLI subtree"""

import readline
import traceback
from typing import List, Tuple, Union

import click

from ._shared import OPTIONS, add_options
from ._utils import ANSIesc, Echo


@click.command(
    name="eval",
    help=(
        "Evaluate a simulation run.\n"
        "\n"
        "Loads a simulation of the given MODEL_NAME model and evaluates it "
        "either using the configured defaults or with custom plots configs. "
        "If no RUN_DIR is given, will use the latest output; to evaluate a "
        "specific simulation, the directory name can be used."
    ),
)
@click.argument("model_name")
@click.argument(
    "run_dir",
    required=False,
)
@click.option(
    "--run-cfg",
    default=None,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help=(
        "An optional run config that can be used if changes to the meta "
        "config are desired. This affects evaluation indirectly as it "
        "determines some of the behavior for data loading and setup of the "
        "plotting infrastructure."
    ),
)
@add_options(OPTIONS["model_selection"])
@click.option(
    "--set-params",
    "-p",
    multiple=True,
    help=(
        "Sets entries in the meta configuration using key-value pairs. "
        "Example: -p some.param=42 sets the 'param' entry in 'some' to 42. "
        "Repeat the -p option to set multiple values."
    ),
)
#
# -- Evaluation
#
@add_options(OPTIONS["load"])
@add_options(OPTIONS["eval"])
@add_options(OPTIONS["debug_flag"])  # --debug
#
#
#
@click.pass_context
def evaluate(ctx, **kwargs):
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
    update_dict, update_plots_cfg = parse_update_args(_mode="eval", **kwargs)

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
    kwargs["plots_cfg"] = plots_cfg
    kwargs["update_plots_cfg"] = update_plots_cfg

    # Create frozen Multiverse; supplies similar interface as Multiverse
    mv = model.create_frozen_mv(
        run_dir=kwargs["run_dir"], run_cfg_path=run_cfg, **update_dict
    )

    # Loading and evaluating . . . . . . . . . . . . . . . . . . . . . . . . .
    _load_and_eval(
        _log=_log,
        ctx=ctx,
        mv=mv,
        **kwargs,
    )


# -----------------------------------------------------------------------------


def _load_and_eval(
    *,
    _log,
    ctx,
    mv: Union["Multiverse", "FrozenMultiverse"],
    use_data_tree_cache: bool,
    show_data_tree: str,
    interactive: bool,
    plots_cfg: str,
    update_plots_cfg: dict,
    reveal_output: bool,
    **kwargs,
):
    """Wrapper that takes care of loading and evaluating"""
    # Loading data into the data tree and (optionally) showing it . . . . . . .
    if not use_data_tree_cache:
        mv.dm.load_from_cfg()

    else:
        if not mv.dm.tree_cache_exists:
            mv.dm.load_from_cfg()
            mv.dm.dump()

        else:
            _log.hilight("Restoring tree from cache file ...")
            mv.dm.restore()

    if show_data_tree == "full":
        _log.info(mv.dm.tree)

    elif show_data_tree == "condensed":
        _log.info(mv.dm.tree_condensed)

    # Plotting . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    if not interactive:
        mv.pm.plot_from_cfg(
            plots_cfg=plots_cfg,
            plot_only=kwargs["plot_only"] if kwargs["plot_only"] else None,
            **update_plots_cfg,
        )

        if reveal_output and mv.pm.common_out_dir:
            _log.progress("Revealing output ...")
            _log.remark("Output directory:  %s", mv.pm.common_out_dir)
            click.launch(mv.pm.common_out_dir)

        _log.success("All done.\n")
        return

    ctx.parse_args()
    _interactive_plotting(
        _log=_log,
        ctx=ctx,
        mv=mv,
    )


def _handle_interactive_plotting_exception(
    exc: Exception, *, _log, debug: int, context: str, remark: str = None
):
    """Helper function to handle exceptions during interactive plotting"""
    if debug:
        _log.error("An exception occured during %s!\n", context)
        traceback.print_exc()
        _log.note("Remove --debug flag to hide traceback.")

    else:
        _log.error(
            "An exception occured during %s!\n\n%s: %s\n",
            context,
            exc.__class__.__name__,
            str(exc),
        )
        _log.note("Add --debug flag to show traceback or --help for CLI help.")

    if remark:
        _log.remark("%s", remark)
    _log.warning("Remaining in interactive plotting mode ...")


def _prompt_for_new_plot_args(
    *,
    old_argv: List[str],
    old_params: dict,
    ctx: click.Context,
    click_cmd: click.Command,
    _log,
) -> Tuple[list, dict]:
    """Given some old arguments, prompts for new ones and returns a new
    list of argument values and the parsed argparse namespace result.

    Args:
        old_argv (List[str]): The old argument value list
        old_params (dict): The old set of parsed arguments
        click_cmd (click.Command): The command to use for evaluating the
            newly specified argument value list

    Returns:
        Tuple[list, dict]: New argument value list and parsed arguments.

    Raises:
        ValueError: Upon error in parsing the new arguments.
    """
    # Specify those arguments that may not be given in the prompt
    DISALLOWED_ARGS = (
        "run_cfg_path",  # TODO Check
        "run_dir",
        "set_cfg",
        "cluster_mode",
        "show_data_tree",  # TODO Check
    )

    # Create a new argument list for querying the user. For that, remove
    # those entries from the argvs that are meant to be in the query.
    prefix_argv = ("--interactive", old_params["model_name"])
    to_query = [arg for arg in old_argv if arg not in prefix_argv]
    to_query_str = " ".join(to_query) + (" " if to_query else "")

    # Now, setup the startup hook with a callable that inserts those
    # arguments that shall be editable by the user. Configure readline to
    # allow tab completion for file paths after certain delimiters.
    readline.set_startup_hook(lambda: readline.insert_text(to_query_str))
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n=")

    # Generate the prompt and store the result, stripping whitespace
    prompt_str = (
        "\n{ansi.CYAN}${ansi.MAGENTA} "
        "utopya eval -i {}"
        "{ansi.RESET} ".format(old_params["model_name"], ansi=ANSIesc)
    )
    input_res = input(prompt_str).strip()
    print("")

    # Reset the startup hook to do nothing
    readline.set_startup_hook()

    # Prepare the new list of argument values.
    add_argv = input_res.split(" ") if input_res else []
    new_argv = list(prefix_argv) + add_argv

    # ... and parse it to the eval subparser.
    new_args = parser.parse_args(new_argv)
    # NOTE This may raise SystemExit upon the --help argument or other
    #      arguments that are not properly parsable.

    # Check that bad arguments were not used
    bad_args = [
        arg
        for arg in DISALLOWED_ARGS
        if getattr(new_args, arg) != parser.get_default(arg)
    ]
    if bad_args:
        print(
            "{ansi.RED}During interactive plotting, arguments that are used "
            "to update the Multiverse meta-configuration cannot be used!"
            "{ansi.RESET}".format(ansi=ANSIesc)
        )
        print(
            "{ansi.DIM}Remove the offending argument{} ({}) and try again. "
            "Consult --help to find out the available plotting-related "
            "arguments."
            "{ansi.RESET}".format(
                "s" if len(bad_args) != 1 else "",
                ", ".join(bad_args),
                ansi=ANSIesc,
            )
        )
        raise ValueError(
            "Cannot specify arguments that are used for updating the "
            "(already-in-use) meta-configuration of the current Multiverse "
            f"instance. Disallowed arguments: {', '.join(DISALLOWED_ARGS)}"
        )

    return new_argv, new_args


def _interactive_plotting(
    *,
    _log,
    ctx,
    mv,
    args,
    argv,
):
    """Interactive plotting routine"""
    raise NotImplementedError("interactive plotting")

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
                    old_argv=argv, old_params=args, parser=p_eval
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
