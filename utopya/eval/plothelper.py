"""Implements utopya's PlotHelper specialization"""

import dantro.plot


class PlotHelper(dantro.plot.PlotHelper):
    """A specialization of dantro's
    :py:class:`~dantro.plot.plot_helper.PlotHelper` which is used for creating
    :py:mod:`matplotlib.pyplot`-based plots using
    :py:class:`~utopya.eval.plotcreators.PyPlotCreator`.

    This can be used to add additional helpers for use in utopya without
    requiring changes to dantro.

    .. note::

        The helpers implemented here should try to adhere to the interface
        exemplified by the dantro
        :py:class:`~dantro.plot.plot_helper.PlotHelper`, with the aim that they
        can then be migrated into dantro in the long run.
    """

    # .. Helper methods .......................................................
    # Can add helper methods here, prefixed with _hlpr_
