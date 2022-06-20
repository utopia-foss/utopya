"""Implements seaborn-based plotting functions"""

import copy
import logging
from typing import Hashable, List, Sequence, Tuple, Union

import pandas as pd
import seaborn as sns
import xarray as xr
from dantro.exceptions import PlottingError
from dantro.plot.funcs.generic import (
    determine_encoding,
    figure_leak_prevention,
    make_facet_grid_plot,
)

from utopya.plotting import PlotHelper, is_plot_func

log = logging.getLogger(__name__)


# .. Seaborn's figure-level plot functions ....................................
SNS_PLOT_FUNCS = {
    "relplot": sns.relplot,
    "displot": sns.displot,
    "catplot": sns.catplot,
    "lmplot": sns.lmplot,
    "clustermap": sns.clustermap,
    "pairplot": sns.pairplot,
    "jointplot": sns.jointplot,
}

SNS_FACETGRID_KINDS = (
    "relplot",
    "displot",
    "catplot",
    "lmplot",
)

# .. Encodings for seaborn's figure-level plot functions ......................
# TODO Check if all are correct
SNS_ENCODINGS = {
    # FacetGrid: Distributions
    "displot": ("col", "row", "hue"),
    "catplot": ("y", "hue", "col", "row"),
    # FacetGrid: Relational
    "relplot": ("x", "y", "hue", "col", "row", "style", "size"),
    "lmplot": ("x", "y", "hue", "col", "row"),
    # Others
    "clustermap": ("hue", "col", "row"),
    "pairplot": ("hue",),
    "jointplot": (
        "x",
        "y",
        "hue",
    ),
}


# -----------------------------------------------------------------------------


