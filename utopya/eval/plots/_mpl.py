"""This module provides matplotlib-related helper constructs"""

import copy
import logging
from typing import Union

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from dantro.plot import ColorManager
from matplotlib.legend_handler import HandlerPatch

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


class HandlerEllipse(HandlerPatch):
    """Custom legend handler to turn an ellipse handle into a legend key."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create_artists(
        self,
        legend,
        orig_handle,
        xdescent,
        ydescent,
        width,
        height,
        fontsize,
        trans,
    ):
        """Create an ellipse as a matplotlib artist object."""
        center = 0.5 * width - 0.5 * xdescent, 0.5 * height - 0.5 * ydescent
        p = mpatches.Ellipse(
            xy=center, width=height + xdescent, height=height + ydescent
        )
        self.update_prop(p, orig_handle, legend)
        p.set_transform(trans)
        return [p]
