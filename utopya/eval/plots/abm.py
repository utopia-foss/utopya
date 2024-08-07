"""Implements plot functions for agent-based models, e.g. of agents and their
movement in a domain."""

import copy
import itertools
import logging
from collections import deque
from math import sqrt
from typing import Dict, Optional, Sequence, Tuple, Union

import numpy as np
import xarray as xr
from dantro.base import BaseDataContainer
from dantro.plot import ColorManager
from dantro.tools import recursive_update
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.legend import Legend
from matplotlib.legend_handler import HandlerBase, HandlerPathCollection
from matplotlib.markers import MarkerStyle
from matplotlib.patches import Patch
from matplotlib.path import Path
from matplotlib.transforms import AffineDeltaTransform

from ...tools import ensure_dict, is_iterable
from .. import PlotHelper, is_plot_func
from ._mpl import adjust_figsize_to_aspect

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------

MARKERS: Dict[str, Path] = {
    "wedge": Path(
        [(0.0, -0.1), (0.3, 0.0), (0.0, 0.1), (0.0, 0.0)],
        codes=[Path.MOVETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY],
    ),
    "fish": Path(
        [
            (-5, 0),
            (-2, +0.2),
            (+3, +2),
            (+3, 0),
            #
            (+3, -2),
            (-2, -0.2),
            (-5, 0),
        ],
        codes=[
            Path.MOVETO,
            Path.CURVE4,
            Path.CURVE4,
            Path.CURVE4,
            #
            Path.CURVE4,
            Path.CURVE4,
            Path.CURVE4,
        ],
    ),
    "fish2": Path(
        [
            (-5, 0),
            (-2, +0.2),
            (+3, +2.5),
            (+3, 0),
            #
            (+3, -2.5),
            (-2, -0.2),
            (-5, 0),
            #
            # tail
            (-3, 0),
            (-5.5, -1.5),
            (-5, 0),
            (-5.5, +1.5),
            #
            # fins left & right
            (+2, 0),
            (-2, -1.3),
            (-1, 0),
            (-2, +1.3),
        ],
        codes=[
            Path.MOVETO,
            Path.CURVE4,
            Path.CURVE4,
            Path.CURVE4,
            #
            Path.CURVE4,
            Path.CURVE4,
            Path.CURVE4,
            #
            Path.MOVETO,
            Path.LINETO,
            Path.LINETO,
            Path.LINETO,
            #
            Path.MOVETO,
            Path.LINETO,
            Path.LINETO,
            Path.LINETO,
        ],
    ),
}
"""Custom markers that can be used in :py:class:`.AgentCollection`, an
essential part of :py:func:`.abmplot`.

Available markers:

- ``wedge``: A triangle that can be used to denote orientations.
- ``fish``: A simple fish-like shape.
- ``fish2``: A more elaborate fish-like shape.

.. image:: ../_static/_gen/abmplot/markers.pdf
    :target: ../_static/_gen/abmplot/markers.pdf
    :width: 100%

.. hint::

    To have consistent orientations, note that markers should point along the
    positive x-axis. With increasing orientation values, they are rotated in
    counter-clockwise direction.
    Angles are measured in radians.

.. note::

    Suggestions for additional markers are
    `welcome <https://gitlab.com/utopia-project/utopya/-/issues>`_.
"""
# TODO add ant-like shape
# TODO tweak shapes to consist only of a single path, not two overlapping ones


