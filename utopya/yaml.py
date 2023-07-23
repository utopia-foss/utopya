"""Takes care of the YAML setup for Utopya.

In the module import order, this module needs to be downstream from all modules
that implement objects that require a custom YAML representation."""

import logging

import yayaml as yay

from ._yaml import load_yml, write_yml, yaml
from .model_registry import ModelInfoBundle, ModelRegistryEntry
from .parameter import Parameter
from .stop_conditions import StopCondition

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


def _parameter_shorthand_constructor(loader, node) -> Parameter:
    """Constructs a Parameter object from a scalar YAML node using
    :py:func:`~yayaml.constructors.scalar_node_to_object`.

    The YAML tag is used as shorthand ``mode`` argument to the
    :py:class:`~utopya.parameter.Parameter.from_shorthand` class method.
    """
    return Parameter.from_shorthand(
        yay.scalar_node_to_object(loader, node),
        mode=node.tag[1:],
    )


# -- Attaching additional representers and constructors -----------------------

# First register the classes which directly implemented dumping/loading
yaml.register_class(StopCondition)
yaml.register_class(ModelInfoBundle)
yaml.register_class(ModelRegistryEntry)
yaml.register_class(Parameter)


# Register the Parameter shorthand constructors
# NOTE The regular constructors and representers are already registered using
#      the call to yaml.register_class above
for mode in Parameter.SHORTHAND_MODES:
    yaml.constructor.add_constructor(
        "!" + mode, _parameter_shorthand_constructor
    )
