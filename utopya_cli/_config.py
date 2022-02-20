"""Utilities for the config-related CLI"""

import copy
import logging
import os

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


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