class AgentCollection(PathCollection):
    """A collection of agent markers and (optionally) their position history
    in the form of a tail.
    Combines :py:class:`~matplotlib.collections.PathCollection` with a
    :py:class:`~matplotlib.collections.LineCollection` for the tails.
    """

    def __init__(
        self,
        xy: Union[np.ndarray, Sequence[Union[Path, Tuple[float, float]]]],
        *,
        marker: Union[Path, Patch, str, dict] = "auto",
        default_marker: Union[Path, Patch, str, dict] = "o",
        default_marker_oriented: Union[Path, Patch, str, dict] = "wedge",
        sizes: Union[float, Sequence[float]] = None,
        size_scale: float = 1.0,
        normalize_marker_sizes: bool = True,
        orientations: Union[float, Sequence[float]] = None,
        base_orientation: float = 0.0,
        tail_length: int = 0,
        tail_kwargs: dict = None,
        tail_decay: float = 0.0,
        tail_max_segment_length: float = None,
        use_separate_paths: bool = True,
        **kwargs,
    ):
        """Set up an AgentCollection, visualizing agents and (optionally) their
        position history using a tail.

        .. hint::

            If you need a higher performance for this plot, consider not using
            the *decaying* tails, for which the line segments need to be drawn
            individually.

        Args:
            xy (Sequence[Tuple[float, float]]): The positions of the agents.
                The number of agents is extracted from the length of this
                sequence or ``(x, y)`` positions or ``(N, 2)`` array.
            marker (Union[matplotlib.path.Path, matplotlib.patches.Patch, str, dict], optional):
                The marker to use to denote agent positions. The following
                input types are possible:

                - A :py:class:`~matplotlib.path.Path` is used as it is
                - A :py:class:`dict` is used as keyword arguments to the
                  :py:class:`~matplotlib.path.Path`, where ``vertices`` can be
                  a sequence of 2-tuples that defines the vertices of the path.
                - A :py:class:`~matplotlib.patches.Patch` already defines a
                  path, which is extracted and used as marker. All other
                  properties are ignored.
                - :py:class:`str` is looked up in :py:data:`.MARKERS`; if no
                  such entry is available, the remaining options are evaluated.
                - All other input is used to construct a
                  :py:class:`~matplotlib.markers.MarkerStyle` from which the
                  path is extracted.

            default_marker (Union[matplotlib.path.Path, matplotlib.patches.Patch, str, dict], optional):
                The marker to use in case that ``marker`` is None and agents
                are *not* initialized with an orientation.
            default_marker_oriented (Union[matplotlib.path.Path, matplotlib.patches.Patch, str, dict], optional):
                The marker to use in case that ``marker`` is None and agents
                *are* initialized with an orientation.
            sizes (Union[float, Sequence[float]], optional): Agent sizes in
                units of area (of bounding box) squared.
                If a scalar value is given, all agents will have the same size.
            size_scale (float, optional): A scaling factor for the sizes.
            normalize_marker_sizes (bool, optional): If True, will normalize
                the size of the given ``marker``. This is done by computing
                the area of the bounding box and scaling the path such that the
                bounding box has an area of one.
            orientations (Union[float, Sequence[float]], optional): Single or
                individual orientations of the agents. Zero corresponds to
                pointing along the positive x-axis, with increasing orientation
                values leading to a counter-clockwise rotation. Angles need to
                be given in radians.
            base_orientation (float, optional): Rotates the given marker by
                this value such that all ``orientations`` have a constant
                offset.
            tail_length (int, optional): For non-zero integers, will draw a
                tail behind the agents that traces their position history.
                This is only relevant if the collection is used as part of an
                animation where the position history can be aggregated upon
                each call to :py:meth:`.set_offsets`.
            tail_kwargs (dict, optional): Keyword arguments that are passed to
                the :py:class:`~matplotlib.collections.LineCollection` which is
                used to represent the tails.
            tail_decay (float, optional): A decay factor. If non-zero, will
                multiply each consecutive tail segments ``alpha`` value with
                ``(1 - tail_decay)``.
            tail_max_segment_length (float, optional): If set, will *not* draw
                tail segments that are longer than this value in either the
                x- or the y-direction. This can be useful if agents move in a
                periodic space where positions may jump.
            use_separate_paths (bool, optional): If False, only a single path
                is used to represent all agents in the underlying
                :py:class:`~matplotlib.collections.PathCollection`.

                .. warning::
                    Setting this to False should *only* be done if all agents
                    can be thought of as identical, i.e. have the same size,
                    color, marker, and orientation — otherwise this leads to
                    subtle and seemingly random breakage in the form of
                    markers not being drawn.
            **kwargs: Passed on to
                :py:class:`~matplotlib.collections.PathCollection`
        """
        xy = np.array(xy)
        if xy.ndim != 2 or xy.shape[1] != 2:
            raise ValueError(
                "Agent positions need to be of shape `(N, 2)` but were "
                f"{xy.shape}! Given data was:\n{str(xy)}"
            )

        # Attributes
        self._normalize_marker_sizes = normalize_marker_sizes
        self._size_scale = size_scale
        self._size_factors = None

        self._has_orientation = orientations is not None
        self._R = np.empty((2, 2))  # re-usable rotation matrix
        self._base_vertices = None
        self._base_orientation = base_orientation
        self._orientations = None

        self._tail_length = tail_length
        self._tails = None
        self._tail_kwargs = ensure_dict(tail_kwargs)
        self._tail_decay = tail_decay
        self._tail_max_segment_length = tail_max_segment_length
        self._offsets_history = None

        # Decide whether they need to be oriented, in which case we need many
        # separate Path objects. Otherwise, a single Path suffices.
        if marker == "auto":
            marker = (
                default_marker_oriented
                if self.has_orientation
                else default_marker
            )
        self._markerpath = self._prepare_marker_path(marker)
        self._has_markers = bool(marker)

        if use_separate_paths or self.has_orientation:
            paths = [copy.deepcopy(self.markerpath) for _ in range(len(xy))]

        else:
            # A bit simpler, only need a single marker
            # FIXME This causes issues in some scenarios, e.g. by mapping
            #       the color only to the first path or not drawing
            #       markers at all!
            #       Perhaps always use separate markerpaths?!
            paths = [self.markerpath]

        # Compute size factors to have reasonably sized markers (and not
        # markers in data units, which typically does not make a lot of sense)
        self._size_factors = self._compute_size_factors(paths)

        # Now setup the underlying PathCollection
        super().__init__(paths, offsets=xy, sizes=self._size_factors, **kwargs)

        # Optionally, set sizes
        if sizes is not None:
            self.set_markersizes(sizes)

        # Optionally, set orientations
        if self.has_orientation:
            # Store copies of the base vertices which will be used for
            # rotating the markers. These base vertices are used for the
            # rotation in order to not accumulate rounding errors etc.
            self._base_vertices = [p.vertices.copy() for p in self.get_paths()]

            # Base vertices should not be writeable, but the patches' vertices
            # need to be writeable. Take care of that here, reduces repetitions
            for _bv in self._base_vertices:
                _bv.setflags(write=False)  # for safety

            # Can apply orientations now
            self.set_orientations(orientations)

        # Optionally, prepare for drawing tails
        if self.tail_length:
            self._offsets_history = deque([], self.tail_length + 1)
            self._add_to_offsets_history(self.get_offsets())

            if not self._tail_decay:
                self._segments = np.empty((len(self), self.tail_length + 1, 2))
            else:
                self._segments = np.empty((len(self) * self.tail_length, 2, 2))
            self._segments.fill(np.nan)

            self.draw_tails()

    def __len__(self) -> int:
        """Number of agents associated with this AgentCollection"""
        return len(self.get_offsets())

    @property
    def has_orientation(self) -> bool:
        """Whether agent orientation is represented"""
        return self._has_orientation

    @property
    def has_markers(self) -> bool:
        """Whether a marker will be shown; if disabled, can skip setting array
        data and thus increase performance somewhat ..."""
        return self._has_markers

    @property
    def tail_length(self) -> int:
        """Length of the tail of each agent, i.e. the number of *historic*
        offset positions that are connected into a line."""
        return self._tail_length

    @property
    def tails(self) -> Optional[LineCollection]:
        """The :py:class:`~matplotlib.collections.LineCollection` that
        represents the tails of the agents — or None if tails are not
        activated.

        .. note::

            This collection still needs to be registered *once* with the axes
            via :py:meth:`~matplotlib.axes.Axes.add_collection`.
        """
        return self._tails

    @property
    def markerpath(self) -> Optional[Path]:
        """Returns the used markerpath"""
        return self._markerpath

    def draw_tails(self, **kwargs) -> LineCollection:
        """Draws the tails *from scratch*, removing the currently added
        collection if there is one.

        .. note::

            If calling this, the collection representing the tails needs to be
            re-added to the desired axes. To update tail positions according
            to the offsets history, use :py:meth:`.update_tails`.
        """
        if not self.tail_length:
            raise ValueError(
                "Cannot add tails to AgentCollection after initialization!"
            )

        if kwargs:
            kwargs = recursive_update(copy.deepcopy(self._tail_kwargs), kwargs)
        else:
            kwargs = self._tail_kwargs

        if self._tails is not None:
            try:
                self._tails.remove()
            except:
                pass

        self._tails = LineCollection(self._build_line_segments(), **kwargs)

        if self._tail_decay != 0:
            alpha = self.tails.get_alpha()
            if not isinstance(alpha, float):
                alpha = 1.0
            decaying_alpha = itertools.accumulate(
                [alpha] * self.tail_length,
                lambda a, _: a * (1.0 - self._tail_decay),
            )
            self.tails.set_alpha(list(decaying_alpha) * len(self))

        return self.tails

    def update_tails(self) -> LineCollection:
        """Updates the collection that holds the tails using the offsets
        history.
        """
        if not self.tail_length:
            raise ValueError(
                "Cannot add tails to AgentCollection after initialization!"
            )
        self.tails.set_segments(self._build_line_segments())
        return self.tails

    def set(self, *args, **kwargs):
        """Sets AgentCollection artist properties"""
        return super().set(*args, **kwargs)

    def set_markersizes(self, sizes):
        """Sets the marker sizes, taking into account the size scaling.

        .. note::

            This behaves differently from the inherited ``set_sizes`` method
            and thus has a different name. The difference is that
            :py:meth:`~matplotlib.collections.PathCollection.set_sizes` is also
            called during saving of a plot and would thus lead to repeated
            application of the size scaling, which is not desired.
        """
        if not is_iterable(sizes):
            sizes = np.array([sizes] * len(self))

        super().set_sizes(self._size_factors * sizes)

    def set_offsets(self, offsets) -> None:
        """Sets the offsets, i.e. path positions of all agents.

        Invokes :py:meth:`~matplotlib.collections.PathCollection.set_offsets`
        and afterwards stores the offset history, using it for
        :py:meth:`.update_tails`.
        """
        super().set_offsets(offsets)

        if self.tail_length:
            self._add_to_offsets_history(offsets)
            self.update_tails()

    def set_orientations(
        self, orientations: Union[float, Sequence[float]]
    ) -> None:
        """Set the orientations of all agents. If a scalar is given, will set
        all orientations to that value. If any kind of sequence is given, will
        associate individual orientations with agents.

        .. note::

            This can only be used if the collection was *initialized* with
            ``orientations``, see :py:meth:`.__init__`.
        """
        if not self.has_orientation:
            raise ValueError(
                "AgentCollection was not initialized with orientations; "
                "cannot change them after initialization!"
            )

        if not is_iterable(orientations):
            orientations = [orientations] * len(self._base_vertices)

        paths = self.get_paths()

        if not (len(paths) == len(orientations) == len(self._base_vertices)):
            raise ValueError(
                f"There was a length mismatch between the number of paths in "
                f"this collection ({len(paths)}), the given values for the "
                f"new orientations ({len(orientations)}), and the number of "
                f"stored base vertices ({len(self._base_vertices)})!"
            )

        for path, _o, _bv in zip(paths, orientations, self._base_vertices):
            self._rotate_path(path, orientation=_o, base_vertices=_bv)

        self._orientations = orientations

    def get_orientations(self) -> Sequence[float]:
        """Returns the current orientations of all agents.

        .. note::

            Changing the returned object does not rotate the agents!
            Use :py:meth:`.set_orientations` to achieve that.
        """
        if not self.has_orientation:
            raise ValueError(
                "AgentCollection was not initialized with orientations!"
            )
        return self._orientations

    # .........................................................................

    def _prepare_marker_path(
        self, marker: Union[Path, Patch, str, list, dict]
    ) -> Path:
        """Generates the :py:class:`~matplotlib.path.Path` needed for the
        agent marker using a variety of setup methods, depending on argument
        type:

        - :py:class:`~matplotlib.path.Path` is used as it is
        - :py:class:`dict` is used to call :py:class:`~matplotlib.path.Path`
        - :py:class:`~matplotlib.patches.Patch` already defines a path, which
          is extracted and used.
        - :py:class:`str` is looked up in :py:data:`.MARKERS`; if no such entry
          is available, the remaining options are evaluated.
        - Other types construct a :py:class:`~matplotlib.markers.MarkerStyle`
          from which the path is extracted.

        After constructing the path, applies the base orientation by rotating
        it by that value.
        """
        if isinstance(marker, Path):
            path = marker

        elif isinstance(marker, dict):
            path = Path(**marker)

        elif isinstance(marker, Patch):
            path = copy.deepcopy(marker.get_path())

        elif isinstance(marker, str) and marker in MARKERS:
            path = copy.deepcopy(MARKERS[marker])

        else:
            path = MarkerStyle(marker).get_path()

        path.vertices.setflags(write=True)
        self._rotate_path(
            path,
            base_vertices=path.vertices.copy(),
            orientation=self._base_orientation,
        )
        return path

    def _compute_size_factors(self, paths: Sequence[Path]) -> np.ndarray:
        """Given a sequence of Paths, computes the corresponding size factors
        which are used in :py:meth:`.set_markersizes` to scale the individual
        marker sizes. The resulting sizes are multiplied with the given
        size scale.

        If marker size normalization is activated, size factors may vary
        between the markers.
        """

        def bbox_area(p) -> float:
            bbox = p.get_extents()
            return bbox.height * bbox.width

        if not self._normalize_marker_sizes:
            return self._size_scale * np.ones((len(paths),))

        return self._size_scale * np.array([1 / bbox_area(p) for p in paths])

    def _add_to_offsets_history(self, new_offsets: np.ndarray) -> None:
        """Adds the given offset to the left side of the deque, pushing old
        entries off the right side of the deque.

        If the tail segment length is limited, will mask the offset positions
        for individual agents if they differ by more than that value from
        their previous position.
        *Note* that in this case the history is no longer strictly correct; it
        is already evaluated for use in :py:meth:`.draw_tails` in order to
        increase performance and avoid evaluating this over and over again.
        """
        max_delta = self._tail_max_segment_length
        if max_delta is not None and len(self._offsets_history) >= 1:
            # Need to mask offset jumps larger than the maximum delta.
            # This will lead to tail segments not being drawn.
            new_offsets = new_offsets.copy()
            abs_delta = np.abs(self._offsets_history[0] - new_offsets)
            new_offsets[abs_delta > max_delta] = np.nan

        self._offsets_history.appendleft(new_offsets)

    def _build_line_segments(self) -> np.ndarray:
        """Creates the line segments for the tails using the offsets history"""
        TL = self._tail_length
        if not self._tail_decay:
            # Can simply use the offsets history (with changed slicing)
            for i, _offsets in enumerate(self._offsets_history):
                self._segments[:, TL - i, :] = _offsets

        else:
            # Have a more complicated segments structure:
            #   axis 0: [0, TL)    segments of first agent's tail,
            #           [TL, 2TL)  segments of second agent's tail,
            #           etc., with lower indices being for more recent history.
            #   axis 1: start and end point
            #   axis 2: x and y coordinates (of start and end point)
            hist = list(self._offsets_history)
            for i, (_p0, _p1) in enumerate(zip(hist[:-1], hist[1:])):
                # _p0 and _p1: offsets of *all* agents at adjacent times
                self._segments[i::TL, 0, :] = _p0
                self._segments[i::TL, 1, :] = _p1

        return self._segments

    def _rotate_path(
        self, path: Path, *, base_vertices: np.ndarray, orientation: float
    ) -> None:
        """Sets the given path's vertices by rotating (a copy of) the base
        vertices by the given ``orientation`` (in radians)."""
        _cos, _sin = np.cos(orientation), np.sin(orientation)
        self._R[0, 0] = _cos
        self._R[1, 0] = _sin
        self._R[0, 1] = -_sin
        self._R[1, 1] = _cos
        path._vertices[...] = np.dot(base_vertices, self._R.T)
        path._orientation = orientation


