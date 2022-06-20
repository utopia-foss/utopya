"""This module provides plotting functions to visualize cellular automata."""

import copy
import logging
from math import ceil, sqrt
from typing import Callable, Dict, Sequence, Union

import matplotlib as mpl
import numpy as np
import xarray as xr
from dantro.abc import AbstractDataContainer
from matplotlib.collections import RegularPolyCollection
from matplotlib.colors import ListedColormap
from mpl_toolkits.axes_grid1 import make_axes_locatable

from ...tools import recursive_update
from .. import DataManager, UniverseGroup
from . import PlotHelper, UniversePlotCreator, is_plot_func

log = logging.getLogger(__name__)

# Increase log threshold for animation module
logging.getLogger("matplotlib.animation").setLevel(logging.WARNING)


# -----------------------------------------------------------------------------


def _get_ax_size(ax, fig) -> tuple:
    """The width and height of the given axis in pixels"""
    bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    width, height = bbox.width, bbox.height
    width *= fig.dpi
    height *= fig.dpi
    return width, height


def imshow_hexagonal(
    data: xr.DataArray,
    *,
    hlpr: PlotHelper,
    colormap: Union[str, mpl.colors.Colormap],
    **kwargs,
) -> mpl.image.AxesImage:
    """Display data as an image, i.e., on a 2D hexagonal grid.

    Args:
        data (xarray.DataArray): The array-like data to plot as image.
        hlpr (PlotHelper): The plot helper.
        colormap (str or matplotlib.colors.Colormap): The colormap to use.

    Returns:
        The RegularPolyCollection representing the hexgrid.
    """
    width, height = _get_ax_size(hlpr.ax, hlpr.fig)
    s = (height / data.y.size) / 0.75 / 2
    # NOTE the 0.75 factor is required because of the hexagonal offset geometry
    area = 3**1.5 / 2 * s**2

    # distinguish pair and impair rows (impair have offset)
    hex_s = 2 * data.isel(y=0).y
    y_ids = ((data.y / hex_s - 0.5) / 0.75).round().astype(int)

    # compute offsets of polygons
    xx, yy = np.meshgrid(data.x, data.y)
    x_offsets = xr.DataArray(
        data=xx, dims=("y", "x"), coords=dict(x=data.x, y=data.y)
    )
    y_offsets = xr.DataArray(
        data=yy, dims=("y", "x"), coords=dict(x=data.x, y=data.y)
    )

    # ... and add an x-offset for impair rows
    x_origin = data.isel(x=0, y=0).coords["x"]
    x_offsets[y_ids % 2 == 1] += x_origin

    # # assign the true coordinates
    # d = d.assign_coords(x=('x', d.x))
    # d_offset = d_offset.assign_coords(x=('x', d_offset.x + x_origin))

    # get the color mapping
    if isinstance(colormap, str):
        cmap = mpl.cm.get_cmap(name=colormap)
    else:
        cmap = colormap
    map_color = mpl.cm.ScalarMappable(cmap=cmap)

    pcoll = RegularPolyCollection(
        6,
        sizes=(area,),
        rotation=0,
        facecolor=map_color.to_rgba(data.data.flatten()),
        offsets=np.transpose(
            [x_offsets.data.flatten(), y_offsets.data.flatten()]
        ),
        transOffset=hlpr.ax.transData,
        animated=kwargs.get("animated", True),
        rasterized=kwargs.get("rasterized", False),
    )
    hlpr.ax.add_collection(pcoll)

    # use same length scale in x and y
    hlpr.ax.set_aspect("equal")

    # rescale cmap
    im = mpl.image.AxesImage(hlpr.ax)

    im.set_cmap(colormap)
    if "vmin" in kwargs and "vmax" in kwargs:
        # From `limits` argument; will either have none or both
        im.set_clim(kwargs["vmin"], kwargs["vmax"])

    return im


