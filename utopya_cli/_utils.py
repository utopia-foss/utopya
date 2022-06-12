"""Various utilities used within the CLI definition and for handling click"""

import copy
import logging
import os
import sys
from typing import Tuple

import click
import paramspace as psp

log = logging.getLogger(__name__)
# FIXME This logger does not support all levels that are used throughout this
#       module, because it is setup prior to the utopya import.

# -----------------------------------------------------------------------------
# Communication via Terminal
# TODO Consider mapping directly to logger?


class ANSIesc:
    """Some selected ANSI escape codes; usable in format strings"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    ORANGE = "\033[38;5;202m"


def _parse_msg(msg: str, args) -> str:
    if args:
        return msg % args
    return msg


class Echo:
    """Adds some standardized styled ``click.echo`` calls.

    The styles are aligned with those set in the utopya.logging module.
    """

    @staticmethod
    def help(*, exit: int = None):
        """Shows the help message of the current context"""
        click.echo(click.get_current_context().get_help())
        if exit is not None:
            sys.exit(exit)

    @staticmethod
    def trace(msg: str, *args, dim=True, **style):
        """An echo that communicates some debug-level information"""
        click.secho(_parse_msg(msg, args), dim=dim, **style)

    @staticmethod
    def debug(msg: str, *args, dim=True, **style):
        """An echo that communicates some debug-level information"""
        click.secho(_parse_msg(msg, args), dim=dim, **style)

    @staticmethod
    def remark(msg: str, *args, fg=246, **style):
        """An echo that communicates some low-level information"""
        click.secho(_parse_msg(msg, args), fg=fg, **style)

    @staticmethod
    def note(msg: str, *args, fg="cyan", **style):
        """An echo that communicates some low-level information"""
        click.secho(_parse_msg(msg, args), fg=fg, **style)

    @staticmethod
    def info(msg: str, *args, **style):
        """An echo that communicates some information"""
        click.secho(_parse_msg(msg, args), **style)

    @staticmethod
    def progress(msg: str, *args, fg="green", **style):
        """An echo that communicates some progress"""
        click.secho(_parse_msg(msg, args), fg=fg, **style)

    @staticmethod
    def caution(msg: str, *args, fg=202, **style):
        """An echo that communicates a cautioning message"""
        click.secho(_parse_msg(msg, args), fg=fg, **style)

    @staticmethod
    def hilight(msg: str, *args, fg="yellow", bold=True, **style):
        """An echo that highlights a certain"""
        click.secho(_parse_msg(msg, args), fg=fg, bold=bold, **style)

    @staticmethod
    def success(msg: str, *args, fg="green", bold=True, **style):
        """An echo that communicates a success"""
        click.secho(_parse_msg(msg, args), fg=fg, bold=bold, **style)

    @staticmethod
    def warning(msg: str, *args, fg=202, bold=True, **style):
        """An echo that communicates a warning"""
        click.secho(_parse_msg(msg, args), fg=fg, bold=bold, **style)

    @staticmethod
    def error(
        msg: str,
        *args,
        error: Exception = None,
        fg="red",
        bold=True,
        **style,
    ):
        """An echo that can be used to communicate an error, optionally
        parsing the exception's error msg as well.
        """
        click.secho(_parse_msg(msg, args), fg=fg, bold=bold, **style)
        if not error:
            return

        click.secho(
            f"{type(error).__name__}: {error}", fg=fg, bold=False, **style
        )


# -----------------------------------------------------------------------------
# Parsing of key-value pairs


class _DEL:
    """Objects of this class symbolize deletion"""

    def __str__(self) -> str:
        return "<DELETION MARKER>"


DEL = _DEL()
"""An object denoting deletion"""


def convert_value(
    val: str,
    *,
    allow_deletion: bool = True,
    allow_yaml: bool = False,
    allow_eval: bool = False,
):
    """Attempts a number of conversions for a given string

    .. todo::

        Should this be here or is there a simpler way to do this?

    Args:
        val (str): Description
        allow_deletion (bool, optional): If set, can pass a ``DELETE`` string
            to a key to remove the corresponding entry.
        allow_yaml (bool, optional): Whether to attempt converting values
            by employing a YAML parser
        allow_eval (bool, optional): Whether to try calling eval() on the
            value strings during conversion
    """
    # Boolean
    if val.lower() in ("true", "false"):
        return bool(val.lower() == "true")

    # None
    if val.lower() == "null":
        return None

    # Numbers
    try:
        return int(val)
    except:
        try:
            return float(val)
        except:
            pass

    # Deletion placeholder
    if val == "DELETE":
        return DEL

    # YAML
    if allow_yaml:
        from utopya.yaml import yaml

        try:
            return yaml.load(val)
        except:
            pass

    # Last resort, if allowed: eval
    if allow_eval:
        try:
            return eval(val)
        except:
            pass

    # Just return the string
    return val


def set_entries_from_kv_pairs(
    *pairs,
    add_to: dict,
    _log=log,
    attempt_conversion: bool = True,
    **conversion_kwargs,
) -> None:
    """Parses the given ``key=value`` pairs and adds them to the given dict.

    .. note::

        This happens directly on the ``add_to`` object, i.e. making use of the
        mutability of the given dict. This function has no return value!

    Args:
        *pairs: Sequence of key=value strings
        add_to (dict): The dict to add the pairs to
        _log (TYPE, optional): A logger-like object
        attempt_conversion (bool, optional): Whether to attempt converting the
            strings to bool, float, int, and other types.
        **conversion_kwargs: Passed on to the conversion function,
            :py:func:`~utopya_cli._utils.convert_value`

    """

    _log.remark(
        "Parsing %d key-value pair%s ...",
        len(pairs),
        "s" if len(pairs) != 1 else "",
    )

    # Go over all pairs and add them to the given base dict
    for kv in pairs:
        key, val = kv.split("=", 1)

        # Process the key and traverse through the dict, already creating new
        # entries if needed. The resulting `d` will be the dict where the value
        # is written to (or deleted from).
        key_sequence = key.split(".")
        traverse_keys, last_key = key_sequence[:-1], key_sequence[-1]

        d = add_to
        for _key in traverse_keys:
            if _key not in d:
                d[_key] = dict()

            d = d[_key]

        # Process the value
        if attempt_conversion:
            val = convert_value(val, **conversion_kwargs)

        _log.remark("  %s  \t->   %s: %s", kv, ".".join(key_sequence), val)

        # Write or delete the entry
        if val is not DEL:
            if not isinstance(val, dict):
                d[last_key] = val

            else:
                from utopya.tools import recursive_update

                d[last_key] = recursive_update(
                    copy.deepcopy(d.get(last_key, {})),
                    val,
                )

        else:
            if last_key not in d:
                continue
            del d[last_key]


# -----------------------------------------------------------------------------
# Custom argument parsing


def parse_run_and_plots_cfg(
    *,
    model: "utopya.model.Model",
    run_cfg: str,
    plots_cfg: str,
    cfg_set: str,
    _interactive_mode: bool = False,
    _log=log,
) -> Tuple[str, str]:
    """Extracts paths to the run configuration and plots configuration by
    looking at the given arguments and the model's configuration sets.

    If ``_interactive_mode`` is given, will not read the run configuration but
    only the plots configuration where it would be confusing to have the
    corresponding log message appear. Also, in interactive mode, this will not
    lead to system exit if parsing failed.
    """
    if cfg_set and (run_cfg is None or plots_cfg is None):
        _log.info("Looking up config set '%s' ...", cfg_set)
        try:
            cfg_set = model.get_config_set(cfg_set)

        except ValueError as err:
            if _interactive_mode:
                raise
            _log.error(err)
            sys.exit(1)

        # Explicitly given arguments take precedence. Also, the config set may
        # not contain a run or eval configuration.
        if run_cfg is None and cfg_set.get("run"):
            if not _interactive_mode:
                run_cfg = cfg_set["run"]
                _log.note("  Using run.yml from config set.")
            else:
                _log.remark(
                    "  Not using run.yml in interactive plotting mode."
                )

        if plots_cfg is None and cfg_set.get("eval"):
            plots_cfg = cfg_set["eval"]
            _log.note("  Using eval.yml from config set.")

    return run_cfg, plots_cfg


def parse_update_dicts(
    *, _mode: str, _log=log, **all_arguments
) -> Tuple[dict, dict]:
    """Parses the given arguments, extracting update dictionaries for the
    Multiverse and the plots configuration

    Args:
        _mode (str): The mode argument. Can be ``run`` or ``eval``

    Returns:
        Tuple[dict, dict]: Multiverse update config and plots update config
    """
    from types import SimpleNamespace

    from utopya.tools import add_item

    # Make attribute access possible for arguments by using SimpleNamespace
    args = SimpleNamespace(**all_arguments)

    # To-be-populated update dicts:
    update_dict = {}
    update_plots_cfg = {}

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # TODO Take into account framework-level defaults
    # TODO Make use of additional debug levels to select more verbose output
    if args.debug >= 1:
        # Set model log level to DEBUG and let PlotManager and WorkerManager
        # raise exceptions
        add_item(
            "debug",
            add_to=update_dict,
            key_path=("parameter_space", "log_levels", "model"),
        )
        add_item(
            True,
            add_to=update_dict,
            key_path=("plot_manager", "raise_exc"),
        )
        add_item(
            "raise",
            add_to=update_dict,
            key_path=("worker_manager", "nonzero_exit_handling"),
        )

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Arguments relevant only in run mode
    if _mode == "run":
        if args.note:
            add_item(
                args.note, add_to=update_dict, key_path=("paths", "model_note")
            )

        # TODO Replacement?
        # if args.sim_errors:
        #     add_item(
        #         args.sim_errors,
        #         add_to=update_dict,
        #         key_path=["worker_manager", "nonzero_exit_handling"],
        #     )

        if args.validate is not None:
            add_item(
                args.validate,
                add_to=update_dict,
                key_path=("perform_validation",),
            )

        if args.num_steps is not None:
            add_item(
                args.num_steps,
                add_to=update_dict,
                key_path=("parameter_space", "num_steps"),
            )

        if args.write_every is not None:
            add_item(
                args.write_every,
                add_to=update_dict,
                key_path=("parameter_space", "write_every"),
            )

        if args.write_start is not None:
            add_item(
                args.write_start,
                add_to=update_dict,
                key_path=("parameter_space", "write_start"),
            )

        if args.num_seeds is not None:
            add_item(
                args.num_seeds,
                value_func=lambda v: psp.ParamDim(default=42, range=[v]),
                add_to=update_dict,
                key_path=("parameter_space", "seed"),
                is_valid=lambda v: bool(v >= 1),
                ErrorMsg=lambda v: ValueError(
                    f"Argument --num-seeds needs to be ≥ 1, was {v}."
                ),
            )
            add_item(True, add_to=update_dict, key_path=("perform_sweep",))

        if args.run_mode is not None:
            add_item(
                args.run_mode == "sweep",
                add_to=update_dict,
                key_path=("perform_sweep",),
            )

        if args.set_model_params:
            # TODO More elegant solution?
            if not update_dict.get("parameter_space"):
                update_dict["parameter_space"] = dict()

            if not update_dict["parameter_space"].get(args.model_name):
                update_dict["parameter_space"][args.model_name] = dict()

            set_entries_from_kv_pairs(
                *args.set_model_params,
                add_to=update_dict["parameter_space"][args.model_name],
                _log=_log,
            )

        if args.set_pspace_params:
            if not update_dict.get("parameter_space"):
                update_dict["parameter_space"] = dict()

            set_entries_from_kv_pairs(
                *args.set_pspace_params,
                add_to=update_dict["parameter_space"],
                _log=_log,
            )

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Arguments relevant *only* in eval mode
    elif _mode == "eval":
        # Can add eval-specific arugments here
        pass

    else:
        raise ValueError(f"Bad mode '{mode}'! Needs be: run or eval")

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Evaluate arguments that apply to both run and eval modes
    if args.load_parallel is not None:
        add_item(
            args.load_parallel,
            add_to=update_dict,
            key_path=("data_manager", "load_cfg", "data", "parallel"),
        )

    if args.cluster_mode is not None:
        add_item(
            args.cluster_mode,
            add_to=update_dict,
            key_path=("cluster_mode",),
        )

    if args.set_params:
        set_entries_from_kv_pairs(
            *args.set_params,
            add_to=update_dict,
            _log=_log,
        )

    if args.update_plots_cfg:
        try:
            set_entries_from_kv_pairs(
                *args.update_plots_cfg,
                add_to=update_plots_cfg,
                _log=_log,
            )

        except ValueError:
            from utopya.yaml import load_yml

            update_plots_cfg = load_yml(*args.update_plots_cfg)
            # FIXME needs to cover case where update_plots_cfg has more than
            #       a single argument

    return update_dict, update_plots_cfg
