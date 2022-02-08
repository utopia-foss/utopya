"""Implements basic generic plot universe plot functions"""

import logging
from typing import Tuple, Union

from .. import DataManager, UniverseGroup
from . import PlotHelper, UniversePlotCreator, is_plot_func

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


@is_plot_func(creator_type=UniversePlotCreator)
def lineplot(
    dm: DataManager,
    *,
    uni: UniverseGroup,
    hlpr: PlotHelper,
    model_name: str,
    path_to_data: Union[str, Tuple[str, str]],
    **plot_kwargs,
):
    """Performs an errorbar plot of a specific universe.

    Args:
        dm (DataManager): The data manager from which to retrieve the data
        uni (UniverseGroup): The data for this universe
        hlpr (PlotHelper): The PlotHelper
        model_name (str): The name of the model the data resides in
        path_to_data (str or Tuple[str, str]): The path to the data within the
            model data or the paths to the x and the y data, respectively
        **plot_kwargs: Passed on to plt.plot

    Raises:
        ValueError: On invalid data dimensionality
        ValueError: On mismatch of data shapes
    """
    # Get the data
    if isinstance(path_to_data, str):
        data_y = uni["data"][model_name][path_to_data]
        data_x = data_y.coords[data_y.dims[0]]

    else:
        data_x = uni["data"][model_name][path_to_data[0]]
        data_y = uni["data"][model_name][path_to_data[1]]

        if data_x.shape != data_y.shape:
            raise ValueError(
                "Mismatch of data shapes! "
                f"Were {data_x.shape} and {data_y.shape}, but have to be of "
                "same shape (after transfromation)."
            )

    # Require 1D data now
    if data_x.ndim != 1:
        raise ValueError(
            f"Lineplot requires 1D data, but got {data_x.ndim}D data of "
            f"shape {data_x.shape} for x-axis data:\n{data_x}\n"
            "Apply dimensionality reducing transformations to arrive "
            "at plottable data."
        )

    if data_y.ndim != 1:
        raise ValueError(
            f"Lineplot requires 1D data, but got {data_y.ndim}D data of "
            f"shape {data_y.shape} for y-axis data:\n{data_y}\n"
            "Apply dimensionality reducing transformations to arrive "
            "at plottable data."
        )

    hlpr.ax.plot(data_x, data_y, **plot_kwargs)