class HandlerAgentCollection(HandlerPathCollection):
    """Legend handler for :py:class:`.AgentCollection` instances."""

    def create_collection(
        self, orig_handle, sizes, offsets, offset_transform
    ) -> AgentCollection:
        """Returns an AgentCollection from which legend artists are created."""
        ac = AgentCollection(
            offsets,
            marker=orig_handle.markerpath,
            sizes=sizes,  # FIXME too small?
            offset_transform=offset_transform,
        )
        # TODO What about the colormap etc?
        return ac

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
        """Creates the artists themselves.

        For original docstring see
        :py:meth:`matplotlib.legend_handler.HandlerBase.create_artists`."""
        xdata, xdata_marker = self.get_xdata(
            legend, xdescent, ydescent, width, height, fontsize
        )

        ydata = self.get_ydata(
            legend, xdescent, ydescent, width, height, fontsize
        )

        sizes = self.get_sizes(
            legend, orig_handle, xdescent, ydescent, width, height, fontsize
        )

        p = self.create_collection(
            orig_handle,
            sizes,
            offsets=list(zip(xdata_marker, ydata)),
            offset_transform=trans,
        )

        self.update_prop(p, orig_handle, legend)
        p.set_offset_transform(trans)
        return [p]


Legend.update_default_handler_map({AgentCollection: HandlerAgentCollection()})


