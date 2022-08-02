"""Takes care of the YAML setup for Utopya.

In the module import order, this module needs to be downstream from all modules
that implement objects that require a custom YAML representation."""

import functools
import logging
import re
from typing import Callable, Tuple

import numpy as np
import paramspace.yaml_constructors as pspyc
import ruamel.yaml

from ._yaml import load_yml, write_yml, yaml
from .model_registry import ModelInfoBundle, ModelRegistryEntry, load_model_cfg
from .parameter import Parameter
from .stop_conditions import StopCondition
from .tools import recursive_update as _recursive_update

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


def _scalar_node_to_object(loader, node):
    """Attempts to convert the given scalar node to a null (Python None),
    a bool, an int, or a float object using the corresponding YAML constructor.
    If those conversions fail, constructs a scalar (which will typically result
    in a string being returned).
    """

    def construct_yaml_null(node) -> None:
        """Constructs a None from an appropriate YAML node.

        This custom constructor should not be necessary, but for some weird
        reason, the ruamel.yaml constructor from loader.construct_yaml_null
        *always* returns None, regardless of the value of the node. As we rely
        on errors being raised if construction fails, we need this custom
        constructor for the two explicitly allowed null values.
        """
        if node.value in ("~", "null"):
            return None
        raise ruamel.yaml.constructor.ConstructorError(
            f"expected null, but " f"got '{node.value}'"
        )

    for constructor in (
        loader.construct_yaml_bool,
        loader.construct_yaml_int,
        loader.construct_yaml_float,
        construct_yaml_null,
        loader.construct_yaml_str,
    ):
        try:
            return constructor(node)
        except:
            pass

    return loader.construct_scalar(node)


# -----------------------------------------------------------------------------


def _expr_constructor(loader, node):
    """Custom pyyaml constructor for evaluating strings with simple
    mathematical expressions.

    Supports: +, -, *, **, /, e-X, eX, inf, nan
    """
    # get expression string
    expr_str = loader.construct_scalar(node)

    # Remove spaces
    expr_str = expr_str.replace(" ", "")

    # Parse some special strings
    if expr_str in ["nan", "NaN"]:
        return float("nan")

    # NOTE these will cause errors if emitted file is not read by python!
    elif expr_str in ["np.inf", "inf", "INF"]:
        return np.inf

    elif expr_str in ["-np.inf", "-inf", "-INF"]:
        return -np.inf

    # remove everything that might cause trouble -- only allow digits, dot, +,
    # -, *, /, and eE to allow for writing exponentials, and parentheses
    expr_str = re.sub(r"[^0-9eE\-.+\*\/\(\)]", "", expr_str)

    # Try to eval
    return eval(expr_str)


def _func_on_sequence_constructor(loader, node, *, func: Callable):
    """Custom yaml constructor that constructs a sequence, passes it to the
    given function, and returns the result of that call.

    Can be used e.g. in conjunction with the any and all functions, evaluating
    sequences of booleans.
    """
    # Get a sequence from the node
    s = loader.construct_sequence(node, deep=True)
    return func(s)


def _parameter_shorthand_constructor(loader, node) -> Parameter:
    """Constructs a Parameter object from a scalar YAML node using
    :py:func:`~utopya.yaml._scalar_node_to_object`.

    The YAML tag is used as shorthand ``mode`` argument to the
    :py:class:`~utopya.parameter.Parameter.from_shorthand` class method.
    """
    return Parameter.from_shorthand(
        _scalar_node_to_object(loader, node), mode=node.tag[1:]
    )


# -----------------------------------------------------------------------------
# Attaching representers and constructors

# First register the classes which directly implemented dumping/loading
yaml.register_class(StopCondition)
yaml.register_class(ModelInfoBundle)
yaml.register_class(ModelRegistryEntry)
yaml.register_class(Parameter)

# Now, add (additional, potentially overwriting) constructors for certain tags.
# Evaluate a mathematical expression
yaml.constructor.add_constructor("!expr", _expr_constructor)

# Apply the any operator to a sequence
yaml.constructor.add_constructor(
    "!any", functools.partial(_func_on_sequence_constructor, func=any)
)

# Apply the all operator to a sequence
yaml.constructor.add_constructor(
    "!all", functools.partial(_func_on_sequence_constructor, func=all)
)


# Add aliases for the (coupled) parameter dimensions
yaml.constructor.add_constructor("!sweep", pspyc.pdim)
yaml.constructor.add_constructor("!sweep-default", pspyc.pdim_default)

yaml.constructor.add_constructor("!coupled-sweep", pspyc.coupled_pdim)
yaml.constructor.add_constructor(
    "!coupled-sweep-default", pspyc.coupled_pdim_default
)


# Register the Parameter shorthand constructors
# NOTE The regular constructors and representers are already registered using
#      the call to yaml.register_class above
for mode in Parameter.SHORTHAND_MODES:
    yaml.constructor.add_constructor(
        "!" + mode, _parameter_shorthand_constructor
    )

# Set the flow style
yaml.default_flow_style = False