def _plot_ca_property(
    prop_name: str,
    *,
    hlpr: PlotHelper,
    data: xr.DataArray,
    default_imshow_kwargs: dict,
    cax=None,
    grid_structure: str = None,
    limits: list = None,
    cmap: Union[str, dict] = "viridis",
    draw_cbar: bool = True,
    title: str = None,
    no_cbar_markings: bool = False,
    imshow_kwargs: dict = None,
    **cbar_kwargs,
):
    """Helper function to plot a property on a given axis and return
    an imshow object

    TODO Finish writing docstring

    Args:
        prop_name (str): The property to plot
        hlpr (PlotHelper): Description
        data (xarray.DataArray): The array-like data to plot as image
        grid_structure (str, optional): Description
        default_imshow_kwargs (dict): Description
        cax: colorbar axis object
        limits (list, optional): The imshow limits to use; will also be
            the limits of the colorbar.
        cmap (Union[str, dict], optional): The colormap to use. If a dict is
            given, defines a (discrete) ``ListedColormap`` from the values.
        draw_cbar (bool, optional): whether to draw a color bar
        title (str, optional): The subplot figure title
        no_cbar_markings (bool, optional): Whether to suppress colorbar
            markings (ticks and tick labels)
        imshow_kwargs (dict, optional): Passed to ``plt.imshow``
        **cbar_kwargs: Passed to ``fig.colorbar``

    Returns:
        imshow object

    Raises:
        TypeError: For invalid ``cmap`` argument.
        ValueError: For invalid grid structure; needs to be ``square``,
            ``hexagonal`` or ``triangular``.
    """
    # Get colormap, either a continuous or a discrete one
    if isinstance(cmap, str):
        norm = None
        bounds = None
        colormap = cmap

    elif isinstance(cmap, dict):
        colormap = ListedColormap(cmap.values())
        bounds = limits
        norm = mpl.colors.BoundaryNorm(bounds, colormap.N)

    else:
        raise TypeError(
            "Argument cmap needs to be either a string with name of the "
            "colormap or a dict with values for a discrete colormap! "
            f"Was: {type(cmap)} with value: '{cmap}'"
        )

    # Parse additional colorbar kwargs and set some default values
    add_cbar_kwargs = dict()
    if "fraction" not in cbar_kwargs:
        add_cbar_kwargs["fraction"] = 0.05

    if "pad" not in cbar_kwargs:
        add_cbar_kwargs["pad"] = 0.02

    # Fill imshow_kwargs, using defaults
    imshow_kwargs = imshow_kwargs if imshow_kwargs else {}
    imshow_kwargs = recursive_update(
        copy.deepcopy(imshow_kwargs),
        default_imshow_kwargs if default_imshow_kwargs else {},
    )
    if limits:
        vmin, vmax = limits
        imshow_kwargs["vmin"] = vmin
        imshow_kwargs["vmax"] = vmax

    # Create imshow object on the currently selected axis
    grid_structure = (
        grid_structure
        if grid_structure
        else data.attrs.get("grid_structure", "square")
    )
    if grid_structure == "square" or grid_structure is None:
        im = hlpr.ax.imshow(
            data.T,
            cmap=colormap,
            animated=True,
            rasterized=True,
            origin="lower",
            aspect="equal",
            **imshow_kwargs,
        )

    elif grid_structure == "hexagonal":
        hlpr.ax.clear()
        im = imshow_hexagonal(
            data=data,
            hlpr=hlpr,
            animated=True,
            rasterized=True,
            colormap=colormap,
            **imshow_kwargs,
        )
        title = title if title else prop_name
        hlpr.ax.set_title(title)

    elif grid_structure == "triangular":
        raise ValueError("Plotting of triangular grid not implemented!")

    else:
        raise ValueError(f"Unknown grid structure '{grid_structure}'!")

    # Create the colorbar.
    # For hexagonal grids, manually create a separate axis next to the
    # current plotting axis. Add a cbar and manually set the ticks and
    # boundaries (as the cbar returned by the mpl.image.AxesImage has
    # default range (0, 1))
    if draw_cbar and grid_structure == "hexagonal":
        cax.clear()
        if bounds:
            num_colors = len(cmap)
            boundaries = [i / num_colors for i in range(num_colors + 1)]
            tick_locs = [
                (2 * i + 1) / (2 * num_colors) for i in range(num_colors)
            ]
        else:
            boundaries = None
            tick_locs = [i * 0.25 for i in range(5)]
            if isinstance(colormap, str):
                colormap = mpl.cm.get_cmap(name=colormap)

        cbar = mpl.colorbar.ColorbarBase(
            cax, cmap=colormap, boundaries=boundaries
        )
        cbar.set_ticks(tick_locs)

        # For discrete colorbars, set the tick labels at the positions
        # defined; for continuous colorbars, get the upper and lower
        # boundaries from the dataset.
        if bounds:
            cbar.ax.set_yticklabels(cmap.keys())
        else:
            lower = np.min(data.data)
            upper = np.max(data.data)
            if lower == upper:
                diff = 0.01
            else:
                diff = upper - lower

            ticklabels = [i * diff / 4 + lower for i in range(5)]
            cbar.ax.set_yticklabels(ticklabels)

    elif draw_cbar:
        cbar = hlpr.fig.colorbar(
            im, ax=hlpr.ax, ticks=bounds, **cbar_kwargs, **add_cbar_kwargs
        )
        # For a discrete colormap, adjust the tick positions
        if bounds:
            num_colors = len(cmap)
            tick_locs = (
                (np.arange(num_colors) + 0.5) * (num_colors - 1) / num_colors
            )
            cbar.set_ticks(tick_locs)
            cbar.ax.set_yticklabels(cmap.keys())

    # Remove markings, if configured to do so
    if draw_cbar and no_cbar_markings:
        cbar.set_ticks([])
        cbar.ax.set_yticklabels([])

    # Remove main axis labels and ticks
    hlpr.ax.axis("off")

    # Provide configuration options to plot helper
    hlpr.provide_defaults("set_title", title=(title if title else prop_name))

    return im


