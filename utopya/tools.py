"""Implements generally useful functions, partly by importing from
:py:mod:`dantro.tools`"""

import io
import logging
import os
import re
import subprocess
import sys
from datetime import timedelta
from typing import Any, Callable, Sequence, Tuple, Union

from dantro.tools import (
    IS_A_TTY,
    TTY_COLS,
    center_in_line,
    fill_line,
    format_time,
    make_columns,
    print_line,
    recursive_getitem,
    recursive_update,
)

from ._yaml import load_yml, write_yml, yaml

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# working on dicts ------------------------------------------------------------


def load_selected_keys(
    src: dict,
    *,
    add_to: dict,
    keys: Sequence[Tuple[str, type, bool]],
    err_msg_prefix: str = None,
    prohibit_unexpected: bool = True,
) -> None:
    """Loads (only) selected keys from dict ``src`` into dict ``add_to``.

    Args:
        src (dict): The dict to load values from
        add_to (dict): The dict to load values into
        keys (Sequence[Tuple[str, type, bool]]): Which keys to load, given
            as sequence of ``(key, allowed types, [required=False])`` tuples.
        err_msg_prefix (str): A description string, used in error message
        prohibit_unexpected (bool, optional): Whether to raise on keys
            that were unexpected, i.e. not given in ``keys`` argument.

    Raises:
        KeyError: On missing key in ``src``
        TypeError: On bad type of value in ``src``
        ValueError: On unexpected keys in ``src``
    """

    def unpack(spec) -> Tuple[str, Union[type, Sequence[type]], bool]:
        """Unpacks a schema entry into a 3-tuple"""
        if len(spec) == 3:
            k, allowed_types, required = spec
        else:
            k, allowed_types = spec
            required = False

        return k, allowed_types, required

    for spec in keys:
        k, allowed_types, required = unpack(spec)
        if k not in src:
            if not required:
                continue
            raise ValueError(
                "{}Missing required key: {}"
                "".format(err_msg_prefix + " " if err_msg_prefix else "", k)
            )

        if not isinstance(src[k], allowed_types):
            raise TypeError(
                "{}Bad type for value of '{}'! Expected "
                "{} but got {}: {}"
                "".format(
                    err_msg_prefix + " " if err_msg_prefix else "",
                    k,
                    allowed_types,
                    type(src[k]),
                    src[k],
                )
            )

        add_to[k] = src[k]

    if not prohibit_unexpected:
        return

    allowed_keys = tuple(unpack(spec)[0] for spec in keys)
    unexpected_keys = tuple(k for k in src if k not in allowed_keys)
    if unexpected_keys:
        raise ValueError(
            "{}Received unexpected keys: {}\n"
            "Expected only: {}"
            "".format(
                err_msg_prefix + " " if err_msg_prefix else "",
                ", ".join(unexpected_keys),
                ", ".join(allowed_keys),
            )
        )


def add_item(
    value,
    *,
    add_to: dict,
    key_path: Sequence[str],
    value_func: Callable = None,
    is_valid: Callable = None,
    ErrorMsg: Callable = None,
) -> None:
    """Adds the given value to the ``add_to`` dict, traversing the given key
    path. This operation happens in-place.

    Args:
        value: The value of what is to be stored. If this is a callable, the
            result of the call is stored.
        add_to (dict): The dict to add the entry to
        key_path (Sequence[str]): The path at which to add it
        value_func (Callable, optional): If given, calls it with ``value`` as
            argument and uses the return value to add to the dict
        is_valid (Callable, optional): Used to determine whether ``value`` is
            valid or not; should take single positional argument, return bool
        ErrorMsg (Callable, optional): A raisable object that prints an error
            message; gets passed ``value`` as positional argument.

    Raises:
        Exception: type depends on specified ``ErrorMsg`` callable
    """
    # Check the value by calling the function; it should raise an error
    if is_valid is not None:
        if not is_valid(value):
            raise ErrorMsg(value)

    # Determine which keys need to be traversed
    traverse_keys, last_key = key_path[:-1], key_path[-1]

    # Set the starting point
    d = add_to

    # Traverse keys
    for _key in traverse_keys:
        # Check if a new entry is needed
        if _key not in d:
            d[_key] = dict()

        # Select the new entry
        d = d[_key]

    # Now d is where the value should be added
    # If applicable
    if value_func is not None:
        value = value_func(value)

    # Store in dict, mutable. Done.
    d[last_key] = value


