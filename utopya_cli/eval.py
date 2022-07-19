"""Implements the utopya eval CLI subtree"""

import copy
import logging
import readline
import sys
import traceback
from typing import List, Tuple, Union

import click

from ._shared import (
    INTERACTIVE_MODE_PROHIBITED_ARGS,
    OPTIONS,
    add_options,
    default_none,
)
from ._utils import ANSIesc, Echo, parse_run_and_plots_cfg, parse_update_dicts

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


@click.command(
    name="eval",
    help=(
        "Evaluate a previously finished simulation run.\n"
        "\n"
        "Loads a simulation of the given ``MODEL_NAME` model and evaluates "
        "it either using the configured defaults or with custom plots "
        "configs. If no ``RUN_DIR`` is given, will use the latest output; to "
        "evaluate a specific simulation, the directory name can be used."
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
    callback=default_none,
    help=(
        "Sets entries in the meta configuration using key-value pairs. "
        "Example: ``-p some.param=42`` sets the ``param`` entry in ``some`` "
        "to ``42``. Specify ``DELETE`` as value to remove an entry. "
        "Repeat the ``-p`` option to set multiple values."
    ),
)
#
# -- Evaluation
#
@add_options(OPTIONS["load"])
@add_options(OPTIONS["eval"])
@add_options(OPTIONS["debug_flag"])  # --debug
@add_options(OPTIONS["cluster_mode"])  # --cluster-mode
#
#
#
@click.pass_context
def evaluate(ctx, **params):
    """Invokes a model simulation run and subsequent evaluation"""
    import utopya
    from utopya.exceptions import ValidationError
    from utopya.tools import pformat

    _log = utopya._getLogger("utopya")  # TODO How best to do this?!

    # Preparations . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    _log.info("Parsing additional command line arguments ...")
    update_dict, update_plots_cfg = parse_update_dicts(_mode="eval", **params)

    if update_dict:
        _log.note("Updates to meta configuration:\n\n%s", pformat(update_dict))

    model = utopya.Model(
        name=params["model_name"],
        bundle_label=params["label"],
    )

    run_cfg, plots_cfg = parse_run_and_plots_cfg(
        model=model,
        run_cfg=params["run_cfg"],
        plots_cfg=params["plots_cfg"],
        cfg_set=params["cfg_set"],
        _log=_log,
    )
    params["plots_cfg"] = plots_cfg
    params["update_plots_cfg"] = update_plots_cfg

    # Create frozen Multiverse; supplies similar interface as Multiverse
    mv = model.create_frozen_mv(
        run_dir=params["run_dir"], run_cfg_path=run_cfg, **update_dict
    )

    # Loading and evaluating . . . . . . . . . . . . . . . . . . . . . . . . .
    _load_and_eval(
        _log=_log,
        ctx=ctx,
        mv=mv,
        **params,
    )


# -----------------------------------------------------------------------------


def _load_and_eval(
    *,
    ctx,
    mv: Union["Multiverse", "FrozenMultiverse"],
    _log=log,
    **params,
):
    """Wrapper that takes care of loading and evaluating"""
    _log.progress(
        "Beginning evaluation: loading data and starting PlotManager ...\n"
    )

    # Loading data into the data tree and (optionally) showing it .............
    if not params["use_data_tree_cache"]:
        mv.dm.load_from_cfg()

    else:
        if not mv.dm.tree_cache_exists:
            mv.dm.load_from_cfg()
            mv.dm.dump()

        else:
            _log.hilight("Restoring tree from cache file ...")
            mv.dm.restore()

    if params["show_data_tree"] == "full":
        _log.info(mv.dm.tree)

    elif params["show_data_tree"] == "condensed":
        _log.info(mv.dm.tree_condensed)

    # Plotting ................................................................
    if not params["interactive"]:
        mv.pm.plot_from_cfg(
            plots_cfg=params["plots_cfg"],
            plot_only=params["plot_only"],
            **params["update_plots_cfg"],
        )

        if params["reveal_output"] and mv.pm.common_out_dir:
            _log.progress("Revealing output ...")
            _log.remark("Output directory:\n  %s", mv.pm.common_out_dir)
            click.launch(mv.pm.common_out_dir)

        _log.success("All done.\n")
        return

    # Interactive Plotting ....................................................
    # Carry over all args relevant for evaluation.
    args = sys.argv[2:]

    # For convenience, drop a potentially given run directory path argument,
    # which would have to be removed from the argument list manually otherwise.
    args = [arg for arg in args if arg not in ()]

    # ... and drop some other flags and combinations of shortcuts of flags
    # that will no longer be necessary.
    # NOTE This is a rather rudimentary approach and will probably not remove
    #      *all* possibly offending arguments. It's purely for convenience at
    #      this point. If there are remaining args that are not parseable, the
    #      parser in interactive plotting mode will complain and the input can
    #      be adjusted at that point.
    # TODO Do the inverse (white-listing) approach instead!
    args = [
        arg
        for arg in args
        if arg
        not in (
            #
            # Options
            "--cluster-mode",
            "--interactive",
            "-i",
            "--use-data-tree-cache",
            "--tc",
            "--show-data-tree",
            "--load-parallel",
            "-P",
            #
            # Combinations
            "-iP",
            "-Pi",
            #
            # Values
            ctx.params.get("run_cfg"),
            ctx.params.get("run_dir"),
            ctx.params["show_data_tree"],
        )
    ]

    # While in interactive mode, the following loop is carried out repeatedly.
    # A counter variable is used to label successive output directories.
    iap_session = 0

    while params["interactive"]:
        print("")
        _log.hilight("--- Interactive plotting session %d ---", iap_session)

        # Unless this is the very first session, need to prompt for new args.
        if iap_session > 0:
            # Provide some information on where the data is from; which is
            # useful if this is a very long session
            _log.remark(
                "Currently selected data directory:\n  %s", mv.dm.dirs["data"]
            )
            _log.note("Use Ctrl+C to exit. Use ↑/↓ for history.")

            # Prompt for new arguments . . . . . . . . . . . . . . . . . . . .
            try:
                args, params, ctx = _prompt_new_params(
                    old_args=args,
                    old_params=params,
                    old_ctx=ctx,
                    _log=_log,
                )

            except KeyboardInterrupt:
                # Ask for confirmation before quitting the plotting session.
                # This is to prohibit accidentally exiting the session, which
                # is especially relevant if loading data took a long time.
                print("\n")
                readline.set_startup_hook()
                _prompt = (
                    "{ansi.ORANGE}{ansi.BOLD}"
                    "Really exit interactive plotting session?"
                    "{ansi.RESET}"
                ).format(ansi=ANSIesc)

                try:
                    if click.confirm(_prompt):
                        break

                except (KeyboardInterrupt, click.exceptions.Abort):
                    pass

                print("\n")
                _log.success("Remaining in interactive plotting mode ...")
                continue

            except EOFError:
                # EOFError is invoked by builtins.input when the input is read
                # from a stream that is not the standard input stream. In such
                # a case, can't have a confirmation, so might as well exit.
                break

            except (SystemExit, click.exceptions.Exit):
                # This came from SystemExit or similar being raised during
                # prompting for new arguments, e.g. because of the --help flag.
                # ... just prompt again; error message was already shown
                continue

            except click.exceptions.UsageError as exc:
                _handle_interactive_plotting_exception(
                    exc,
                    _log=_log,
                    description="command line argument parsing",
                )
                continue

        # Get updated configurations . . . . . . . . . . . . . . . . . . . . .
        try:
            _, plots_cfg = parse_run_and_plots_cfg(
                model=mv.model,
                run_cfg=params["run_cfg"],
                plots_cfg=params["plots_cfg"],
                cfg_set=params["cfg_set"],
                _log=_log,
                _interactive_mode=True,
            )
            _, update_plots_cfg = parse_update_dicts(_mode="eval", **params)

            params["plots_cfg"] = plots_cfg
            params["update_plots_cfg"] = update_plots_cfg

        except Exception as exc:
            _handle_interactive_plotting_exception(
                exc,
                _log=_log,
                debug=params["debug"],
                description="parsing of new PlotManager arguments",
            )
            continue

        if update_plots_cfg:
            _log.note(
                "Updates to plot configuration:\n\n%s",
                pformat(update_plots_cfg),
            )

        # Create a new PlotManager . . . . . . . . . . . . . . . . . . . . . .
        # Uses a custom output directory (inside the regular eval directory)
        # and include the session number into it.
        # Also increments the session counter.
        try:
            mv.renew_plot_manager(
                out_dir=f"session{iap_session:03d}/",
                raise_exc=(params["debug"] >= 1),
            )

        except Exception as exc:
            _handle_interactive_plotting_exception(
                exc,
                _log=_log,
                debug=params["debug"],
                description="PlotManager renewal",
                remark=(
                    "Inspect the traceback for details and check that all "
                    "involved plot configuration files are using valid YAML."
                ),
            )
            continue

        finally:
            iap_session += 1
            print("")

        # Plotting . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        try:
            mv.pm.plot_from_cfg(
                plots_cfg=plots_cfg,
                plot_only=params["plot_only"],
                **update_plots_cfg,
            )

        except KeyboardInterrupt:
            print("")
            _log.caution("Interrupted current plotting session.")
            _log.progress("Remaining in interactive plotting mode ...")
            continue

        except Exception as exc:
            _handle_interactive_plotting_exception(
                exc,
                _log=_log,
                debug=params["debug"],
                description="interactive plotting",
            )
            continue

        # Reveal output . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        if params["reveal_output"] and mv.pm.common_out_dir:
            try:
                click.launch(mv.pm.common_out_dir)

            except Exception as exc:
                # This may fail for certain paths; it should not lead to the
                # plotting session being interrupted.
                _handle_interactive_plotting_exception(
                    exc,
                    _log=_log,
                    debug=params["debug"],
                    description="opening of output directory",
                )
                continue

        # End of interactive plotting loop . . . . . . . . . . . . . . . . . .

    print("\n")
    _log.success("Left interactive plotting session.\n")


def _handle_interactive_plotting_exception(
    exc: Exception,
    *,
    description: str,
    debug: int = None,
    remark: str = None,
    _log=log,
):
    """Helper function to handle exceptions during interactive plotting

    Args:
        exc (Exception): The exception to handle
        description (str): A context-like description that will be used in the
            log message
        debug (int, optional): The debug level. If this evaluates to True,
            a traceback will be shown. If given, regardless of value, there
            will be a note-level message that hints at the possibility of
            showing a traceback; if not given (i.e.: None, default), no such
            message will be shown.
        remark (str, optional): A remark-level message added after the error
            message was provided. Use this to hint at possible ways to address
            the error.
        _log (TYPE, optional): A logger-like instance to use for emitting all
            information.
    """
    if debug:
        _log.error("An error occured during %s!\n", description)
        traceback.print_exc()
        _log.note("Remove --debug flag to hide traceback.")

    else:
        _log.error(
            "An error occured during %s!\n\n%s%s%s: %s\n",
            description,
            ANSIesc.BOLD,
            exc.__class__.__name__,
            ANSIesc.RESET + ANSIesc.RED,
            str(exc),
        )
        _log.note("Add --help to show usage info.")
        if debug is not None:
            _log.note("Add --debug to show traceback.")

    if remark:
        _log.remark(remark)
    _log.progress("Remaining in interactive plotting mode ...")


def _prompt_new_params(
    *,
    old_args: List[str],
    old_params: dict,
    old_ctx: click.Context,
    _log=log,
) -> Tuple[list, dict, click.Context]:
    """Given some old arguments, prompts for new ones and returns a new
    list of argument values and the parsed argparse namespace result.

    Args:
        old_args (List[str]): The old argument value list
        old_params (dict): The old set of parsed arguments
        old_ctx (click.Context): The CLI context
        _log: A logger-like object

    Returns:
        Tuple[list, dict]: New argument value list and parsed arguments.

    Raises:
        ValueError: Upon error in parsing the new arguments.
    """
    # Create a new argument list for querying the user. For that, remove
    # those entries from the argss that are meant to be in the query.
    prefix_args = ("--interactive", old_params["model_name"])
    to_query = [arg for arg in old_args if arg not in prefix_args]
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

    # Prepare the new list of arguments
    add_args = input_res.split(" ") if input_res else []
    new_args = list(prefix_args) + add_args

    # Now let the click.Context create a new context, parsing the arguments
    # NOTE This may raise SystemExit or click.exceptions.Exit upon the --help
    #      argument or click.exceptions.UsageError if parsing failed!
    #      However, exception handling cannot happen here because the new
    #      context would not be usable. Thus, we let these propagate upwards.
    new_ctx = old_ctx.command.make_context(
        "utopya eval", args=copy.copy(new_args)
    )
    new_params = new_ctx.params

    # Check that bad arguments were not used
    defaults = {p.name: p.get_default(new_ctx) for p in new_ctx.command.params}
    bad_args = {
        arg: new_params[arg]
        for arg in INTERACTIVE_MODE_PROHIBITED_ARGS
        if new_params.get(arg) != defaults.get(arg)
    }
    if bad_args:
        raise click.exceptions.UsageError(
            "During interactive plotting, arguments that update the "
            "Multiverse meta-configuration cannot be used!\n"
            "Remove the offending argument{} (value shown in parentheses):\n{}"
            "".format(
                "s" if len(bad_args) != 1 else "",
                "\n".join({f"  {k}  ({v})" for k, v in bad_args.items()}),
            )
        )

    return new_args, new_params, new_ctx
