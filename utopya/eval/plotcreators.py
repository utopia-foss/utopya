"""Implements utopya-specializations of :py:mod:`dantro.plot.creators`"""

import logging

import dantro
import dantro.plot.creators

from .plothelper import PlotHelper

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class PyPlotCreator(dantro.plot.creators.PyPlotCreator):
    """This is the Utopia-specific version of dantro's
    :py:class:`~dantro.plot.creators.pyplot.PyPlotCreator`.

    Its main purpose is to define common settings for plotting. By adding this
    extra layer, it allows for future extensibility as well.
    """

    EXTENSIONS = "all"
    """Which file extensions to support.
    A value of ``all`` leads to no checks being performed on the extension.
    """

    DEFAULT_EXT = "pdf"
    """Default plot file extension"""

    PLOT_HELPER_CLS = PlotHelper
    """The PlotHelper class to use; here, the utopya-specific one"""


class UniversePlotCreator(
    dantro.plot.creators.UniversePlotCreator, PyPlotCreator
):
    """Makes plotting with data from a single universe more convenient"""

    PSGRP_PATH: str = "multiverse"
    """The path within the data tree to arrive at the
    :py:class:`~utopya.eval.groups.MultiverseGroup` that this plot creator
    expects universes to be located *in*.
    """


class MultiversePlotCreator(
    dantro.plot.creators.MultiversePlotCreator, PyPlotCreator
):
    """Makes plotting with data from *all* universes more convenient"""

    PSGRP_PATH: str = "multiverse"
    """The path within the data tree to arrive at the
    :py:class:`~utopya.eval.groups.MultiverseGroup`.
    """