# -- String formatting --------------------------------------------------------


def pprint(obj: Any, **kwargs):
    """Prints a "pretty" string representation of the given object.

    Args:
        obj (Any): The object to print
        **kwargs: Passed to print
    """
    print(pformat(obj), **kwargs)


def pformat(obj: Any) -> str:
    """Creates a "pretty" string representation of the given object.

    This is achieved by creating a yaml representation.

    .. todo::

        Improve parsing of leaf-level mappings
    """
    sstream = io.StringIO("")
    yaml.dump(obj, stream=sstream)
    sstream.seek(0)
    return sstream.read()


# misc ------------------------------------------------------------------------


def parse_si_multiplier(s: str) -> int:
    """Parses a string like ``1.23M`` or ``-2.34 k`` into an integer.

    If it is a string, parses the SI multiplier and returns the appropriate
    integer for use as number of simulation steps.
    Supported multipliers are ``k``, ``M``, ``G`` and ``T``. These need to be
    used as the suffix of the string.

    .. note::

        This is only intended to be used with integer values and does *not*
        support float values like ``1u``.

    The used regex can be found `here <https://regex101.com/r/xngAoc/1>`_.

    Args:
        s (str): A string representing an integer number, potentially including
            a supported SI multiplier as *suffix*.

    Returns:
        int: The parsed number of steps as integer. If the value has decimal
            places, integer rounding is applied.

    Raises:
        ValueError: Upon string that does not match the expected pattern
    """
    SUFFIXES = dict(k=1e3, M=1e6, G=1e9, T=1e12)
    pattern = r"^(?P<value>\-?\s?\d+|\-?\s?\d+\.\d+)?\s?(?P<suffix>[kMGT])?$"
    # See:  https://regex101.com/r/xngAoc/1

    match = re.match(pattern, s.strip())
    if not match:
        raise ValueError(
            f"Cannot parse '{s}' into an integer! May only contain the metric "
            "suffixes k, M, G, or T. Examples: 1000, 1k, 1.23M, 0.5 G"
        )

    groups = match.groupdict()
    val = float(groups["value"].replace(" ", ""))
    mul = SUFFIXES[groups["suffix"]] if groups["suffix"] else 1

    return int(val * mul)


def parse_num_steps(
    N: Union[str, int], *, raise_if_negative: bool = True
) -> int:
    """Given a string like ``1.23M`` or an integer, prepares the num_steps
    argument for a single universe simulation.

    For string arguments, uses :py:func:`~utopya.tools.parse_si_multiplier` for
    string parsing. If that fails, attempts to read it in float notation by
    calling ``int(float(N))``.

    .. note:: This function always applies integer rounding.

    Args:
        N (Union[str, int]): The ``num_steps`` argument as a string or integer.
        raise_if_negative (bool, optional): Whether to raise an error if the
            value is negative.

    Returns:
        int: The parsed value for ``num_steps``

    Raises:
        ValueError: Result invalid, i.e. not parseable or of negative value.
    """
    if isinstance(N, str):
        try:
            N = parse_si_multiplier(N)

        except ValueError as err:
            # Don't give up just yet, could still be in scientific notation ...
            try:
                N = int(float(N))

            except:
                # Ok, that also failed. Giving up now.
                raise ValueError(f"Failed parsing `num_steps`: {err}") from err

    if raise_if_negative and N < 0:
        raise ValueError(
            f"Argument `num_steps` needs to be non-negative, but was {N}!"
        )

    return N
