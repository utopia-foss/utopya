"""Implements data group classes specific to the Utopia output data structure.

They are based on dantro BaseDataGroup-derived implementations. In this module,
they are imported and configured using class variables.
"""

import logging

import numpy as np

import dantro as dtr
import dantro.groups

from .datacontainer import NumpyDC, XarrayDC

# Configure and get logger
log = logging.getLogger(__name__)

# Local constants

# -----------------------------------------------------------------------------

class UniverseGroup(dtr.groups.ParamSpaceStateGroup):
    """This group represents the data of a single universe"""

    def get_times_array(self) -> np.ndarray:
        """Constructs a 1D np.array using the information from this universe's
        configuration, i.e. the ``num_steps``, ``write_start``, and
        ``write_every`` keys.

        NOTE That this data is retrieved from the universe's _top level_
             configuration. If the ``write_start`` and ``write_every``
             parameters were set differently within a model or the model does
             not use ``basic`` WriteMode, this group cannot know that.
        
        Returns:
            np.ndarray: The array of time coordinates
        """
        # Check if a configuration was loaded
        try:
            cfg = self['cfg']

        except KeyError as err:
            raise ValueError("No configuration associated with {}! Check the "
                             "load configuration of the root DataManager or "
                             "manually add a configuration container.   "
                             "".format(self.logstr)) from err
        
        # Retrieve the necessary parameters from the configuration
        write_start = cfg.get('write_start', 0)
        write_every = cfg.get('write_every', 1)
        num_steps = cfg['num_steps']

        # Combine these to a range expression, including the last time step
        return np.arange(write_start, num_steps + 1, write_every)


class MultiverseGroup(dtr.groups.ParamSpaceGroup):
    """This group is meant to manage the `uni` group of the loaded data, i.e.
    the group where output of all universe groups is stored in.

    Its main aim is to provide easy access to universes. By default, universes
    are only identified by their ID, which is a zero-padded _string_. This
    group adds the ability to access them via integer indices.

    Furthermore, via dantro, an easy data selector is available
    """
    _NEW_GROUP_CLS = UniverseGroup


class NetworkGroup(dtr.groups.NetworkGroup):
    """This group is meant to manage network data and create a NetworkX graph
    from it."""
    # Allow only Numpy Data Containers for now # FIXME
    _NEW_CONTAINER_CLS = NumpyDC

    # Define allowed member container types
    _ALLOWED_CONT_TYPES = (NumpyDC,)

    # Expected names for the containers that hold vertex/edge information
    _NWG_node_container = "_vertices"
    _NWG_edge_container = "_edges"

    # Expected _group_ attribute names determining the type of graph
    _NWG_attr_directed = "is_directed"
    _NWG_attr_parallel = "is_parallel"
