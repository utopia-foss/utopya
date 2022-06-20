"""Implements specialized data group classes that are based on group types
provided in :py:mod:`dantro.groups`.
Here, they are configured using their class variables.
"""

import logging

import dantro
import dantro.groups

from .containers import XarrayDC as _XarrayDC

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class UniverseGroup(dantro.groups.ParamSpaceStateGroup):
    """This group represents the data of a single universe"""


class MultiverseGroup(dantro.groups.ParamSpaceGroup):
    """This group is meant to manage the ``multiverse`` group of the loaded
    data, i.e. the group where output of the individual
    :py:class:`~utopya.eval.groups.UniverseGroup` objects is stored in.

    Its main aim is to provide easy access to universes. By default, universes
    are only identified by their ID, which is a zero-padded *string*. This
    group adds the ability to access them via integer indices.

    Furthermore, via dantro, an easy data selector method is available, see
    :py:meth:`dantro.groups.psp.ParamSpaceGroup.select`.
    """

    _NEW_GROUP_CLS = UniverseGroup


class TimeSeriesGroup(dantro.groups.TimeSeriesGroup):
    """This group is meant to manage time series data, with the container names
    being interpreted as the time coordinate.
    """

    _NEW_CONTAINER_CLS = _XarrayDC


class HeterogeneousTimeSeriesGroup(dantro.groups.HeterogeneousTimeSeriesGroup):
    """This group is meant to manage time series data, with the container names
    being interpreted as the time coordinate.
    """

    _NEW_CONTAINER_CLS = _XarrayDC


class GraphGroup(dantro.groups.GraphGroup):
    """This group is meant to manage graph data and create a NetworkX graph
    from it.
    """

    # Let new groups contain only time series
    _NEW_GROUP_CLS = TimeSeriesGroup

    # Define allowed member container types
    _ALLOWED_CONT_TYPES = (TimeSeriesGroup, _XarrayDC)

    # Expected names for the containers that hold vertex/edge information
    _GG_node_container = "_vertices"
    _GG_edge_container = "_edges"

    # _group_ attribute names for optionally providing additional information
    # on the graph.
    _GG_attr_directed = "is_directed"
    _GG_attr_parallel = "allows_parallel"
    _GG_attr_edge_container_is_transposed = "edge_container_is_transposed"
    _GG_attr_keep_dim = "keep_dim"

    # Whether warning is raised upon bad alignment of property data
    _GG_WARN_UPON_BAD_ALIGN = True