# -----------------------------------------------------------------------------


def _get_data(d: Union[xr.DataArray, xr.Dataset], var: str) -> xr.DataArray:
    """Retrieve data by key, e.g. for hue, size, ..."""
    try:
        return d[var]

    except Exception as exc:
        if isinstance(d, xr.DataArray):
            if d.name == var:
                return d
            raise ValueError(
                "If using xr.DataArray for agent data, make sure to have the "
                f"array's `name` attribute set (in this case to: '{var}')!\n"
                f"Got:  {str(d)}"
            ) from exc

        raise ValueError(
            f"Failed retrieving agent data variable '{var}' from:\n{d}\n"
            f"Got a {type(exc).__name__}: {exc}\n"
            f"Make sure that the data variable '{var}' exists "
            f"or pass an xr.DataArray with name '{var}' instead."
        ) from exc


def _parse_vmin_vmax(
    specs: dict,
    d: Union[xr.DataArray, xr.Dataset],
    *,
    vmin_key: str = "vmin",
    vmax_key: str = "vmax",
) -> dict:
    """Adapts ``specs`` dict entries ``vmin_key`` and ``vmax_key``, replacing
    their *values* with the minimum or maximum value of given data ``d``."""
    if specs.get(vmin_key) == "min":
        specs[vmin_key] = d.min().item()
    if specs.get(vmax_key) == "max":
        specs[vmax_key] = d.max().item()

    return specs


def _set_domain(
    *,
    ax: "matplotlib.axes.Axes",
    layers: dict,
    mode: str = "auto",
    extent: Tuple[float, float, float, float] = None,
    height: float = None,
    aspect: Union[float, int, str] = "auto",
    update_only: bool = False,
    pad: float = 0.05,
) -> Optional[Tuple[float, float]]:
    """Sets the axis limits and computes the area of the domain

    Args:
        ax (matplotlib.axes.Axes): The axes to adjust
        layers (dict): Layer information prepared by :py:func:`.abmplot`
        mode (str, optional): Domain mode, can be ``auto``, ``manual``,
            ``fixed`` and ``follow``. In fixed mode, all available data in
            ``layers`` is inspected to derive domain bounds.
            In ``follow`` mode, the currently used collection positions are
            used to determine the boundaries.
            In ``auto`` mode, will use a ``fixed`` domain if *no* ``extent``
            was given, otherwise ``manual`` mode is used.
        extent (Tuple[float, float, float, float], optional): A manually set
            extent in form ``(left, right, bottom, top)``. Alternatively,
            a 2-tuple will be interpreted as ``(0, right, 0, top)``.
        height (float, optional): The height of the domain in data units
        aspect (Union[float, int, str], optional): The aspect ratio of the
            domain, the width being computed via ``height * aspect``.
            If ``auto``, will
        update_only (bool, optional): If true, will only make changes to the
            domain bounds if necessary, e.g. in ``follow`` mode.
        pad (float, optional): Relative padding added to each side.

    Returns:
        Optional[Tuple[float, float]]:
            The domain area (in data units squared) and the aspect ratio, i.e.
            ``width/height``. The return value will be None if ``update_only``
            was set.
    """
    # Determine mode
    if mode == "auto":
        mode = "fixed" if extent is None else "manual"

    # May already have a new extent specified
    if extent is not None:
        try:
            _l, _r, _b, _t = extent

        except:
            try:
                _l, _b = 0, 0
                _r, _t = extent
            except:
                raise

    else:
        # Get the "previous" values, just to have something set
        _l, _r = ax.get_xlim()
        _b, _t = ax.get_ylim()

    # Depending on mode, the values may further change
    if mode is None or mode == "manual":
        if update_only:
            return

    elif isinstance(mode, str):
        # Decide which data source to use
        colls = [lyr["coll"] for lyr in layers.values()]
        have_colls = all([c is not None for c in colls])

        if mode == "fixed" and update_only:
            # No need to update
            return

        if mode == "fixed" or (mode == "follow" and not have_colls):
            # Get all the data
            # NOTE Will need adaption if plotting on multiple axes
            xdata = [lyr["data"][lyr["x"]] for lyr in layers.values()]
            ydata = [lyr["data"][lyr["y"]] for lyr in layers.values()]

        elif mode == "follow":
            # Get the existing offset data from the collection
            xdata = [coll.get_offsets()[:, 0] for coll in colls]
            ydata = [coll.get_offsets()[:, 1] for coll in colls]

        else:
            raise ValueError(
                f"Got invalid `mode` argument with value '{mode}'! "
                "Possible modes:  fixed, follow, manual, auto"
            )

        # Determine bounds
        _l = min([x.min().item() for x in xdata])
        _r = max([x.max().item() for x in xdata])
        _b = min([y.min().item() for y in ydata])
        _t = max([y.max().item() for y in ydata])

    else:
        raise TypeError(
            f"Got invalid `mode` argument of type {type(mode)}, expected str!"
        )

    # Ensure the domain has a fixed aspect ratio
    if aspect == "auto":
        if mode == "follow":
            aspect = 1.0
        else:
            aspect = abs(_r - _l) / abs(_t - _b)

    if aspect is not None:
        current_width = abs(_r - _l)
        current_height = abs(_t - _b)

        if height:
            target_width = height * aspect
            target_height = height
        else:
            target_width = max(current_width, current_height * aspect)
            target_height = max(current_height, current_width / aspect)

        if current_width < target_width:
            d = target_width - current_width
            _l -= d / 2
            _r += d / 2

        if current_height < target_height:
            d = target_height - current_height
            _b -= d / 2
            _t += d / 2

    # Apply padding
    if pad is not None:
        _w = abs(_r - _l)
        _h = abs(_t - _b)
        _l -= _w * pad
        _r += _w * pad
        _b -= _h * pad
        _t += _h * pad

    # Finally, compute domain area and actually set the limits
    domain_area = abs(_r - _l) * abs(_t - _b)
    actual_aspect = abs(_r - _l) / abs(_t - _b)
    ax.set_xlim(_l, _r)
    ax.set_ylim(_b, _t)

    return domain_area, actual_aspect