# -----------------------------------------------------------------------------


@is_plot_func(use_dag=True, supports_animation=True)
def caplot(
    *,
    hlpr: PlotHelper,
    data: dict,
    to_plot: Dict[str, dict],
    from_dataset: xr.Dataset = None,
    frames: str = "time",
    frames_isel: Union[int, Sequence] = None,
    grid_structure: str = None,
    aspect: float = 1.0,
    aspect_pad: float = 0.1,
    size: float = None,
    col_wrap: Union[int, str, bool] = "auto",
    default_imshow_kwargs: dict = None,
    default_cbar_kwargs: dict = None,  # TODO implement
    suptitle_fstr: str = "{} = {}",
    suptitle_kwargs: dict = None,
):
    """Plots an animated series of one or many 2D Cellular Automata states.

    The data used for plotting is assembled from ``data`` using the keys that
    are specified in ``to_plot``. Alternatively, the ``from_dataset`` argument
    can be used to pass a dataset which contains all the required data.

    The keys in ``to_plot`` should match the names of data variables.
    The values in ``to_plot`` specify the individual subplots' properties like
    the color map that is to be used or the minimum or maximum values.

    For plotting, the matplotlib ``imshow`` function is used.

    .. note::

        Overall, there should be two spatial dataset dimensions and one that
        goes along the ``frames`` dimension. All coordinate labels should be
        identical, otherwise the behavior is not defined.

    Args:
        hlpr (PlotHelper): The plot helper instance
        data (dict): The selected data
        to_plot (Dict[str, dict]): Which data to plot and how. The keys of
            this dict refer to an item within the selected ``data`` or the
            given dataset.
            Each of these keys is expected to hold yet another dict,
            supporting the following configuration options (all optional):

                - ``cmap`` (str or dict): The colormap to use. If it is a
                    dict, a discrete colormap is assumed. The keys will be the
                    labels and the values the color. Association happens in
                    the order of entries.
                - ``title`` (str): The title for this sub-plot
                - ``limits`` (2-tuple, list): The fixed heat map limits of this
                    property; if not given, limits will be auto-scaled. If
                    they are ``min`` or ``max``, the *global* minimum or
                    maximum, respectively, will be used.
                    Note that specifying ``limits`` will overwrite potentially
                    existing ``vmin`` and ``vmax`` arguments to imshow.
                - ``**imshow_kwargs``: passed on to imshow invocation

        from_dataset (xarray.Dataset, optional): If given, will use this object
            instead of assembling a dataset from ``data`` and ``to_plot`` keys.
        frames (str, optional): Name of the animated dimension, typically the
            time dimension.
        frames_isel (Union[int, Sequence], optional): The index selector for
            the frames dimension. Can be a single integer but also a range
            expression.
        grid_structure (str, optional): The underlying grid structure, can be
            ``square``, ``hexagonal``, or ``triangular`` (not implemented).
            If None, will try to read it from the individual properties' data
            attribute ``grid_structure``.
        aspect (float, optional): The aspect ratio (width/height) of the
            subplots; should match the aspect ratio of the data.
        aspect_pad (float, optional): A factor that is added to the calcuation
            of the subplots width. This can be used to create a horizontal
            padding between subplots.
        size (float, optional): The height in inches of a subplot.
            Is used to determine the subplot size with the width being
            calculated by ``size * (aspect + aspect_pad)``.
        col_wrap (Union[int, str, bool], optional): Controls column wrapping.
            If ``auto``, will compute a column wrapping that leads to an
            (approximately) square subplots layout (not taking into account
            the subplots aspect ratio, only the grid layout). This will start
            producing a column wrapping with four or more properties to plot.
        default_imshow_kwargs (dict, optional): The default parameters passed
            to the underlying imshow plotting function. These are updated by
            the values given via ``to_plot``.
        default_cbar_kwargs (dict, optional): NOT IMPLEMENTED  # FIXME
        suptitle_fstr (str, optional): A format string used to create the
            suptitle string. Passed arguments are ``frames`` and the currently
            selected frames *coordinate* (not the index!).
            If this evaluates to False, will not create a figure suptitle.
        suptitle_kwargs (dict, optional): Passed on to ``fig.suptitle``.
    """
    # Helper functions ........................................................

    def get_grid_structure(d: xr.DataArray) -> str:
        """Retrieves the grid structure from data attributes"""
        grid_structure = d.attrs.get("grid_structure")
        if isinstance(grid_structure, np.ndarray):
            grid_structure = grid_structure.item()

        return grid_structure

    def prepare_data(data: dict, *, prop_name: str) -> xr.DataArray:
        """Prepares data for (later) creating an :py:class:`xarray.Dataset`"""
        d = data[prop_name]
        if isinstance(d, AbstractDataContainer):
            d = d.data
        return d

    def select_data(ds: xr.Dataset, name: str, isel: dict) -> xr.DataArray:
        """Selects a slice of data for plotting using
        :py:meth:`~xarray.DataArray.isel` on the data variable ``name``."""
        return ds[name].isel(isel)

    def set_suptitle(data: xr.DataArray):
        """Sets the suptitle"""
        if not suptitle_fstr:
            return

        hlpr.fig.suptitle(
            suptitle_fstr.format(frames, data.coords[frames].item()),
            **(suptitle_kwargs if suptitle_kwargs else {}),
        )

    # Prepare the data ........................................................
    # Work on a copy of the plot spec
    to_plot = copy.deepcopy(to_plot)

    # Bring data into xr.Dataset form
    log.note("Preparing data for CA plot ...")
    if from_dataset:
        log.remark("Using explicitly passed dataset ...")
        ds = from_dataset
    else:
        log.remark("Constructing dataset ...")
        ds = xr.Dataset({p: prepare_data(data, prop_name=p) for p in to_plot})

    # Check that frames dimension is available
    if not frames or frames not in ds.coords:
        _avail = ", ".join(xr.coords.keys())
        raise ValueError(
            f"Invalid frames coordinate dimension '{frames}'! "
            f"Available coordinates:  {_avail}"
        )

    # Apply selection along frames dimension
    if frames_isel is not None:
        if isinstance(frames_isel, int):
            frames_isel = [frames_isel]
        _selector = {frames: frames_isel}
        log.remark("Applying index selection %s  ...", _selector)
        ds = ds.isel(_selector, drop=False)

    # TODO x-y mapping?
    # TODO Automate aspect computation from x and y dimensions

    # Depending on length of coordinate dimension, ensure that animation mode
    # is enabled or disabled.
    num_frames = ds.coords[frames].size
    if num_frames > 1:
        hlpr.enable_animation()
    else:
        hlpr.disable_animation()

    # If not given, retrieve the structure from the data variable's attributes.
    if not grid_structure:
        structures = {p: get_grid_structure(ds[p]) for p in to_plot}

        if len(set(structures.values())) != 1:
            raise ValueError(
                "Mismatch in grid structure; all grid structures need to be "
                f"the same but were:  {structures}"
            )
        grid_structure = next(iter(structures.values()))

    # Evaluate limits argument for all properties
    for prop_name, spec in to_plot.items():
        if spec.get("limits"):
            vmin, vmax = spec["limits"]
            if vmin == "min":
                vmin = ds[prop_name].min().item()
            if vmax == "max":
                vmax = ds[prop_name].max().item()
            spec["limits"] = (vmin, vmax)

    # Inform about the data that is to be plotted
    log.note(
        "Performing CA plot for %d data variable%s ...",
        len(to_plot),
        "" if len(to_plot) == 1 else "s",
    )
    log.remark("  Data variables:     %s", ", ".join(to_plot))
    log.remark(
        "  Dimensions:         %s",
        ", ".join(f"{k}: {s}" for k, s in ds.sizes.items()),
    )
    log.remark("  Grid structure:     %s", grid_structure)

    # Some final checks ...
    if len(ds.sizes) != 3:
        raise ValueError(
            f"Dataset shape needs to be 3-dimensional, but was: {ds.sizes}"
        )

    # Prepare the figure ......................................................
    # Evaluate column wrapping
    if col_wrap and not (col_wrap == "auto" and len(to_plot) < 4):
        if col_wrap == "auto":
            col_wrap = ceil(sqrt(len(to_plot)))
        log.remark("  Column wrapping:    %s", col_wrap)

        ncols = col_wrap
        nrows = ceil(len(to_plot) / col_wrap)
        axis_map = {
            p: dict(col=i % col_wrap, row=i // col_wrap)
            for i, p in enumerate(to_plot)
        }

    else:
        ncols = len(to_plot)
        nrows = 1
        axis_map = {p: dict(col=col, row=0) for col, p in enumerate(to_plot)}

    # Determine the figsize from the size argument (height) and data aspect.
    # Depending on structure, may need to adapt figure size.
    if not size:
        size = mpl.rcParams["figure.figsize"][1]
    figsize = (size * (aspect + aspect_pad), size)

    if grid_structure == "hexagonal":
        figsize = (figsize[0] * 1.2, figsize[1])

    # Create the figure and set all axes as invisible. This is needed because
    # col_wrap may lead to some subplots being completely empty.
    # Below
    hlpr.setup_figure(
        figsize=figsize,
        scale_figsize_with_subplots_shape=True,
        ncols=ncols,
        nrows=nrows,
    )
    for ax in hlpr.axes.flat:
        ax.set_visible(False)

    # Do the single plot for all data variables, looping through subfigures.
    # This creates the first imshow objects, which are being kept track of
    # such that they can later be updated.
    # This also sets the axes as visible again, but only for those that have
    # a property assigned to them.
    ims = dict()
    for i, (prop_name, props) in enumerate(to_plot.items()):
        hlpr.select_axis(**axis_map[prop_name])
        hlpr.ax.set_visible(True)

        # For hexagonal grids, need to add custom colorbar axis here
        # TODO Parameterise default values
        if props.get("draw_cbar", True) and grid_structure == "hexagonal":
            divider = make_axes_locatable(hlpr.ax)
            props["cax"] = divider.append_axes("right", size="5%", pad=0.2)
            hlpr.select_axis(**axis_map[prop_name])

        # Select the appropriate data, then plot the data variable
        data = select_data(ds, prop_name, {frames: 0})

        ims[prop_name] = _plot_ca_property(
            prop_name,
            hlpr=hlpr,
            data=data,
            grid_structure=grid_structure,
            default_imshow_kwargs=default_imshow_kwargs,
            **props,
        )

        # Use this data for setting the figure suptitle
        if i == 0:
            set_suptitle(data)

    # End of single frame CA state plot function ..............................
    # The above variables are all available below, but the update function is
    # supposed to start plotting anew, starting from frame 0.

    def update_data():
        """Updates the data of the imshow objects"""
        log.note("Plotting animation with %d frames ...", num_frames)

        for frame_idx in range(num_frames):
            log.debug("Plotting frame %d ...", frame_idx)

            for i, (prop_name, props) in enumerate(to_plot.items()):
                hlpr.select_axis(**axis_map[prop_name])

                frame_data = select_data(ds, prop_name, {frames: frame_idx})

                # Depending on grid structure, update data or plot anew
                if grid_structure == "hexagonal":
                    # For hexagonal grids recreate the plot each time.
                    # Just resetting the data does not show the updated states
                    # otherwise because the facecolors have to be updated, too.
                    ims[prop_name] = _plot_ca_property(
                        prop_name,
                        data=frame_data,
                        hlpr=hlpr,
                        grid_structure=grid_structure,
                        default_imshow_kwargs=default_imshow_kwargs,
                        **props,
                    )

                else:
                    # Update imshow data without creating a new object
                    ims[prop_name].set_data(frame_data.T)

                    # If no limits are provided, autoscale the new limits in
                    # the case of continuous colormaps. A discrete colormap
                    # provided as a dict should never have to autoscale.
                    if not isinstance(props.get("cmap"), dict):
                        if not props.get("limits"):
                            ims[prop_name].autoscale()

                # Use the first subplot's data for setting the figure suptitle
                if i == 0:
                    set_suptitle(frame_data)

            # Done with this frame; yield control to the animation framework.
            yield

    # Register this update method with the helper, which takes care of the rest
    hlpr.register_animation_update(update_data)


# -----------------------------------------------------------------------------


@is_plot_func(creator_type=UniversePlotCreator, supports_animation=True)
def state(
    dm: DataManager,
    *,
    uni: UniverseGroup,
    hlpr: PlotHelper,
    model_name: str,
    to_plot: dict,
    time_idx: int,
    default_imshow_kwargs: dict = None,
    **_kwargs,
):
    r"""Plots the state of the cellular automaton as a 2D heat map.
    This plot function can be used for a single plot, but also supports
    animation.

    Which properties of the state to plot can be defined in ``to_plot``.

    Args:
        dm (DataManager): The DataManager that holds all loaded data
        uni (UniverseGroup): The currently selected universe, parsed by the
            :py:class:`~utopya.eval.plotcreators.UniversePlotCreator`.
        hlpr (PlotHelper): The plot helper
        model_name (str): The name of the model of which the data is to be
            plotted
        to_plot (dict): Which data to plot and how. The keys of this dict
            refer to a path within the data and can include forward slashes to
            navigate to data of submodels. Each of these keys is expected to
            hold yet another dict, supporting the following configuration
            options (all optional):

                - cmap (str or dict): The colormap to use. If it is a dict, a
                    discrete colormap is assumed. The keys will be the labels
                    and the values the color. Association happens in the order
                    of entries.
                - title (str): The title for this sub-plot
                - limits (2-tuple, list): The fixed heat map limits of this
                    property; if not given, limits will be auto-scaled.
                - \**imshow_kwargs: passed on to imshow invocation

        time_idx (int): Which time index to plot the data of. Is ignored when
            creating an animation.
        default_imshow_kwargs (dict, optional): The default parameters passed
            to the underlying imshow plotting function. These are updated by
            the values given via ``to_plot``.

    Raises:
        ValueError: Shape mismatch of data selected by ``to_plot``
        AttributeError: Got unsupported arguments (referring to the old data
            transformation framework)
    """
    if _kwargs:
        raise AttributeError(
            "This plot no longer supports preprocessing or transformation but "
            f"got one of the following arguments:  {_kwargs}\n"
            "Use the new CA plot function (.ca.caplot) which supports the "
            "data transformation framework."
        )

    log.warning(
        "The .ca.state plot is deprecated and should no longer be used!\n"
        "Please use the .ca.caplot function, which is almost identical in its "
        "interface and uses the data transformation framework for data "
        "selection and pre-processing."
    )

    # Helper functions ........................................................

    def prepare_data(
        prop_name: str, *, all_data: dict, time_idx: int
    ) -> np.ndarray:
        """Prepares the data for plotting"""
        return all_data[prop_name][time_idx]

    # Prepare the data ........................................................
    # Get the group that all datasets are in
    grp = uni["data"][model_name]

    # Collect all data
    all_data = {p: grp[p] for p in to_plot.keys()}
    shapes = [d.shape for p, d in all_data.items()]

    if any([shape != shapes[0] for shape in shapes]):
        raise ValueError(
            "Shape mismatch of properties {}: {}! Cannot plot."
            "".format(", ".join(to_plot.keys()), shapes)
        )

    # Can now be sure they all have the same shape,
    # so its fine to take the first shape to extract the number of steps
    num_steps = shapes[0][0]

    structure = prepare_data(
        list(to_plot.keys())[0], all_data=all_data, time_idx=0
    ).attrs.get("grid_structure", "square")

    # Prepare the figure ......................................................
    # Prepare the figure to have as many columns as there are properties
    hlpr.setup_figure(
        ncols=len(to_plot), scale_figsize_with_subplots_shape=True
    )
    if structure == "hexagonal":
        old_figsize = hlpr.fig.get_size_inches()  # (width, height)
        hlpr.fig.set_size_inches(
            old_figsize[0] * 1.25,
            old_figsize[1],
        )

    # Store the imshow objects such that only the data has to be updated in a
    # following iteration step. Keys will be the property names.
    ims = dict()

    # Do the single plot for all properties, looping through subfigures
    for col_no, (prop_name, props) in enumerate(to_plot.items()):
        # Select the axis
        hlpr.select_axis(col_no, 0)

        # For hexagonal grids, add custom colorbar axis
        if structure == "hexagonal":
            divider = make_axes_locatable(hlpr.ax)
            cax = divider.append_axes("right", size="5%", pad=0.2)
            hlpr.select_axis(col_no, 0)

        # Get the data for this time step
        data = prepare_data(prop_name, all_data=all_data, time_idx=time_idx)

        # In the first time step create a new imshow object
        ims[prop_name] = _plot_ca_property(
            prop_name,
            data=data,
            hlpr=hlpr,
            default_imshow_kwargs=default_imshow_kwargs,
            **props,
        )

    # End of single frame CA state plot function ..............................
    # The above variables are all available below, but the update function is
    # supposed to start plotting anew starting from frame 0.

    def update_data():
        """Updates the data of the imshow objects"""
        log.info(
            "Plotting animation with %d frames of %d %s each ...",
            num_steps,
            len(to_plot),
            "property" if len(to_plot) == 1 else "properties",
        )

        for time_idx in range(num_steps):
            log.debug("Plotting frame for time index %d ...", time_idx)

            # Loop through the columns
            for col_no, (prop_name, props) in enumerate(to_plot.items()):
                # Select the axis
                hlpr.select_axis(col_no, 0)

                # Get the data for this time step
                data = prepare_data(
                    prop_name, all_data=all_data, time_idx=time_idx
                )

                # Get the structure of the grid data
                structure = data.attrs.get("grid_structure", "square")

                # For hexagonal grids recreate the plot each time.
                # Just resetting the data does not show the updated states
                # otherwise because the facecolors have to be updated, too.
                # For other grid structures just update the data and colormap.
                if structure == "hexagonal":
                    ims[prop_name] = plot_property(
                        prop_name,
                        data=data,
                        hlpr=hlpr,
                        default_imshow_kwargs=default_imshow_kwargs,
                        **props,
                    )

                else:
                    # Update imshow data without creating a new object
                    ims[prop_name].set_data(data.T)

                    # If no limits are provided, autoscale the new limits in
                    # the case of continuous colormaps. A discrete colormap,
                    # that is provided as a dict, should never have to
                    # autoscale.
                    if not isinstance(props.get("cmap"), dict):
                        if not props.get("limits"):
                            ims[prop_name].autoscale()

            # Done with this frame; yield control to the animation framework
            # which will grab the frame...
            yield

        log.info("Animation finished.")

    # Register this update method with the helper, which takes care of the rest
    hlpr.register_animation_update(update_data)
