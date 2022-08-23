"""This module provides plotting functions to visualize cellular automata."""

import copy
import logging
import warnings
from math import ceil, sqrt
from typing import Callable, Dict, Sequence, Tuple, Union

import matplotlib as mpl
import matplotlib.collections
import matplotlib.image
import matplotlib.patches
import matplotlib.transforms
import numpy as np
import xarray as xr
from dantro.abc import AbstractDataContainer
from matplotlib.colors import ListedColormap
from mpl_toolkits.axes_grid1 import make_axes_locatable

from ...tools import recursive_update
from .. import DataManager, UniverseGroup
from . import PlotHelper, UniversePlotCreator, is_plot_func

log = logging.getLogger(__name__)

# Increase log threshold for animation module
logging.getLogger("matplotlib.animation").setLevel(logging.WARNING)


# -----------------------------------------------------------------------------


def _prepare_hexgrid_data(
    data: Union[np.ndarray, xr.DataArray], *, x: str = None, y: str = None
) -> Tuple[xr.DataArray, str, str]:
    """Prepares data for :py:func:`imshow_hexagonal` by checking the given data
    and specified dimension names are consistent.
    """
    if not isinstance(data, xr.DataArray):
        data = xr.DataArray(data)

    if data.ndim != 2:
        raise ValueError(
            "Need 2-dimensional data for hexagonal grid plot, but got "
            f"{data.ndim}-dimensional data!\n{str(data)}"
        )

    # May not have dimension arguments given, e.g. because this was a data
    # array. Assume that it's fine to just use the available two.
    # For simplicity, we don't allow to give only one of them.
    if not x and not y:
        x, y = data.dims

    elif x == y:
        raise ValueError(
            "Dimension names `x` and `y` need to be different, "
            f"but were '{x}' and '{y}', respectively!"
        )

    elif (x is None) != (y is None):
        raise ValueError(
            "Need either both `x` and `y` dimension names or neither!"
        )

    # Make sure data dimensions are ordered correctly
    data = data.transpose(x, y)

    return data, x, y


def _flatten_hexgrid_data(data: xr.DataArray) -> np.ndarray:
    """Flattens hexgrid data in a specific way.

    For consistency, this function should be used when calling
    :py:meth:`~matplotlib.collections.PolyCollection.set_array` on collections
    that represent hexagonal grid data.
    """
    return data.data.T.flatten()


# .............................................................................

# TODO Register imshow_hexagonal for facet grid