# -----------------------------------------------------------------------------


def draw_agents(
    d: Union[xr.Dataset, xr.DataArray],
    *,
    x: str,
    y: str,
    ax: "matplotlib.axes.Axes" = None,
    _collection: Optional[AgentCollection] = None,
    _domain_area: float = 1,
    marker: Union[Path, Patch, str, list, dict] = "auto",
    hue: str = None,
    orientation: Union[str, float, Sequence[float]] = None,
    size: Union[str, float, Sequence[float]] = None,
    size_norm: Union[str, dict, "matplotlib.colors.Normalize"] = None,
    size_vmin: float = None,
    size_vmax: float = None,
    size_scale: float = 0.0005,
    label: str = None,
    cmap: Union[str, dict] = None,
    norm: Union[str, dict] = None,
    vmin: Union[float, str] = None,
    vmax: Union[float, str] = None,
    cbar_label: str = None,
    cbar_labels: dict = None,
    add_colorbar: bool = None,
    cbar_kwargs: dict = None,
    **coll_kwargs,
) -> AgentCollection:
    """Draws agent positions onto the given axis.

    Data can be a :py:class:`~xarray.DataArray` or :py:class:`~xarray.Dataset`
    with ``x``, ``y`` and the other encodings ``hue``, ``orientation`` and
    ``size`` being strings that denote

    Args:
        d (Union[xarray.Dataset, xarray.DataArray]): The agent data.
            The recommended format is that of datasets, because it can hold
            more data variables.
            If using data *arrays*, multiple coordinates can be used to set the
            data. Also, the ``name`` attribute needs to be set (to avoid
            accidentally using the wrong data).
        x (str): Name of the data dimension or variable that holds x positions.
        y (str): Name of the data dimension or variable that holds y positions.
        ax (matplotlib.axes.Axes, optional): The axis to plot to; will use the
            current axis if not given.
        _collection (Optional[AgentCollection], optional): If a collection
            exists, will update this collection instead of creating a new one.
        _domain_area (float, optional): The domain area, used to normalize the
            marker sizes for a consistent visual appearance. This is only
            needed when initializing the collection and will set its
            ``size_scale`` parameter to ``size_scale * _domain_area``.
        marker (Union[matplotlib.path.Path, matplotlib.patches.Patch, str, list, dict], optional):
            Which marker to use for the agents. See
            :py:class:`.AgentCollection` for available arguments.
        hue (str, optional): The name of the data dimension or variable that
            holds the values from which marker colors are determined.
        orientation (Union[str, float, Sequence[float]], optional): The name of
            the data variable or dimension that holds the orientation data (in
            radians). If scalar or sequence, will pass those explicit values
            through.
        size (Union[str, float, Sequence[float]], optional): The name of the
            data variable or dimension that holds the values from which the
            marker size is determined.
        size_norm (Union[str, dict, matplotlib.colors.Normalize], optional):
            A normalization for the sizes.
            The :py:class:`~dantro.plot.utils.color_mngr.ColorManager` is used
            to set up this normalization, thus offering all the corresponding
            capabilities.
            Actual sizes are computed by `xarray.plot.utils._parse_size``.
        size_vmin (float, optional): The value that is mapped to the smallest
            size of the markers.
        size_vmax (float, optional): The value that is mapped to the largest
            size of the markers.
        size_scale (float, optional): A scaling factor that is applied to the
            size of all markers; use this to control overall size.
        label (str, optional): How to label the collection that is created.
            Will be used as default colorbar label and for the legend.
        cmap (Union[str, dict], optional): The colormap to use for the markers.
            Supports :py:class:`~dantro.plot.utils.color_mngr.ColorManager`.
        norm (Union[str, dict], optional): Norm to use for the marker colors.
            Supports :py:class:`~dantro.plot.utils.color_mngr.ColorManager`.
        vmin (Union[float, str], optional): The value of the ``hue`` dimension
            that is mapped to the beginning of the colormap.
        vmax (Union[float, str], optional): The value of the ``hue`` dimension
            that is mapped to the end of the colormap.
        cbar_labels (dict, optional): Colorbar labels, parsed by the
            :py:class:`~dantro.plot.utils.color_mngr.ColorManager`.
        add_colorbar (bool, optional): Whether to add a colorbar or not. Only
            used upon creating the collection.
        cbar_kwargs (dict, optional): Passed on to
            :py:meth:`~dantro.plot.utils.color_mngr.ColorManager.create_cbar`
        **coll_kwargs: Passed on to :py:class:`.AgentCollection`; see there
            for further available arguments.
    """
    import matplotlib.pyplot as plt

    def parse_sizes(d: np.ndarray, size_norm) -> np.ndarray:
        from xarray.plot.utils import _MARKERSIZE_RANGE, _parse_size

        # Use ColorManager to evaluate the size_norm argument
        size_norm = ColorManager(
            norm=size_norm, vmin=size_vmin, vmax=size_vmax
        ).norm

        # Compute and apply the size mapping.
        # Need a correction factor to let mapped sizes appear approximately
        # equally large as unmapped ones. With _parse_sizes returning values
        # within _MARKERSIZE_RANGE (typically [18, 72]), the correction is
        # simply to divide by a value of *approximately* that magnitude.
        size_mapping = _parse_size(d, size_norm)
        corr_factor = 1 / np.array(_MARKERSIZE_RANGE).mean()
        return corr_factor * size_mapping.loc[d.values.ravel()].values

    def get_orientations(d: Union[xr.DataArray, xr.Dataset]):
        """If ``orientation`` is a string, looks up the orientation data,
        otherwise simply passes the value through, letting the AgentManager
        handle the argument."""
        if isinstance(orientation, str):
            return _get_data(d, orientation)
        return orientation

    def get_xy(d: Union[xr.DataArray, xr.Dataset]) -> np.ndarray:
        """Retrieve and aggregate x and y position data"""
        xpos = _get_data(d, x)
        ypos = _get_data(d, y)
        stacked = np.stack([xpos, ypos], -1)
        return stacked
        # equivalent to np.dstack([xpos, ypos])[0], but that one is slower

    # .........................................................................

    if isinstance(d, BaseDataContainer):
        d = d.data

    if not isinstance(d, (xr.Dataset, xr.DataArray)):
        raise TypeError(f"Expected xr.Dataset or xr.DataArray, got {type(d)}!")

    if ax is None:
        ax = plt.gca()

    # Depending on the collection existing or not, update it or create it.
    coll = _collection
    if coll is not None:
        # Only need to update the existing collection's offsets, orientations,
        # array data, sizes ...
        coll.set_offsets(get_xy(d))

        if orientation:
            coll.set_orientations(get_orientations(d))

        if hue and coll.has_markers:
            coll.set_array(_get_data(d, hue))
            if vmin is None or vmax is None:
                coll.autoscale()
                coll.set_clim(vmin, vmax)

        if size and isinstance(size, str):
            # TODO Make this more efficient?
            coll.set_markersizes(parse_sizes(_get_data(d, size), size_norm))

        return coll

    # else: Still need to create everything ...................................
    cm = ColorManager(
        cmap=cmap, norm=norm, vmin=vmin, vmax=vmax, labels=cbar_labels
    )

    # Prepare size data ...
    if size:
        if "sizes" in coll_kwargs:
            raise ValueError(
                "Cannot pass both `sizes` and `size` arguments! "
                "Use `size` to pass marker sizes via a data dimension, a "
                "sequence of sizes, or a scalar size (same for all agents)."
            )

        if isinstance(size, str):
            coll_kwargs["sizes"] = parse_sizes(_get_data(d, size), size_norm)

        else:
            # Let the collection take care of this
            coll_kwargs["sizes"] = size

    # Create collection
    # Need to pass orientations here already, because it determines whether
    # this will be a heterogeneous AgentCollection (with individual paths) or
    # a homogeneous one (with a single path, copied for each agent).
    coll = AgentCollection(
        get_xy(d),
        offset_transform=AffineDeltaTransform(ax.transData),
        orientations=get_orientations(d) if orientation else None,
        label=label,
        cmap=cm.cmap,
        norm=cm.norm,
        size_scale=(size_scale * _domain_area),
        marker=marker,
        **coll_kwargs,
    )
    if hue and coll.has_markers:
        coll.set_array(_get_data(d, hue))
        coll.autoscale()
        coll.set_clim(vmin, vmax)

    # Add collections to the current axis and ensure equal aspect ratio
    ax.set_aspect("equal")
    ax.add_collection(coll)
    if coll.tails is not None:
        ax.add_collection(coll.tails)

    # Create the colorbar
    cbar = None
    if add_colorbar or (add_colorbar is None and (hue and marker)):
        cbar = cm.create_cbar(
            coll,
            fig=ax.get_figure(),
            ax=ax,
            label=cbar_label,
            **ensure_dict(cbar_kwargs),
        )
        # NOTE matplotlib already adds it as `coll.colorbar` attribute

    return coll


