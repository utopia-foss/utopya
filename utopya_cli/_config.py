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

    # Floating point number (requiring '.' being present)
    import re

    if re.match(r"^[-+]?[0-9]*\.[0-9]*([eE][-+]?[0-9]+)?$", val):
        try:
            return float(val)
        except:
            pass

    # Integer
    if re.match(r"^[-+]?[0-9]+$", val):
        try:
            return int(val)
        except:  # very unlike to be reached; regex is quite restrictive
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
            # FIXME Fails if d is not a dict

            if _key not in d:
                d[_key] = dict()

            d = d[_key]

        # Process the value
        if attempt_conversion:
            val = convert_value(val, **conversion_kwargs)

        _log.remark("  %s   ->   %s: %s", kv, ".".join(key_sequence), val)

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


def deploy_user_cfg(
    user_cfg_path: str = "~/.config/utopya/user_cfg.yml",  # TODO load
) -> None:
    """Deploys a copy of the full config to the specified location

    Instead of just copying the full config, it is written line by line,
    commenting out lines that are not already commented out, and changing the
    header.

    Args:
        user_cfg_path (str, optional): The path the user config file is
            expected at

    Returns:
        None
    """
    # Check if a user config already exists and ask if it should be overwritten
    if os.path.isfile(user_cfg_path):
        print("A config file already exists at " + str(user_cfg_path))
        if input("Replace? [y, N]  ").lower() in ["yes", "y"]:
            os.remove(user_cfg_path)
            print("")

        else:
            print("Not deploying user config.")
            return

    # At this point, can assume that it is desired to write the file and there
    # is no other file there.
    # Make sure that the folder exists
    os.makedirs(os.path.dirname(user_cfg_path), exist_ok=True)

    # Create a file at the given location
    with open(user_cfg_path, "x") as ucfg:
        # Write header section, from user config header file
        with open(USER_CFG_HEADER_PATH) as ucfg_header:
            ucfg.write(ucfg_header.read())

        # Now go over the full config and write the content, commenting out
        # the lines that are not already commented out
        with open(BASE_CFG_PATH) as bcfg:
            past_prefix = False

            for line in bcfg:
                # Look for "---" to find out when the header section ended
                if line == "---\n":
                    past_prefix = True
                    continue

                # Write only if past the prefix
                if not past_prefix:
                    continue

                # Check if the line in the target (user) config needs to be
                # commented out or not
                if line.strip().startswith("#") or line.strip() == "":
                    # Is a comment or empty line -> just write it
                    ucfg.write(line)

                else:
                    # There is an entry on this line -> comment out before the
                    # first character (looks cleaner)
                    spaces = " " * (len(line.rstrip()) - len(line.strip()))
                    ucfg.write(spaces + "# " + line[len(spaces) :])

    print(
        f"Deployed user config to: {user_cfg_path}\n\n"
        "All entries are commented out; open the file to edit your "
        "configuration. Note that it is wise to only uncomment those entries "
        "that you absolutely *need* to set."
    )