@is_plot_func(use_dag=True, required_dag_tags=("data",))
def snsplot(
    *,
    data: dict,
    hlpr: PlotHelper,
    sns_kind: str,
    free_indices: Tuple[str],
    optional_free_indices: Tuple[str] = (),
    auto_encoding: Union[bool, dict] = None,
    reset_index: bool = False,
    to_dataframe_kwargs: dict = None,
    dropna: bool = False,
    dropna_kwargs: dict = None,
    sample: Union[bool, int] = False,
    sample_kwargs: dict = None,
    **plot_kwargs,
) -> None:
    """Interface to seaborn's figure-level plot functions.

    Plots on a facet grid:
        * ``relplot``:      seaborn.pydata.org/generated/seaborn.relplot.html
        * ``displot``:      seaborn.pydata.org/generated/seaborn.displot.html
        * ``catplot``:      seaborn.pydata.org/generated/seaborn.catplot.html
        * ``lmplot``:       seaborn.pydata.org/generated/seaborn.lmplot.html

    Other plots:
        * ``clustermap``:   seaborn.pydata.org/generated/seaborn.clustermap.html
        * ``pairplot``:     seaborn.pydata.org/generated/seaborn.pairplot.html
        * ``jointplot``:    seaborn.pydata.org/generated/seaborn.jointplot.html

    Args:
        data (dict): The data transformation framework results, expecting a
            single entry ``data`` which can be a pandas.DataFrame or an
            xarray data type.
        hlpr (PlotHelper): The plot helper instance
        sns_kind (str): Which seaborn plot to use
        free_indices (Tuple[str]): Which index names *not* to associate with a
            layout encoding; seaborn uses these to calculate the distribution
            statistics.
        optional_free_indices (Tuple[str], optional): These indices will be
            added to the free indices *if they are part of the data frame*.
            Otherwise, they are silently ignored.
        auto_encoding (Union[bool, dict], optional): Auto-encoding options.
        reset_index (bool, optional): Whether to reset indices such
            that only the ``free_indices`` remain as indices and all others are
            converted into columns.
        to_dataframe_kwargs (dict, optional): For xarray data types, this is
            used to convert the given data into a pandas.DataFrame.
        sample (bool, optional): If True, will sample a subset from the final
            dataframe, controlled by ``sample_kwargs``
        sample_kwargs (dict, optional): Passed to ``pd.DataFrame.sample``.
        **plot_kwargs: Passed on to the selected plotting function.
    """
    df = data["data"]

    # For xarray types, attempt conversion
    if isinstance(df, (xr.Dataset, xr.DataArray)):
        tdf_kwargs = to_dataframe_kwargs if to_dataframe_kwargs else {}
        log.note("Attempting conversion to pd.DataFrame ...")
        log.remark(
            "  Arguments:  %s",
            ", ".join(f"{k}: {v}" for k, v in tdf_kwargs.items()),
        )
        df = df.to_dataframe(**tdf_kwargs)

    # Re-index to get long-form data
    # See:  https://seaborn.pydata.org/tutorial/data_structure.html
    log.note("Evaluating data frame ...")
    log.remark("  Length:           %d", len(df))
    log.remark("  Shape:            %s", df.shape)
    log.remark("  Size:             %d", df.size)
    try:
        log.remark("  Columns:          %s", ", ".join(df.columns))
    except:  # TODO Make more specific or even avoid try-except
        log.remark("  Columns:          (none)")

    try:
        log.remark("  Indices:          %s", ", ".join(df.index.names))
    except:  # TODO Make more specific or even avoid try-except
        log.remark("  Indices:          (no named indices)")

    log.remark("  Free indices:     %s", ", ".join(free_indices))
    log.remark("  Optionally free:  %s", ", ".join(optional_free_indices))

    # TODO Add an option to make all indices free, excluding some ...

    # Apply optionally free indices
    free_indices += [n for n in optional_free_indices if n in df.index.names]

    # For some kinds, it makes sense to re-index such that only the free
    # indices are used as columns
    if reset_index:
        reset_for = [n for n in df.index.names if n not in free_indices]
        if reset_for:
            df = df.reset_index(level=reset_for)
            log.remark("  Reset index for:  %s", ", ".join(reset_for))

    # Might want to drop null values
    if dropna:
        dropna_kwargs = dropna_kwargs if dropna_kwargs else {}
        log.note("Dropping null values ...")
        log.remark(
            "  Arguments:  %s",
            ", ".join(f"{k}: {v}" for k, v in dropna_kwargs.items()),
        )
        df = df.dropna(**dropna_kwargs)
        log.remark("  Length after drop:  %d", len(df))

    # Sampling
    if sample:
        if not sample_kwargs:
            sample_kwargs = {}
            if isinstance(sample, int) and sample < len(df):
                sample_kwargs["n"] = sample

        if sample_kwargs:
            log.note("Sampling from data frame ...")
            log.remark(
                "  Arguments:  %s",
                ", ".join(f"{k}: {v}" for k, v in sample_kwargs.items()),
            )
            len_before = len(df)
            try:
                df = df.sample(**sample_kwargs)
            except Exception as exc:
                log.error(
                    "  Sampling failed with %s: %s", type(exc).__name__, exc
                )
            else:
                log.remark(
                    "  Sampling succeeded. New length: %d (%d)",
                    len(df),
                    len(df) - len_before,
                )
        else:
            log.note("Sampling skipped (no arguments applicable).")

    # ... further preprocessing ...

    # Interface with auto-encoding
    # Need to pop any given `kind` argument (valid input to sns.pairplot)
    kind = plot_kwargs.pop("kind", None)
    plot_kwargs = determine_encoding(
        {
            n: s
            for n, s in zip(
                df.index.names, getattr(df.index, "levshape", [len(df.index)])
            )
            if n not in free_indices
        },
        kind=sns_kind,
        auto_encoding=auto_encoding,
        default_encodings=SNS_ENCODINGS,
        plot_kwargs=plot_kwargs,
    )
    if kind is not None:
        plot_kwargs["kind"] = kind

    # Depending on plot kinds, determine some further arguments
    if kind in SNS_FACETGRID_KINDS:
        # Provide a best guess for the `x` encoding, if it is not given
        if "x" not in plot_kwargs and len(df.columns) == 1:
            x = str(df.columns[0])
            log.note("Using '%s' for x-axis encoding.", x)
            plot_kwargs["x"] = x

    # Retrieve the plot function
    try:
        plot_func = SNS_PLOT_FUNCS[sns_kind]

    except KeyError:
        _avail = ", ".join(SNS_PLOT_FUNCS)
        raise ValueError(
            f"Invalid plot kind '{sns_kind}'! Available: {_avail}"
        )

    # Actual plotting . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Close the existing figure; the seaborn functions create their own
    hlpr.close_figure()

    # Let seaborn do the plotting
    log.note("Now invoking sns.%s ...", sns_kind)

    try:
        with figure_leak_prevention():
            fg = plot_func(data=df, **plot_kwargs)

    except Exception as exc:
        raise PlottingError(
            f"sns.{sns_kind} failed! Got {type(exc).__name__}: {exc}\n\n"
            f"Data was:\n{df}\n\n"
            f"Plot function arguments were:\n  {plot_kwargs}"
        ) from exc

    # Attach the created figure, including a workaround for `col_wrap`, in
    # which case `fg.axes` is one-dimensional (for whatever reason)
    if isinstance(fg, sns.JointGrid):
        fig = fg.fig
        axes = [[fg.ax_joint]]  # TODO consider registering all axes

    else:
        # Assume it's FacetGrid-like
        fig = fg.fig
        axes = fg.axes
        if axes.ndim != 2:
            axes = axes.reshape((fg._nrow, fg._ncol))

    hlpr.attach_figure_and_axes(fig=fig, axes=axes)

    # TODO Animation?!