# -----------------------------------------------------------------------------


@is_plot_func(use_dag=True, supports_animation=True)
def abmplot(
    *,
    data: Dict[str, Union[xr.Dataset, xr.DataArray]],
    hlpr: PlotHelper,
    to_plot: Dict[str, dict],
    frames: str = None,
    frames_isel: Union[int, slice] = None,
    domain: Union[str, dict, Tuple[float, float, float, float]] = "fixed",
    adjust_figsize_to_domain: bool = True,
    figsize_aspect_offset: float = 0.2,
    suptitle_fstr: str = "{dim:} = {val:5d}",
    suptitle_kwargs: dict = dict(fontfamily="monospace"),
    add_legend: bool = None,
    **shared_kwargs,
):
    """Plots agents in a domain, animated over time.

    Features:

    - Plot multiple "layers" of agents onto the same axis.
    - Encode ``hue``, ``size`` and ``orientation`` of all agents.
    - Keep track of position history through an animation and draw the history
      as (constant or decaying) tails.
    - Automatically determine the domain bounds, allowing to dynamically follow
      the agents through the domain.
    - Generate marker paths ad-hoc or use pre-defined markers that are relevant
      in the context of visualizing agent-based models, e.g. ``fish``.

    Example output:

    .. raw:: html

        <video width="720" src="../_static/_gen/abmplot/fish.mp4" controls></video>

    .. admonition:: Corresponding plot configuration
        :class: dropdown

        The following configuration was used to generate the above example
        animation.

        .. literalinclude:: ../../tests/cfg/plots/abm_plots.yml
            :language: yaml
            :start-after: ### START -- doc_fish
            :end-before: ### END ---- doc_fish

        The used dummy data (``circle_walk…``) is an
        :py:class:`xarray.Dataset` with data variables ``x``, ``y``,
        ``orientation``, each one spanning dimensions ``time`` and ``agents``.
        Data variables do not have coordinates in this case, but it would be
        possible to supply some.

    .. admonition:: Development roadmap

        The following extensions of this plot function are *planned*:

        - Subplot support, allowing to manually distribute `to_plot` entries
          onto individual subplots.
        - Faceting support, allowing to automatically distribute *all* data
          layers onto rows and columns and thus performing a dimensionality
          reduction on them.

    .. admonition:: See also

        - :py:func:`draw_agents`
        - :ref:`plot_funcs_abm`

    Args:
        data (Dict[str, Union[xarray.Dataset, xarray.DataArray]]): A dict
            holding the data that is to be plotted.
        hlpr (PlotHelper): The plot helper instance.
        to_plot (Dict[str, dict]): Individual plot specifications. Each entry
            refers to one "layer" of agents being plotted and its key needs to
            match the corresponding entry in ``data``.
            See :py:func:`.draw_agents` for available arguments.
            Note that the ``shared_kwargs`` also end up in the entries here.
        frames (str, optional): Which data dimension to use for the animation.
        frames_isel (Union[int, slice], optional): An index-selector that is
            applied on the ``frames`` dimension (*without* dropping empty
            dimensions resulting from this operation). Scalar values will be
            wrapped into a list of size one.
        domain (Union[str, dict, Tuple[float, float, float, float]], optional):
            Specification of the domain on which the agents are plotted.
            If a 4-tuple is given, it defines the position of the *fixed*
            ``(left, right, bottom, top)`` borders of the domain; a 2-tuple
            will be interpreted as ``(0, right, 0, top)``.
            If a string is given, it determines the *mode* by which the domain
            is determined. It can be ``fixed`` (determine bounds from all
            agent positions, then keep them constant) or ``follow`` (domain
            dynamically follows agents, keeping them centered).
            If a dict is given, it is passed to :py:func:`._set_domain`,
            and offers more options like ``pad`` or ``aspect``.
        adjust_figsize_to_domain (bool, optional): If True, will adjust the
            figure size to bring it closer to the aspect ratio of the domain,
            thus reducing whitespace.
        figsize_aspect_offset (float, optional): A constant offset that is
            added to the aspect ratio of the domain to arrive at the target
            aspect ratio of the figure used for ``adjust_figsize_to_domain``.
        suptitle_fstr (str, optional): The format string to use for the
            figure's super-title. If empty or None, no suptitle is added.
            The format string can include the following keys:
            ``dim`` (frames dimension name), ``val`` (current coordinate value,
            will be an index if no coordinates are available),
            ``coords`` (a dict containing all layers' iterator states),
            and ``frame_no`` (enumerates the frame number).
        suptitle_kwargs (dict, optional): Passed to
            :py:meth:`~matplotlib.figure.Figure.suptitle`.
        add_legend (bool, optional): Whether to add a legend.
            ⚠️ This is currently *experimental* and does not work as expected.
        **shared_kwargs: Shared keyword arguments for all plot specifications.
            Whatever is specified here is used as a basis for each individual
            layer in ``to_plot``, i.e. *updated* by the entries in ``to_plot``.
            See :py:func:`.draw_agents` for available arguments.
    """

    def prepare_layer_specs(
        name: str, *, shared_kwargs: dict, **plot_kwargs
    ) -> dict:
        """Parses arguments for each layer into a dict"""
        lyr = dict(
            name=name,
            data=None,
            plot_kwargs=None,
            ax=None,
            coll=None,
            frames=None,
            frames_iter=None,
            num_frames=None,
        )

        # Prepare plot kwargs
        plot_kwargs = recursive_update(
            copy.deepcopy(shared_kwargs), copy.deepcopy(plot_kwargs)
        )
        plot_kwargs["label"] = plot_kwargs.get("label", name)

        # Store it, exposing some parameters on the upper level
        lyr["plot_kwargs"] = plot_kwargs
        lyr["x"] = plot_kwargs["x"]
        lyr["y"] = plot_kwargs["y"]

        # Prepare data
        try:
            d = data[name]

        except KeyError as err:
            _avail = ", ".join(data.keys())
            raise ValueError(
                f"Missing data named '{name}'! Available:  {_avail}\n"
                "Check that the name is correctly defined. If you are using "
                "the DAG framework for data selection, make sure the tag is "
                "computed by including it into `compute_only` or setting the "
                "`force_compute` flag for the tagged node."
            ) from err

        # Extract parameters that are not meant to be passed on to the plot
        frames = plot_kwargs.pop("frames", None)
        frames_isel = plot_kwargs.pop("frames_isel", None)

        # Prepare the frames iterator
        if frames_isel is not None:
            if isinstance(frames_isel, int):
                selector = {frames: [frames_isel]}
            else:
                selector = {frames: frames_isel}
            try:
                d = d.isel(selector, drop=False)

            except Exception as exc:
                raise ValueError(
                    f"Failed applying index-selection for layer '{name}'! "
                    "Did you intend to apply a selection to this layer's "
                    "data? If not, set `frames_isel` to None.\n"
                    f"  frames:       {frames}\n"
                    f"  frames_isel:  {frames_isel}\n"
                    f"  → selector:   {selector}\n"
                    f"  data:\n{d}"
                ) from exc

        frames_iter = None
        if frames is not None:
            frames_iter = d.groupby(frames, squeeze=False)

        # ... and store it all to the layer specs
        lyr["frames"] = frames
        lyr["frames_iter"] = frames_iter
        lyr["num_frames"] = len(frames_iter) if frames_iter else 0
        lyr["data"] = d

        # (Mutably) evaluate vmin & vmax on hue and size dimensions
        if plot_kwargs.get("hue"):
            _parse_vmin_vmax(plot_kwargs, _get_data(d, plot_kwargs["hue"]))

        if plot_kwargs.get("size"):
            _parse_vmin_vmax(
                plot_kwargs,
                _get_data(d, plot_kwargs["size"]),
                vmin_key="size_vmin",
                vmax_key="size_vmax",
            )

        return lyr

    def set_suptitle(
        fstr: str, *, shared_dim: str, frame_coords: dict, **fstr_kwargs
    ) -> Tuple[str, float]:
        """Sets the suptitle, filling it with information about the currently
        plotted frame, e.g. its coordinate."""

        # Need to extract a shared coordinate value
        shared_coord = None
        coords = [v for v in frame_coords.values() if v is not None]
        if coords and all([c == coords[0] for c in coords]):
            shared_coord = coords[0]

        # TODO intelligently set fstr?

        if fstr and shared_dim:
            fstr_kwargs["dim"] = shared_dim
            fstr_kwargs["val"] = shared_coord
            fstr_kwargs["coords"] = frame_coords
            try:
                hlpr.fig.suptitle(
                    fstr.format(**fstr_kwargs),
                    **ensure_dict(suptitle_kwargs),
                )
            except Exception as exc:
                _fstr_kwargs = "\n".join(
                    f"    {k}:  {v}" for k, v in fstr_kwargs.items()
                )
                raise ValueError(
                    "Failed setting suptitle, probably due to a formatting "
                    "issue! Check the format string and the available "
                    "formatting values are compatible.\n"
                    f"  suptitle_fstr:  {repr(fstr)}\n"
                    f"  fstr_kwargs:\n{_fstr_kwargs}"
                ) from exc

        return shared_dim, shared_coord

    def parse_frame_coords(*iters, names: list) -> dict:
        """Extracts the current frame coordinate values from the state of the
        iterators. This is necessary because coordinate values may also be none
        if some layers are not iterated over.
        """

        def parse_coord(frit: Optional[tuple]):
            if frit is None:
                return None
            c, _ = frit
            return c

        coords = {
            names[i]: parse_coord(frit[0]) for i, frit in enumerate(iters)
        }
        # TODO check for equal values in case there *is* a coordinate?!

        return coords

    def parse_domain_kwargs(
        domain: Union[None, str, list, tuple, dict]
    ) -> dict:
        if domain is None:
            return dict()
        elif isinstance(domain, str):
            return dict(mode=domain)
        elif isinstance(domain, (list, tuple)):
            return dict(extent=domain, pad=0)
        elif isinstance(domain, dict):
            return domain

        raise TypeError(
            f"Got invalid type {type(domain)} for `domain` argument! "
            "Valid types are:  None, str, tuple, list, dict"
        )

    # .........................................................................

    # Work on a copy of the plot spec, to be on the safe side.
    to_plot = copy.deepcopy(to_plot)

    # Bring data into expected form and
    log.note("Preparing data for ABM plot ...")
    shared_kwargs = dict(
        frames=frames,
        frames_isel=frames_isel,
        **shared_kwargs,
    )
    layers = {
        k: prepare_layer_specs(k, shared_kwargs=shared_kwargs, **spec)
        for k, spec in to_plot.items()
    }
    layer_names = list(layers)

    # Check frames iteration
    num_frames = [layers[lyr]["num_frames"] for lyr in layer_names]
    if not all([n == 0 or n == num_frames[0] for n in num_frames]):
        _info = "\n".join(
            f"  {layer_names[i]:12}: {n:4d}" for i, n in enumerate(num_frames)
        )
        raise ValueError(
            "There was a mismatch in the length of the given frame iterators! "
            "Iterators need either be of the same length along the `frames` "
            "dimension or zero (if there is no `frames` dimension for that "
            f"layer).\nGiven iterator lengths were:\n{_info}"
        )
    else:
        num_frames = num_frames[0]

    # May need to switch in to / out of animation mode
    if num_frames > 1:
        hlpr.enable_animation()
    else:
        hlpr.disable_animation()

    # Construct the aggregated frames iterators object
    _frits = [layers[lyr]["frames_iter"] for lyr in layer_names]
    mock_frit = lambda: [None] * max(1, num_frames)
    frames_iters = zip(
        *[frit if frit is not None else mock_frit() for frit in _frits]
    )

    # Determine the name of a potentially existing shared frames dimension
    shared_frames_dim = None
    frame_dims = [layers[lyr]["frames"] for lyr in layer_names]
    unique_frame_dim_names = set([f for f in frame_dims if f])
    if unique_frame_dim_names and len(unique_frame_dim_names) == 1:
        shared_frames_dim = unique_frame_dim_names.pop()

    # Extract domain information and set the x- and y-axis limits.
    domain_area, _aspect = _set_domain(
        ax=hlpr.ax, layers=layers, **parse_domain_kwargs(domain)
    )

    # Inform about the plot ...
    log.remark("  Data variables:         %s", ", ".join(to_plot))
    log.remark(
        "  Frames dimension(s):    %s",
        (
            shared_frames_dim
            if shared_frames_dim
            else ", ".join(f"{f}" for f in frame_dims)
        ),
    )
    log.remark(
        "  Number of frames:       %s",
        num_frames if num_frames > 1 else "(snapshot)",
    )
    log.remark(
        "  Domain area:            %.4g  (aspect: %.3g)", domain_area, _aspect
    )

    if adjust_figsize_to_domain:
        adjust_figsize_to_aspect(_aspect + figsize_aspect_offset, fig=hlpr.fig)
        _fw, _fh = hlpr.fig.get_size_inches()
        log.remark("  Figure size adjusted:   [%.3g, %.3g]", _fw, _fh)

    # .. Define single frame and animation update functions ...................
    # For simplicity, these use objects from the outer scope

    def plot_frame(frame_data: tuple, *, frame_no: int):
        """Plots a single frame from the given frame data"""
        frame_coords = parse_frame_coords(frame_data, names=layer_names)
        set_suptitle(
            suptitle_fstr,
            shared_dim=shared_frames_dim,
            frame_coords=frame_coords,
            frame_no=frame_no,
        )

        for lyr_no, coords_and_data in enumerate(frame_data):
            lyr_spec = layers[layer_names[lyr_no]]

            # Get the data
            if coords_and_data is None:
                # No iterator available; only need to draw once
                if lyr_spec["coll"] is not None:
                    continue
                xy = lyr_spec["data"]

            else:
                # always draw, using the data from the iterator
                _, xy = coords_and_data

            # May need to squeeze out size-1 dimensions that are created from
            # the .groupby iteration
            if lyr_spec["frames"]:
                xy = xy.squeeze(dim=lyr_spec["frames"], drop=True)

            # Now draw
            lyr_spec["coll"] = draw_agents(
                xy,
                ax=hlpr.ax,
                **lyr_spec["plot_kwargs"],
                _collection=lyr_spec["coll"],
                _domain_area=domain_area,
            )

        # May want to update the domain
        _set_domain(
            ax=hlpr.ax,
            layers=layers,
            update_only=True,
            **parse_domain_kwargs(domain),
        )

        hlpr.invoke_enabled()  # FIXME should not have to do this here!?

    def update():
        # First frame was already plotted, grab it directly
        yield

        # Plot the rest
        for frame_no, frame_data in enumerate(frames_iters):
            plot_frame(frame_data, frame_no=frame_no + 1)

            # Done with this frame; yield control to the animation framework
            # which will grab the frame...
            yield

        if frame_no > 1:
            log.info("Animation finished.")

    hlpr.register_animation_update(update)

    # .. Actual plotting ......................................................

    # Plot only the first frame here; all further frames are plotted via the
    # helper's animation framework.
    # What is done here is meant for the case of the snapshot and advances the
    # iterator by one. The captured iterator in the update function above
    # will then continue from the second frame.
    plot_frame(frames_iters.__next__(), frame_no=0)

    # Create the legend
    if add_legend:
        log.caution("Adding a legend via abmplot will probably be buggy!")
        hlpr.ax.legend()
