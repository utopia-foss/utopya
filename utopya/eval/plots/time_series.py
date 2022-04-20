"""A generic, DAG-supporting time series plot"""

import xarray as xr

from . import PlotHelper, is_plot_func

# -----------------------------------------------------------------------------


@is_plot_func(
    use_dag=True,
    required_dag_tags=("y",),
    helper_defaults=dict(
        set_labels=dict(x="Time"), set_limits=dict(x=["min", "max"])
    ),
)
def time_series(
    *, data: dict, hlpr: PlotHelper, label_fstr: str = "{:.2g}", **plot_kwargs
):
    """This is a generic plotting function that plots one or multiple time
    series from the 'y' tag that is selected via the DAG framework.

    The y data needs to be an xarray object. If y is an xr.DataArray, it is
    assumed to be one- or two-dimensional.
    If y is an xr.Dataset, all data variables are plotted and their name is
    used as the label.

    For the x axis values, the corresponding 'time' coordinates are used.

    Args:
        data (dict): The data selected by the DAG framework
        hlpr (PlotHelper): The plot helper
        label_fstr (str, optional): Formatting to use for label
        **plot_kwargs: Passed on ot matplotlib.pyplot.plot
    """
    y = data["y"]

    # If this is an xr.DataArray, it may be one or two-dimensional
    if isinstance(y, xr.Dataset):
        # Simply plot all data variables
        for dvar, line in y.data_vars.items():
            hlpr.ax.plot(line.coords["time"], line, label=dvar, **plot_kwargs)

    elif isinstance(y, xr.DataArray):
        # Also allow two-dimensional arrays
        if y.ndim == 1:
            hlpr.ax.plot(y.coords["time"], y, **plot_kwargs)

        elif y.ndim == 2:
            loop_dim = [d for d in y.dims if d != "time"][0]

            for c in y.coords[loop_dim]:
                line = y.sel({loop_dim: c})
                hlpr.ax.plot(
                    line.coords["time"],
                    line,
                    label=label_fstr.format(c.item()),
                    **plot_kwargs,
                )

            # Provide a default title to the legend: name of the loop dimension
            hlpr.provide_defaults(
                "set_legend", title=f"${loop_dim}$ coordinate"
            )

        else:
            raise ValueError(
                "Given y-data needs to be of one- or two-dimensional, "
                f"was of dimensionality {y.ndim}! Data: {y}"
            )

    else:
        raise TypeError(f"Expected xr.Dataset or xr.DataArray, got {type(y)}")
