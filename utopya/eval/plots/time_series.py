"""A generic, DAG-supporting time series plot"""

import xarray as xr

from . import PlotHelper, is_plot_func

# -----------------------------------------------------------------------------


@is_plot_func(
    use_dag=True,
    required_dag_tags=("data",),
    helper_defaults=dict(set_limits=dict(x=["min", "max"])),
)
def time_series(
    *,
    data: dict,
    hlpr: PlotHelper,
    x: str = "time",
    label_fstr: str = "{:.2g}",
    **plot_kwargs,
):
    """This is a generic plotting function that plots one or multiple time
    series from the ``data`` tag that is selected via the DAG framework.

    The data needs to be an xarray object. If y is an xr.DataArray, it is
    assumed to be one- or two-dimensional.
    If is an :py:class:`xarray.Dataset`, all data variables are plotted and
    their name is used as the label.

    For the x axis values, the corresponding ``time`` coordinates are used;
    these need to be part of the dataset!

    .. note::

        For a more generic plot, see dantro's
        :py:func:`~dantro.plot.funcs.generic.facet_grid`, which is available
        under ``.plot.facet_grid`` in utopya.

    Args:
        data (dict): The data selected by the DAG framework
        hlpr (PlotHelper): The plot helper
        x (str, optional): Name of the coordinate dimension to put on the
            x-axis, typically (and by default) ``time``.
        label_fstr (str, optional): Formatting to use for label in case of
            the data being an :py:class:`xarray.DataArray`.
        **plot_kwargs: Passed on ot :py:func:`matplotlib.pyplot.plot`.
    """
    d = data["data"]

    # If this is an xr.DataArray, it may be one or two-dimensional
    if isinstance(d, xr.Dataset):
        # Simply plot all data variables as individual lines
        for dvar, line in d.data_vars.items():
            hlpr.ax.plot(line.coords[x], line, label=dvar, **plot_kwargs)

        hlpr.invoke_helper(
            "set_labels", x=x.capitalize(), mark_disabled_after_use=False
        )

    elif isinstance(d, xr.DataArray):
        # Also allow two-dimensional arrays
        if d.ndim == 1:
            hlpr.ax.plot(d.coords[x], d, **plot_kwargs)

        elif d.ndim == 2:
            loop_dim = [dim for dim in d.dims if dim != x][0]

            for c in d.coords[loop_dim]:
                line = d.sel({loop_dim: c})
                hlpr.ax.plot(
                    line.coords[x],
                    line,
                    label=label_fstr.format(c.item()),
                    **plot_kwargs,
                )

            # Provide a default title to the legend: name of the loop dimension
            hlpr.invoke_helper(
                "set_legend",
                title=f"${loop_dim}$ coordinate",
                mark_disabled_after_use=False,
            )
            hlpr.invoke_helper(
                "set_labels", x=x.capitalize(), mark_disabled_after_use=False
            )

        else:
            raise ValueError(
                f"Array data needs to be 1D or 2D, but was {d.ndim}D!\n"
                f"Given data:\n{d}"
            )

    else:
        raise TypeError(f"Expected xr.Dataset or xr.DataArray, got {type(d)}")
