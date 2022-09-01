"""Implements data container classes specialised on Utopia output data.

It is based on the :py:class:`dantro.base.BaseDataContainer` classes,
especially their numeric form, the
:py:class:`~dantro.containers.numeric.NumpyDataContainer` and the
:py:class:`~dantro.containers.xr.XrDataContainer`.
"""

import copy
import logging
from typing import Sequence, Tuple, Union

import dantro.containers
import dantro.mixins
import numpy as np
import xarray as xr

from ..tools import yaml as _yaml

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


class NumpyDC(
    dantro.mixins.Hdf5ProxySupportMixin, dantro.containers.NumpyDataContainer
):
    """This is the base class for numpy data containers used in Utopia.

    It is based on the NumpyDataContainer provided by dantro and extends it
    with the Hdf5ProxySupportMixin, allowing to load the data from the Hdf5
    file only once it becomes necessary.
    """


class XarrayDC(
    dantro.mixins.Hdf5ProxySupportMixin, dantro.containers.XrDataContainer
):
    """This is the base class for xarray data containers used in Utopia.

    It is based on the XrDataContainer provided by dantro. As of now, it has
    no proxy support, but will gain it once available on dantro side.
    """

    # Configure proxy support .................................................
    PROXY_RESOLVE_ASTYPE = None
    """Which type to resolve the proxy to.
    None defaults to :py:class:`numpy.ndarray`."""

    PROXY_RETAIN = True
    """Whether to retain a proxy after resolving it; allows reinstating
    proxy objects."""

    PROXY_REINSTATE_FAIL_ACTION = "log_warning"
    """Which action to take if reinstating a proxy was not possible"""

    # Specialize XrDataContainer for Utopia ...................................
    _XRC_DIMS_ATTR = "dim_names"
    """Define as class variable the name of the attribute that determines the
    dimensions of the :py:class:`xarray.DataArray`.
    """

    _XRC_DIM_NAME_PREFIX = "dim_name__"
    """Attributes prefixed with this string can be used to set names for
    specific dimensions. The prefix should be followed by an integer-parsable
    string, e.g. ``dim_name__0`` would be the dimension name for the 0th dim
    """

    _XRC_COORDS_ATTR_PREFIX = "coords__"
    """Attributes prefixed with this string determine the coordinate values for
    a specific dimension. The prefix should be followed by the _name_ of the
    dimension, e.g. ``coords__time``. The values are interpreted according to
    the default coordinate mode or, if given, the ``coords_mode__*`` attribute
    """

    _XRC_COORDS_MODE_DEFAULT = "values"
    """The default mode by which coordinates are interpreted. See the base
    class, :py:class:`dantro.containers.xr.XrDataContainer` for more
    information.

    Available modes:
      - ``values``: the explicit values (iterable) to use for coordinates
      - ``trivial``: The trivial indices; ignores the coordinate argument
      - ``scalar``: makes sure only a single coordinate is provided
      - ``range``: python built-in range function arguments
      - ``arange``: np.arange arguments
      - ``linspace``: np.linspace arguments
      - ``logspace``: np.logspace arguments
      - ``start_and_step``: the start and step values of an integer range
          expression; the stop value is deduced by looking at the length
          of the corresponding dimension.
      - ``linked``: Load the coordinates from a linked object within the
          tree, specified by a relative path from the current object.
    """

    _XRC_COORDS_MODE_ATTR_PREFIX = "coords_mode__"
    """Prefix for the coordinate mode if a custom mode is to be used.
    To, e.g., use mode ``start_and_step`` for time dimension, set the
    ``coords_mode__time`` attribute to value ``start_and_step``
    """

    _XRC_INHERIT_CONTAINER_ATTRIBUTES = False
    """Whether to inherit the other container attributes"""

    _XRC_STRICT_ATTR_CHECKING = True
    """Whether to use strict attribute checking; throws errors if there are
    container attributes available that match the prefix but don't match a
    valid dimension name. Can be disabled for speed improvements.
    """


# -----------------------------------------------------------------------------


class XarrayYamlDC(XarrayDC):
    """An :py:class:`.XarrayDC` specialization that assumes that each array
    entry is a YAML string, which is subsequently loaded. This can be done
    alongside the metadata application of the :py:class:`.XarrayDC`.
    """

    def _apply_metadata(self):
        """Whenever metadata is applied that is also a good point to resolve
        the YAML data...
        """
        super()._apply_metadata()

        def convert_to_yaml(element) -> dict:
            """Given an array element, try to convert it to yaml"""
            try:
                if isinstance(element, bytes):
                    return _yaml.load(element.decode("utf8"))
                return _yaml.load(element)

            except Exception as exc:
                raise ValueError(
                    f"Could not convert element of type {type(element)} to "
                    f"yaml! Element value was:  {element}"
                ) from exc

        self._data = xr.apply_ufunc(np.vectorize(convert_to_yaml), self._data)