def imshow_hexagonal(
    data: Union[xr.DataArray, np.ndarray],
    *,
    ax: "matplotlib.axes.Axes" = None,
    x: str = None,
    y: str = None,
    grid_properties: dict = {},
    update_grid_properties: dict = {},
    grid_properties_keys: dict = {},
    extent: tuple = None,
    scale: float = 1.01,
    draw_centers: bool = False,
    draw_center_radius: float = 0.08,
    draw_center_kwargs: dict = {},
    hide_ticks: bool = None,
    cmap: str = None,
    norm: str = None,
    vmin: float = None,
    vmax: float = None,
    collection_kwargs: dict = {},
    **im_kwargs,
) -> mpl.image.AxesImage:
    """Visualizes data using a grid of hexagons (⬢ or ⬣).

    Owing to the many ways in which a hexagonal grid can be visualized,
    this function requires additional information compared to
    :py:meth:`~matplotlib.axes.Axes.imshow`. These so called *grid properties*
    need to be passed via the ``grid_properties`` argument or directly
    alongside the data via ``data.attrs`` (for :py:class:`~xarray.DataArray`).

    The following grid properties are available:

        coordinate_mode (str):
            In which way the data is stored. Currently only supports
            ``offset`` mode, i.e. with offset row and column coordinates.
            No coordinates actually need to be (or can be) given, they are
            completely deduced from the
        pointy_top (bool):
            Whether the hexagons have a pointy top (⬢) or a flat top (⬣).
            More precisely, with a pointy top, there is only a single vertex
            at the top and bottom of the hexagon (i.e. along the ``y``
            dimension and the top/bottom of the resulting plot).
        offset_mode (str):
            Whether ``even`` or ``odd`` rows or columns are offset towards
            higher values. In other words:
            For pointy tops, offset every second *row* toward the right.
            For flat tops, offset every second *column* towards the top.
            Offset distance is half a cell's width and half a cell's height,
            respectively.
        space_size (Tuple[float, float], optional):
            The size of the space in ``(width, height)`` that the hexagonal
            grid cells cover.
            If given, will make the assumption that the available number of
            hexagons in each dimension reach from one end of the space to the
            other, even if that means that the hexagons become distorted along
            the dimensions.
            If *not* given, will assume regular hexagons and use arbitrary
            units to cover the space; these hexagons will *not* be distorted.
        space_offset (Tuple[float, float], optional):
            Offsets the space by ``(offset_x, offset_y)``.
            Also applies to the case where ``space_size`` was not given.
        space_boundary (str, optional):
            Whether the space (regardless of explicitly given or deduced)
            describes the ``outer`` or ``inner`` boundary of the hexagonal
            grid. The ``outer`` boundary (default) goes through the outermost
            vertices of the outermost cells.
            The ``inner`` boundary goes through some hexagon center, cutting
            off pointy tops and protruding parts of the hexagons such that the
            whole space is covered by hexagonal cells.

    For example, grid properties may look like this:

    .. code-block:: yaml

        grid_properties:
          # -- Required:
          coordinate_mode: offset
          pointy_top: true
          offset_mode: even

          # -- Optional:
          space_size: [10, 10]
          space_offset: [-5, -5]
          space_boundary: outer

    .. hint::

        For an excellent introduction to hexagonal grid representations, see
        `this article <https://www.redblobgames.com/grids/hexagons/>`_.

    Args:
        data (Union[xarray.DataArray, numpy.ndarray]): 2D array-like data that
            holds the grid information that is to be plotted.
            If the data is given as :py:class:`~xarray.DataArray`, its
            ``attrs`` are used to *update* the given ``grid_properties``.
        ax (matplotlib.axes.Axes, optional): The axes to draw to; if not given,
            will use the current axes.
        x (str, optional): Name of the data dimension that is to be represented
            on the x-axis of the plot. If not given, will use the first data
            dimension.
        y (str, optional): Name of the data dimension that is to be represented
            on the x-axis of the plot. If not given, will use the second data
            dimension.
        grid_properties (dict, optional): The grid properties dict, which needs
            to specify the above properties in order to determine how to
            represent the data. This dict is first updated with potentially
            available ``data.attrs`` and subsequently updated with the
            ``update_grid_properties``.
        update_grid_properties (dict, optional): Updates the grid properties,
            see above.
        grid_properties_keys (dict, optional): A mapping that can be used if
            the given data has grid properties given under different names.
            For instance, ``{"space_size": "size"}`` would read the ``size``
            entry instead of ``space_size``.
        extent (tuple, optional): A custom space *extent*, denoting the edges
            ``(left, right, bottom, top)`` of the domain *in data units*.
        scale (float, optional): A scaling factor for the size of the hexagons.
            The default value is very slightly larger than 1 to reduce aliasing
            artefacts on exactly overlapping hexagon edges. Scaling is uniform.
        draw_centers (bool, optional): Whether to additionally draw the center
            points of all hexagons.
        draw_center_radius (float, optional): The relative radius of the
            center points in units of ``min(cell_width, cell_height) / 2``.
        draw_center_kwargs (dict, optional): Additional arguments that are
            passed to the :py:class:`~matplotlib.collections.PatchCollection`
            used to draw the center points.
        hide_ticks (bool, optional): Whether to hide the ticks and tick labels.
            If None, will hide ticks if no ``space_size`` grid property was
            given (in which case the units are assumed irrelevant).
        cmap (str, optional): The colormap to use
        norm (str, optional): The normalization to use
        vmin (float, optional): The minimum value of the color range to use
        vmax (float, optional): The maximum value of the color range to use
        collection_kwargs (dict, optional): Passed on to the
            :py:class:`~matplotlib.collections.PolyCollection` that is used to
            represent the hexagons.
        **im_kwargs: Passed on to :py:class:`matplotlib.image.AxesImage` that
            is created from the whole axis.
            Can be used to set ``interpolation`` or similar options.

    Returns:
        matplotlib.image.AxesImage:
            The imshow-like object containing the hexagonal grid.
    """
    # .. constants ............................................................
    sqrt_3 = np.sqrt(3)  # 2 * sin(60°)

    # Regular unit hexagon vertices in clockwise direction.
    # Define one with a pointy and one with a flat top (easier than rotating).
    unit_hexagon_pointy_top = np.array(
        [
            [0, 1],
            [sqrt_3 / 2, +1 / 2],
            [sqrt_3 / 2, -1 / 2],
            [0, -1],
            [-sqrt_3 / 2, -1 / 2],
            [-sqrt_3 / 2, +1 / 2],
        ]
    )
    unit_hexagon_flat_top = np.array(
        [
            [1, 0],
            [+1 / 2, sqrt_3 / 2],
            [-1 / 2, sqrt_3 / 2],
            [-1, 0],
            [-1 / 2, -sqrt_3 / 2],
            [+1 / 2, -sqrt_3 / 2],
        ]
    )

    # .. Prepare data .........................................................

    # Bring data into a uniform shape: 2D xr.DataArray
    data, x, y = _prepare_hexgrid_data(data, x=x, y=y)

    # Aggregate grid properties
    grid_properties = grid_properties if grid_properties else {}
    grid_properties.update(data.attrs)
    grid_properties.update(
        update_grid_properties if update_grid_properties else {}
    )
    if not grid_properties:
        raise ValueError(
            "Could not determine grid properties! "
            "Either pass them explicitly via the `grid_properties` or "
            "`update_grid_properties` arguments or, if `data` is given as "
            "an xr.DataArray, add them to `data.attrs`."
        )

    # .. Get hexgrid information ..............................................
    GRID_PROP_KEYS = (
        "coordinate_mode",
        "pointy_top",
        "offset_mode",
        "space_size",
        "space_offset",
        "space_boundary",
    )
    _keys = {k: grid_properties_keys.get(k, k) for k in GRID_PROP_KEYS}

    # Extract attribute values
    coordinate_mode = grid_properties[_keys["coordinate_mode"]]
    pointy_top = grid_properties[_keys["pointy_top"]]
    offset_mode = grid_properties[_keys["offset_mode"]]
    space_size = grid_properties.get(_keys["space_size"])
    space_offset = grid_properties.get(_keys["space_offset"], (0.0, 0.0))
    boundary = grid_properties.get(_keys["space_boundary"], "outer")
    space_given = space_size is not None

    # May have an explicitly given extent, in which case the space size and
    # offset given by the grid properties needs to be overwritten.
    if extent:
        _l, _r, _b, _t = extent
        space_size = (abs(_r - _l), abs(_t - _b))
        space_offset = (min(_l, _r), min(_b, _t))

    # Check validity
    COORDINATE_MODES = ("offset",)
    if coordinate_mode not in COORDINATE_MODES:
        raise ValueError(
            f"Invalid coordinate mode '{coordinate_mode}'! "
            "Hexagonal grid property `coordinate_mode` needs to be one of:  "
            f"{', '.join(COORDINATE_MODES)}"
        )

    if offset_mode not in ("even", "odd"):
        raise ValueError(
            f"Invalid offset mode '{offset_mode}'! Hexagonal grid property "
            "`offset_mode` needs to be 'even' or 'odd'."
        )

    if boundary not in ("outer", "inner"):
        raise ValueError(
            f"Invalid space boundary '{boundary}'! Hexagonal grid property "
            "`space_boundary` needs to be 'outer' or 'inner'."
        )

    # .. Calculations .........................................................
    # Determine number of cells in x and y direction (of the final plot)
    n_x = data.sizes[x]
    n_y = data.sizes[y]

    ids_x = np.arange(n_x)
    ids_y = np.arange(n_y)

    # Issue a warning if there are too few cells.
    if n_x < 2 or n_y < 2:
        warnings.warn(
            "Plotting a hexagonal grid with fewer than two cells in any "
            "dimension may lead to unexpected results!",
            UserWarning,
        )

    # Decide on which unit hexagon to use
    if pointy_top:
        unit_hexagon = unit_hexagon_pointy_top
    else:
        unit_hexagon = unit_hexagon_flat_top

    # Depending on whether the space is known, need to go different ways:
    #   - If known, deduce s and scale hexagon accordingly.
    #   - If not known, use s = 1 and compute the size of the space instead.
    if space_given:
        # With a space given, the size of the hexagon may be different in the
        # x and y direction in order to cover the whole space with the
        # available number of cells.
        #
        # However, a scaled hexagon no longer has a characteristic size `s`,
        # but needs two parameters to describe the scaling: `lx` and `ly`.
        # These are slightly different than `s`, but depending on which pointy
        # end aligns with which dimension, one of them is equal to what would
        # be `s` in a regular hexagon.
        # To reduce pitfalls of using `s` further down, we deliberately do NOT
        # define it here.

        # First, compute the boundaries (lower, upper) along each dimension
        space_x = (space_offset[0], space_offset[0] + space_size[0])
        space_y = (space_offset[1], space_offset[1] + space_size[1])

        space_width, space_height = space_size

        # Now deduce the scaling factors, depending on pointyness and position
        # of the boundary:
        if pointy_top:
            if boundary == "outer":
                offs_corr = 1 if n_x > 1 else 0  # offset correction
                lx = 2 * space_width / (sqrt_3 * (2 * n_x + offs_corr))
                ly = 2 * space_height / (3 * n_y + 1)
            else:
                lx = 2 * space_width / (sqrt_3 * (2 * n_x - 1))
                ly = 2 * space_height / (3 * n_y - 1)

            cell_width = sqrt_3 * lx  # sic! lx is a scaling factor
            cell_height = 2 * ly

        else:
            # flat top
            if boundary == "outer":
                offs_corr = 1 if n_y > 1 else 0
                lx = 2 * space_width / (3 * n_x + 1)
                ly = 2 * space_height / (sqrt_3 * (2 * n_y + offs_corr))
            else:
                lx = 2 * space_width / (3 * n_x - 1)
                ly = 2 * space_height / (sqrt_3 * (2 * n_y - 1))

            cell_width = 2 * lx
            cell_height = sqrt_3 * ly  # sic! ly is a scaling factor

        # Scale and transform the hexagon accordingly.
        # This may lead to elongation along x or y dimensions.
        # Note the use of lx and ly here, not cell_width and cell_height.
        # This is because lx/ly == 1 if the hexagon is regular (the available
        # space's aspect ratio is 1:sqrt(3)/2 ).
        # In contrast, cell_width / cell_height will be sqrt(3)/2 == 1.15470…
        # for a unit hexagon, thus not suitable as scaling factors.
        hexagon = scale * np.array([lx, ly]) * unit_hexagon

    else:
        # Space was not given, can choose s and deduce space as we desire.
        #
        # Also, the hexagon will be regular: a _uniformly_ scaled unit hexagon.
        # Thus, we do not need to worry about scaling factors like above, but
        # the side length `s` alone suffices.
        s = 1

        hexagon = scale * s * unit_hexagon

        if pointy_top:
            cell_width = s * sqrt_3
            cell_height = 2 * s

            if boundary == "outer":
                offs_corr = 0.5 if n_x > 1 else 0
                space_x = (0.0, (n_x + offs_corr) * cell_width)
                space_y = (0.0, 3 / 2 * n_y * s + s / 2)
            else:
                space_x = (cell_width / 2, n_x * cell_width)
                space_y = (s / 2, 3 / 2 * n_y * s)
        else:
            # flat top
            cell_width = 2 * s
            cell_height = s * sqrt_3

            if boundary == "outer":
                offs_corr = 0.5 if n_y > 1 else 0
                space_x = (0.0, 3 / 2 * n_x * s + s / 2)
                space_y = (0.0, (n_y + offs_corr) * cell_height)
            else:
                space_x = (s / 2, 3 / 2 * n_x * s)
                space_y = (cell_height / 2, n_y * cell_height)

        space_size = (space_x[1], space_y[1])
        space_width, space_height = space_size

        space_x = (space_offset[0] + space_x[0], space_offset[0] + space_x[1])
        space_y = (space_offset[1] + space_y[0], space_offset[1] + space_y[1])

    # .. Compute cell positions . . . . . . . . . . . . . . . . . . . . . . . .
    # Temporary position values -- without row/col offsets!
    if pointy_top:
        if boundary == "outer":
            _pos_x = np.linspace(
                space_x[0] + cell_width / 2,
                space_x[1] - cell_width,  # due to row offset
                n_x,
            )
            _pos_y = np.linspace(
                space_y[0] + cell_height / 2,
                space_y[1] - cell_height / 2,
                n_y,
            )
        else:
            _pos_x = np.linspace(
                space_x[0],
                space_x[1] - cell_width / 2,  # due to row offset
                n_x,
            )
            _pos_y = np.linspace(
                space_y[0] + cell_height / 4,
                space_y[1] - cell_height / 4,
                n_y,
            )
    else:
        # flat top
        if boundary == "outer":
            _pos_x = np.linspace(
                space_x[0] + cell_width / 2,
                space_x[1] - cell_width / 2,
                n_x,
            )
            _pos_y = np.linspace(
                space_y[0] + cell_height / 2,
                space_y[1] - cell_height,  # due to col offset
                n_y,
            )
        else:
            _pos_x = np.linspace(
                space_x[0] + cell_width / 4,
                space_x[1] - cell_width / 4,
                n_x,
            )
            _pos_y = np.linspace(
                space_y[0],
                space_y[1] - cell_height / 2,  # due to col offset
                n_y,
            )

    # Bring into the form that's required for imshow
    x_offsets, y_offsets = np.meshgrid(_pos_x, _pos_y)

    # Add the offset towards higher values
    if pointy_top:
        if n_x > 1:
            offset = cell_width / 2
            if offset_mode == "even":
                x_offsets[ids_y % 2 == 0, ...] += offset
            else:
                x_offsets[ids_y % 2 == 1, ...] += offset
    else:
        if n_y > 1:
            offset = cell_height / 2
            if offset_mode == "even":
                y_offsets[..., ids_x % 2 == 0] += offset
            else:
                y_offsets[..., ids_x % 2 == 1] += offset

    # .. Create the PolyCollection ............................................
    # At this point, need the following information to generate the collection
    # of hexagons:
    #   - the appropriately transformed hexagon
    #   - x and y offsets (2D arrays, flattened and combined)

    collection_kwargs = collection_kwargs if collection_kwargs else {}

    # Here we go ...
    pcoll = mpl.collections.PolyCollection(
        [hexagon],
        offsets=np.transpose([x_offsets.flatten(), y_offsets.flatten()]),
        transOffset=mpl.transforms.AffineDeltaTransform(ax.transData),
        #
        # Pass collection-related kwargs
        linewidths=collection_kwargs.get("linewidths", 0),
        **collection_kwargs,
    )
    # NOTE There also is a RegularPolyCollection, but that is a massive pain
    #      because it expects the sizes to be given in units of the canvas
    #      (area in *points squared*), which depends on the representation and
    #      not on the data.
    #      The PolyCollection does not have that issue because the polygons
    #      need to be drawn "by hand". This way, all information can be
    #      supplied in units of data space when using the data transformation
    #      of the offsets.

    # Set the data in a (consistently) flattened form
    pcoll.set_array(_flatten_hexgrid_data(data))

    # Set cmap stuff and norm
    pcoll.set_cmap(cmap)
    pcoll.set_clim(vmin, vmax)
    pcoll.set_norm(norm)
    pcoll._scale_norm(norm, vmin, vmax)

    # .. Add to axis ..........................................................
    if ax is None:
        import matplotlib.pyplot as plt

        ax = plt.gca()

    ax.add_collection(pcoll)

    # Use same length scale in x and y and set space limits
    ax.set_aspect("equal")
    ax.set_xlim(*space_x)
    ax.set_ylim(*space_y)

    # Allow marking the center points of the hexagons
    #
    # Again need to use a manually created collection such that positions and
    # sizes can be given in data units.
    # The radius factor is a heuristic value for an "effective" `s` parameter
    # for the shorter side of the hexagon.
    if draw_centers:
        circle = mpl.patches.Circle(
            (0, 0),
            radius=min(cell_width, cell_height) / 2 * draw_center_radius,
        )
        draw_center_kwargs = draw_center_kwargs if draw_center_kwargs else {}
        ccoll = mpl.collections.PatchCollection(
            [circle],
            offsets=np.transpose([x_offsets.flatten(), y_offsets.flatten()]),
            transOffset=mpl.transforms.AffineDeltaTransform(ax.transData),
            #
            linewidths=draw_center_kwargs.pop("linewidths", 0),
            **draw_center_kwargs,
        )
        ax.add_collection(ccoll)

    # If space was not known, don't show axis labels
    if hide_ticks or (not space_given and hide_ticks is None):
        ax.tick_params(
            axis="both",
            left=False,
            top=False,
            right=False,
            bottom=False,
            labelleft=False,
            labeltop=False,
            labelright=False,
            labelbottom=False,
        )

    # Create axes image to have the same result object as imshow does,
    # including interpolation features etc
    im = mpl.image.AxesImage(ax, **im_kwargs)
    im.hexagons = pcoll

    # Do some post-processing
    im.set_cmap(cmap)
    im.set_clim(vmin, vmax)

    # Some callbacks
    # def on_changed(collection):
    #     hbar.set_cmap(collection.get_cmap())
    #     hbar.set_clim(collection.get_clim())
    #     vbar.set_cmap(collection.get_cmap())
    #     vbar.set_clim(collection.get_clim())

    # pcoll.callbacks.connect("changed", on_changed)

    return im


