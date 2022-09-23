"""This module provides matplotlib-related helper constructs"""

import copy
import logging
from typing import Tuple, Union

import matplotlib as mpl
import matplotlib.patches as mpatches
import numpy as np
from dantro.plot import ColorManager
from matplotlib.legend_handler import HandlerPatch

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


def adjust_figsize_to_aspect(
    aspect: float, *, fig: "matplotlib.figure.Figure"
) -> Tuple[float, float]:
    """Adjusts the given figures size, *enlarging* it to match the given aspect
    ratio where ``width = height * aspect``.

    Args:
        aspect (float): The aspect ratio ``width / height``
        fig (matplotlib.figure.Figure): The figure

    Returns:
        Tuple[float, float]:
            New width and height of the figure in inches.
    """
    w, h = fig.get_size_inches()
    if w < h * aspect:
        w = h * aspect
    else:
        h = w / aspect
    fig.set_size_inches(w, h)
    return fig.get_size_inches()


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