# -----------------------------------------------------------------------------


class GridDC(XarrayDC):
    """This is the base class for all grid data used in Utopia.

    It is based on the :py:class:`.XarrayDC` and reshapes the data to the grid
    shape. The last dimension is assumed to be the dimension that goes along
    the grid cell IDs.
    """

    # Define class variables to allow specializing behaviour ..................
    _GDC_grid_shape_attr = "grid_shape"
    """The attribute to read the desired grid shape from"""

    _GDC_space_extent_attr = "space_extent"
    """The attribute to read the space extent from"""

    _GDC_index_order_attr = "index_order"
    """The attribute to read the index order from"""

    _GDC_grid_structure_attr = "grid_structure"
    """The attribute to read the desired grid structure from"""

    # .........................................................................

    def __init__(
        self, *, name: str, data: Union[np.ndarray, xr.DataArray], **dc_kwargs
    ):
        """Initialize a GridDC which represents grid-like data.

        Given the container attribute (see :py:attr:`._GDC_grid_shape_attr`),
        this container takes care to reshape the underlying data such that it
        represents that grid, even if it is saved in another shape.

        .. note::

            Use this container if it is easier to store array data in a flat
            format (e.g. because there is no need to take care of slicing etc)
            but you still desire to work with it in its actual shape.

        Args:
            name (str): The name of this container
            data (Union[numpy.ndarray, xarray.DataArray]): The not yet
                reshaped data. If this is 1D, it is assumed that there is no
                additional dimension.
                If it is 2D (or more), it is assumed to be ``(..., cell ids)``.
            **kwargs: Further initialization kwargs, e.g. ``attrs`` ...
        """
        # To prohibit proxy resolution in the below __init__, need a flag
        self._shapes_cached = False

        # Call the __init__ function of the base class
        super().__init__(name=name, data=data, **dc_kwargs)
        # ._data is an xr.DataArray now or might still be a proxy

        # Store the old and determine the new shape of the data; needed for
        # proxy property support
        self._data_shape = self.shape

        # Now, determine the shapes ... Will set the following attributes:
        self._new_shape = None
        self._grid_shape = None
        self._new_dims = None
        self._new_coords = None
        self._determine_shape()

        # Have all shapes cached now; set the flag such that the properties
        # use those values instead of the proxy's
        self._shapes_cached = True

        # Do the reshaping and everything only if it is not a proxy
        if not self.data_is_proxy:
            self._data = self._reshape_data()
        # otherwise: postpone reshaping until proxy gets resolved

    def _postprocess_proxy_resolution(self):
        """Invoked from
        :py:class:`~dantro.mixins.proxy_support.Hdf5ProxySupportMixin` after a
        proxy was resolved, this takes care to apply the reshaping operation
        onto the underlying data.
        """
        super()._postprocess_proxy_resolution()
        self._data = self._reshape_data()

    def _parse_sizes_from_metadata(self) -> Sequence[Tuple[str, int]]:
        """Invoked from _format_shape when no metadata was applied but the
        dimension names are available. Should return data in the same form as
        ``xr.DataArray.sizes.items()`` does.
        """
        if not self._shapes_cached:
            return super()._parse_sizes_from_metadata()

        # Iterate over new dimension names and grid shape and use the dim names
        # and shape determined and cached by _determine_shape.
        return tuple(
            (n, l) for i, (n, l) in enumerate(zip(self._new_dims, self.shape))
        )

    # Properties ..............................................................

    @property
    def grid_shape(self) -> tuple:
        """The shape of the grid"""
        if self._shapes_cached:
            return self.shape[1:]
        return self.attrs.get(self._GDC_grid_shape_attr)

    @property
    def space_extent(self) -> tuple:
        """The space's extent this grid is representing, read from attrs"""
        return self.attrs.get(self._GDC_space_extent_attr)

    @property
    def shape(self) -> tuple:
        """Returns shape, proxy-aware

        This is an overload of the property in Hdf5ProxySupportMixin which
        takes care that not the actual underlying proxy data shape is returned
        but whatever the container's shape is to be after reshaping.
        """
        if self.data_is_proxy:
            # Might not be set yet, i.e. during call to super().__init__
            if self._shapes_cached:
                return self._new_shape
            return self.proxy.shape
        return self.data.shape

    @property
    def ndim(self) -> int:
        """Returns ndim, proxy-aware

        This is an overload of the property in Hdf5ProxySupportMixin which
        takes care that not the actual underlying proxy data ndim is returned
        but whatever the container's ndim is to be after reshaping.
        """
        if self.data_is_proxy:
            return len(self.shape)
        return self.data.ndim

    # Reshaping ...............................................................

    def _determine_shape(self):
        """Determine the new shape and store it as ``_new_shape`` attribute"""
        try:
            self._grid_shape = tuple(self.attrs[self._GDC_grid_shape_attr])

        except KeyError as err:
            raise ValueError(
                "Missing attribute '{}' in {} to extract the "
                "desired grid shape from! Available: {}"
                "".format(
                    self._GDC_grid_shape_attr,
                    self.logstr,
                    ", ".join(self.attrs.keys()),
                )
            ) from err

        # To get the new shape, add up the old data shape without the grid
        # dimension and the expected grid shape.
        # NOTE It is assumed that the _last_ dimension goes along cell IDs and
        #      the reshaped x-y data dimensions are thus appended.
        self._new_shape = tuple(self._data_shape[:-1] + self._grid_shape)

        # New shape is now calculated, data shape is still the same
        data_shape = self._data_shape
        new_shape = self._new_shape
        grid_shape = self._grid_shape

        # Determine new dimension names
        if len(data_shape) == 2:
            new_dims = ("time",) + ("x", "y", "z")[: len(grid_shape)]

        elif len(data_shape) == 1:
            new_dims = ("x", "y", "z")[: len(grid_shape)]

        else:
            raise ValueError(
                f"Can only reshape from 1D or 2D data, got {data_shape}!"
            )

        # Determine new coordinates
        new_coords = dict()

        # If there is a space extent attribute available, use that to set the
        # spatial coordinates. Otherwise, assign the trivial coordinates.
        extent = self.attrs.get(self._GDC_space_extent_attr)
        structure = self.attrs.get(self._GDC_grid_structure_attr)
        if extent is None:
            # Trivial coordinate generator
            coord_gen = lambda n, _: range(n)
            extent = (None,) * len(grid_shape)  # dummy for the iterator below
            for n, l, dim_name in zip(grid_shape, extent, ("x", "y", "z")):
                new_coords[dim_name] = coord_gen(n, l)

        elif structure is None or structure == "square":
            # Actual cell position coordinate generator
            coord_gen = lambda n, l: np.linspace(0.0, l, n, False) + (
                0.5 * l / n
            )
            for n, l, dim_name in zip(grid_shape, extent, ("x", "y", "z")):
                new_coords[dim_name] = coord_gen(n, l)

        elif structure == "hexagonal":
            if (_ndim := len(grid_shape)) != 2:
                raise ValueError(
                    "Grid structure 'hexagonal' does not support coordinates "
                    f"for {_ndim}-dimensional grids!"
                )
            # FIXME These lack the appropriate offset -- and they make too many
            #       assumptions on the particular form of discretization!
            # TODO  Consider using trivial offset coordinates instead?
            new_coords["x"] = (
                np.linspace(0.0, extent[0], grid_shape[0], False)
                + 0.5 * extent[0] / grid_shape[0]
            )
            new_coords["y"] = (
                np.linspace(0.0, extent[1], grid_shape[1], False)
                + 0.5 * extent[1] / grid_shape[1] / 0.75
            )

        else:
            raise ValueError(f"Unknown grid structure '{structure}'!")

        # NOTE Time coordinates are not changed

        # Store the new dimension names and coordinates for later association
        self._new_dims = new_dims
        self._new_coords = new_coords

    def _reshape_data(self) -> xr.DataArray:
        """Looks at the current data shape and container attributes to
        reshape the data such that it represents a grid.
        """
        data_shape = self._data_shape
        new_shape = self._new_shape
        grid_shape = self._grid_shape
        new_dims = self._new_dims
        new_coords = self._new_coords

        # Determine index order
        index_order = self.attrs.get(self._GDC_index_order_attr, "F")

        # Have to postprocess this if order is stored as array of strings
        if isinstance(index_order, np.ndarray):
            if index_order.ndim == 0:
                index_order = index_order.item()
            else:
                index_order = index_order.flatten()[0]

        # Reshape data now
        log.debug(
            "Reshaping data of shape %s to %s (assuming order '%s') to "
            "match given grid shape %s ...",
            data_shape,
            new_shape,
            index_order,
            grid_shape,
        )

        try:
            data = np.reshape(self._data.values, new_shape, order=index_order)

        except ValueError as err:
            raise ValueError(
                "Reshaping failed! This is probably due to a "
                "mismatch between the written dataset attribute "
                "for the grid shape ('{}': {}, configured by "
                "class variable `_GDC_grid_shape_attr`) and the "
                "actual shape {} of the written data."
                "".format(self._GDC_grid_shape_attr, grid_shape, data_shape)
            ) from err

        # All succeeded. Based on the existing data, create a new DataArray
        new_data = xr.DataArray(
            name=self.name,
            data=data,
            dims=new_dims,
            coords=new_coords,
            attrs={k: copy.copy(v) for k, v in self.attrs.items()},
        )

        # Carry over the time coordinates
        if "time" in self._data.dims:
            new_data.coords["time"] = self._data.coords["time"]

        # Done.
        log.debug("Successfully reshaped data to represent a spatial grid.")
        return new_data
