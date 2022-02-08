"""Implements utopya's PlotHelper specialization"""

import dantro


class PlotHelper(dantro.plot_creators.PlotHelper):
    """A specialization of the dantro ``PlotHelper`` used in plot creators that
    are derived from ``ExternalPlotCreator``.

    This can be used to add additional helpers for use in Utopia without
    requiring changes on dantro-side.

    .. note::

        The helpers implemented here should try to adhere to the interface
        exemplified by the dantro ``PlotHelper`` class, with the aim that they
        can then be migrated into dantro in the long run.
    """

    # .. Helper methods .......................................................
    # Can add helper methods here, prefixed with _hlpr_