# -----------------------------------------------------------------------------


def _plot_ca_property(
    prop_name: str,
    *,
    hlpr: PlotHelper,
    data: xr.DataArray,
    default_imshow_kwargs: dict,
    default_cbar_kwargs: dict = None,
    grid_structure: str = None,
    limits: Tuple[float, float] = None,
    cmap: Union[str, dict] = None,
    norm: Union[str, dict] = None,
    draw_cbar: bool = True,
    set_axis_off: bool = True,
    title: str = None,
    no_cbar_markings: bool = False,
    imshow_kwargs: dict = None,
    **cbar_kwargs,
) -> mpl.image.AxesImage:
    """Helper function, used in :py:func:`caplot` and :py:func:`state` to plot
    a property on the given axis. Returns the created axes image object.

    .. note::

        The arguments here are those within the individual entries of the
        ``to_plot`` argument for the above plotting functions.

    Args:
        prop_name (str): The property to plot
        hlpr (PlotHelper): The plot helper
        data (xarray.DataArray): The array-like data to plot as an image
        default_imshow_kwargs (dict): Default arguments for the imshow call,
            updated with individually-specified ``imshow_kwargs``.
        default_cbar_kwargs (dict): Default arguments for the colorbar
            creation, updated with ``cbar_kwargs``.
        grid_structure (str, optional): Can be used to
        limits (Tuple[float, float], optional): The imshow limits to use; will
            also be the limits of the colorbar.
        cmap (Union[str, dict], optional): The colormap to use. If a dict is
            given, defines a (discrete) ``ListedColormap`` from the values.
        norm (Union[str, dict], optional): Description
        draw_cbar (bool, optional): whether to draw a color bar
        set_axis_off (bool, optional): Description
        title (str, optional): The subplot figure title
        no_cbar_markings (bool, optional): Whether to suppress colorbar
            markings (ticks and tick labels)
        imshow_kwargs (dict, optional): Depending on grid structure, is passed
            on either to :py:meth:`~matplotlib.axes.Axes.imshow` or to
            :py:func:`.imshow_hexagonal`.
        **cbar_kwargs: Passed to :py:meth:`matplotlib.figure.Figure.colorbar`

    Returns:
        matplotlib.image.AxesImage:
            The created axes image representing the CA property.

    Raises:
        TypeError: on invalid ``cmap`` argument.
        ValueError: on invalid grid structure; supported structures are
            ``square`` and ``hexagonal``
    """
    # Get colormap, either a continuous or a discrete one
    discrete_cmap = dict()
    if cmap is None or isinstance(cmap, str):
        cmap = mpl.cm.get_cmap(name=cmap)

    elif isinstance(cmap, dict):
        if not limits:
            raise ValueError(
                "When giving a dict-like `cmap` argument, need to also "
                "provide the `limits` argument."
            )

        discrete_cmap["labels"] = cmap.keys()
        discrete_cmap["n_colors"] = len(cmap)
        cmap = ListedColormap(cmap.values())
        norm = mpl.colors.BoundaryNorm(limits, cmap.N)

    else:
        raise TypeError(
            "Argument `cmap` needs to be either a string with name of the "
            "colormap or a dict with values for a discrete colormap! "
            f"Was {type(cmap).__name__} with value:  {repr(cmap)}"
        )

    # Fill imshow_kwargs, using defaults
    imshow_kwargs = imshow_kwargs if imshow_kwargs else {}
    imshow_kwargs = recursive_update(
        copy.deepcopy(default_imshow_kwargs) if default_imshow_kwargs else {},
        copy.deepcopy(imshow_kwargs),
    )

    # Determine vmin and vmax
    if limits:
        vmin, vmax = limits
        imshow_kwargs["vmin"] = vmin
        imshow_kwargs["vmax"] = vmax

    # Create imshow(-like) object on the currently selected axis
    grid_structure = (
        grid_structure
        if grid_structure
        else data.attrs.get("grid_structure", "square")
    )
    if grid_structure == "square" or grid_structure is None:
        im = hlpr.ax.imshow(
            data.T,
            cmap=cmap,
            animated=True,
            rasterized=True,
            origin="lower",
            aspect="equal",
            **imshow_kwargs,
        )

    elif grid_structure == "hexagonal":
        im = imshow_hexagonal(
            data=data,
            ax=hlpr.ax,
            animated=True,
            rasterized=True,
            cmap=cmap,
            **imshow_kwargs,
        )

    else:
        raise ValueError(
            f"Unsupported grid structure '{grid_structure}'!\n"
            "Choose from:  square, hexagonal"
        )

    # Remove main axis labels and ticks and provide some default options
    if set_axis_off:
        hlpr.ax.axis("off")

    hlpr.provide_defaults("set_title", title=(title if title else prop_name))

    # .. Colorbar .............................................................
    if not draw_cbar:
        return im
    # else: draw the colorbar

    # Parse colorbar kwargs, setting some default values
    default_cbar_kwargs = default_cbar_kwargs if default_cbar_kwargs else {}
    cbar_kwargs = recursive_update(
        copy.deepcopy(default_cbar_kwargs), cbar_kwargs
    )
    cbar_kwargs["fraction"] = cbar_kwargs.get("fraction", 0.05)
    cbar_kwargs["pad"] = cbar_kwargs.get("pad", 0.02)

    # For hexagonal grids, need to attach the PolyCollection, because it holds
    # the data array.
    artist = im
    if grid_structure == "hexagonal":
        artist = im.hexagons

    cbar = hlpr.fig.colorbar(artist, ax=hlpr.ax, ticks=limits, **cbar_kwargs)

    # For a discrete colormap, adjust the tick positions
    # FIXME breaks with limits not starting at 0 or one of them being None
    if discrete_cmap:
        n_colors = discrete_cmap["n_colors"]
        tick_locs = (np.arange(n_colors) + 0.5) * (n_colors - 1) / n_colors
        cbar.set_ticks(tick_locs)
        cbar.ax.set_yticklabels(discrete_cmap["labels"])
        # FIXME what if this was horizontal?!

    # Remove markings, if configured to do so
    if draw_cbar and no_cbar_markings:
        cbar.set_ticks([])
        cbar.ax.set_yticklabels([])

    # Store the cbar object in the AxesImage to have it accessible later
    im.cbar = cbar

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
    default_cbar_kwargs: dict = None,
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

    For plotting square grids, :py:meth:`matplotlib.axes.Axes.imshow` is used,
    :py:func:`imshow_hexagonal` is used for hexagonal grids.

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
                - ``label`` (str, optional): A label for the colorbar
                - ``**kwargs``: passed on to the imshow invocation, i.e. to
                    :py:meth:`~matplotlib.axes.Axes.imshow` or to
                    :py:meth:`imshow_hexagonal`.

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
        default_cbar_kwargs (dict, optional): The default parameters for the
            colorbar that is added to applicable subplots. These are updated
            by the parameters given under ``to_plot``.
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
        _avail = ", ".join(ds.coords.keys())
        raise ValueError(
            f"Invalid `frames` coordinate dimension '{frames}'! "
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
                f"the same but were:  {structures}\n"
                "This may have resulted from data attributes being lost in a "
                "data transformation. If so, one alternative to re-adding the "
                "data attributes (via the `update_with_attrs_from` operation) "
                "is to specify `grid_structure` explicitly. "
                "For hexagonal grids, grid properties can also be passed via "
                "`imshow_kwargs.grid_properties`."
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
            "Dataset shape needs to be 3-dimensional, but was: "
            f"{dict(ds.sizes)}! Full dataset:\n{ds}"
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
    if not size:
        size = mpl.rcParams["figure.figsize"][1]
    figsize = (size * (aspect + aspect_pad), size)

    # Create the figure and set all axes as invisible. This is needed because
    # col_wrap may lead to some subplots being completely empty.
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

        # Select the appropriate data, then plot the data variable
        data = select_data(ds, prop_name, {frames: 0})

        ims[prop_name] = _plot_ca_property(
            prop_name,
            hlpr=hlpr,
            data=data,
            grid_structure=grid_structure,
            default_imshow_kwargs=default_imshow_kwargs,
            default_cbar_kwargs=default_cbar_kwargs,
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

        # Determine whether a autoscaling is needed for a property:
        # If no limits are provided, need to autoscale the new limits in the
        # case of continuous colormaps. A discrete colormap provided as a dict
        # should never have to autoscale.
        needs_autoscale = {
            n: (not p.get("limits") and not isinstance(p.get("cmap"), dict))
            for n, p in to_plot.items()
        }

        # Frame iteration
        for frame_idx in range(num_frames):
            log.debug("Plotting frame %d ...", frame_idx)

            for i, (prop_name, props) in enumerate(to_plot.items()):
                hlpr.select_axis(**axis_map[prop_name])

                frame_data = select_data(ds, prop_name, {frames: frame_idx})

                # Depending on grid structure, update data or plot anew
                if grid_structure == "hexagonal":
                    # Update imshow_hexagonal data according as would otherwise
                    # happen inside that function
                    frame_data, _, _ = _prepare_hexgrid_data(
                        frame_data, x=props.get("x"), y=props.get("y")
                    )
                    ims[prop_name].hexagons.set_array(
                        _flatten_hexgrid_data(frame_data)
                    )

                    if needs_autoscale[prop_name]:
                        ims[prop_name].hexagons.autoscale()

                else:
                    # Update imshow data without creating a new object
                    ims[prop_name].set_data(frame_data.T)

                    if needs_autoscale[prop_name]:
                        ims[prop_name].autoscale()

                # Use the first subplot's data for setting the figure suptitle
                if i == 0:
                    set_suptitle(frame_data)

            # Done with this frame; yield control to the animation framework.
            yield

    # Register this update method with the helper, which takes care of the rest
    hlpr.register_animation_update(update_data)


# -----------------------------------------------------------------------------


@is_plot_func(creator="universe", supports_animation=True)
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

    if structure != "square":
        raise ValueError(
            "Legacy CA plot no longer supports non-square grid structure "
            f"'{structure}'! Use the modern caplot (`.plot.ca`) instead."
        )

    # Prepare the figure ......................................................
    # Prepare the figure to have as many columns as there are properties
    hlpr.setup_figure(
        ncols=len(to_plot), scale_figsize_with_subplots_shape=True
    )

    # Store the imshow objects such that only the data has to be updated in a
    # following iteration step. Keys will be the property names.
    ims = dict()

    # Do the single plot for all properties, looping through subfigures
    for col_no, (prop_name, props) in enumerate(to_plot.items()):
        # Select the axis
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
                hlpr.select_axis(col_no, 0)
                data = prepare_data(
                    prop_name, all_data=all_data, time_idx=time_idx
                )

                # Update imshow data without creating a new object
                ims[prop_name].set_data(data.T)

                # If no limits are provided, autoscale the new limits in
                # the case of continuous colormaps. A discrete colormap,
                # that is provided as a dict, should never have to autoscale.
                if not isinstance(props.get("cmap"), dict):
                    if not props.get("limits"):
                        ims[prop_name].autoscale()

            # Done with this frame; yield control to the animation framework
            # which will grab the frame...
            yield

        log.info("Animation finished.")

    # Register this update method with the helper, which takes care of the rest
    hlpr.register_animation_update(update_data)
