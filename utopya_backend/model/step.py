"""Implements a model that is optimized for a stepwise iteration paradigm."""

import abc
from typing import Tuple

from .base import BaseModel

# -----------------------------------------------------------------------------


class StepwiseModel(BaseModel):
    """A base class that is optimized for models based on stepwise integration,
    i.e. with constant time increments.


    The time steps that will be written are defined by a range operation,
    ``range(start, stop, step)``.
    More specifically: ``range(write_start, num_steps+1, write_every)``.
    """

    # .. Implementation of (some) abstract methods ............................

    def should_iterate(self) -> bool:
        """Iteration should continue until the maximum number of steps is
        reached."""
        return self._time < self._num_steps

    def iterate(self):
        """Performs a single iteration using a stepwise integration over a
        fixed time interval. The step consists of:

        #. the simulation step via :py:meth:`.perform_step`
        #. incrementing the model's ``time`` variable
        """
        self.perform_step()
        self._time += 1

    def should_write(self) -> bool:
        """Decides whether to write data or not"""
        return self._time in range(*self._write_start_stop_step)

    # .. New abstract methods .................................................

    @abc.abstractmethod
    def perform_step(self):
        """Called once from each :py:meth:`.iterate` call"""

    # .. Non-abstract method overwrites .......................................

    def _parse_root_cfg(
        self,
        *,
        num_steps: int,
        write_every: int = 1,
        write_start: int = 0,
        **_,
    ):
        """Extracts class-specific parameters from the model configuration.

        Args:
            num_steps (int): Number of iteration steps to make
            write_every (int, optional): How frequently to write data
            write_start (int, optional): When to start writing data
            **_: *ignored*
        """
        self._time = 0

        self.log.info("Extracting time step and writing parameters ...")
        self._num_steps = num_steps
        self._write_every = write_every
        self._write_start = write_start

        self.log.info("  Iteration steps:  %d", self.num_steps)
        self.log.info("  Write start:      %d", self.write_start)
        self.log.info("  Write every:      %d", self.write_every)

        _rg = range(*self._write_start_stop_step)
        self.log.info(
            "  Writing steps:    %d : %s = %s",
            len(_rg),
            _rg,
            (
                "[{}, {}, {}, …, {}, {}]".format(*_rg[:3], _rg[-2], _rg[-1])
                if len(_rg) > 6
                else list(_rg)
            ),
        )

    def _setup_finished(self):
        """Called after the model setup has finished."""
        # May want to write initial state
        if self.write_start <= 0:
            self.log.info("Writing initial state ...")
            self.write_data()
            self.log.info("Initial state written.\n")
        super()._setup_finished()

    def compute_progress(self) -> float:
        """Computes simulation progress"""
        return self.time / self._num_steps

    def show_iteration_info(self) -> None:
        """Informs about the state of the iteration"""
        self.log.debug("Finished step %d / %d.", self.time, self.num_steps)

    def _invoke_epilog(self, *, finished_run: bool, **kwargs):
        """Overwrites the parent method and logs some information in case that
        the epilog is invoked with ``not finished_run``."""
        if not finished_run:
            self.log.info(
                "Last iteration step was: %d / %d.", self.time, self.num_steps
            )

        super()._invoke_epilog(finished_run=finished_run, **kwargs)

    # .. Additional properties ................................................

    @property
    def time(self) -> int:
        """Returns the current time, which is incremented after each step.

        .. note::

            This is not the same as ``n_iterations`` that
            :py:class:`~utopya_backend.model.base.BaseModel` keeps track of!
        """
        return self._time

    @property
    def num_steps(self) -> int:
        """Returns the ``num_steps`` parameter for this simulation run."""
        return self._num_steps

    @property
    def write_start(self) -> int:
        """Returns the ``write_start`` parameter for this simulation run."""
        return self._write_start

    @property
    def write_every(self) -> int:
        """Returns the ``write_every`` parameter for this simulation run."""
        return self._write_every

    @property
    def _write_start_stop_step(self) -> Tuple[int, int, int]:
        return (self._write_start, self._num_steps + 1, self._write_every)

    # .. Data I/O helper methods ..............................................

    def create_ts_dset(
        self,
        name: str,
        *,
        extra_dims: tuple = (),
        sizes: dict = {},
        coords: dict = {},
        compression=2,
        **dset_kwargs,
    ) -> "h5py.Dataset":
        """Creates a :py:class:`h5py.Dataset` that is meant to store time
        series data. It supports adding extra dimensions to the back of the
        dataset and supports writing attributes that can be read (by the
        :py:mod:`dantro.utils.coords` module) to have dimension and coordinate
        labels available during data evaluation.

        The ``time`` dimension will be the very first one (``axis=0``) of the
        resulting dataset. Also, the initial size will be zero along that
        dimension – you will need to resize it before writing data to it.

        Args:
            name (str): Name of the dataset
            extra_dims (tuple, optional): Sequence of additional dimension
                names, which will follow the ``time`` dimension
            sizes (dict, optional): Sizes of the additional dimensions; if not
                given, will not limit the maximum size in that dimension.
            coords (dict, optional): Attributes that allow coordinate mapping
                will be added for all keys in this dict. Values can be either
                a dict with the ``mode`` and ``coords`` keys, specifying
                parameters for :py:func:`dantro.utils.coords.extract_coords`,
                or a list or 1D array that specifies coordinate values.
            compression (int, optional): Compression parameter for h5py dataset
            **dset_kwargs: Passed on to :py:meth:`h5py.Group.create_dataset`

        Raises:
            ValueError: If an invalid dimension name is given in ``coords`` or
                if the size of the coordinates did not match the dimension size
        """
        # Prepare arguments
        start, stop, step = self._write_start_stop_step
        start = max(self.time, start)
        num_writes = len(range(start, stop, step))

        dims = ("time",) + extra_dims
        extra_dim_sizes = tuple(sizes[d] for d in extra_dims)
        initial_size = (0,) + extra_dim_sizes
        maxshape = (num_writes,) + extra_dim_sizes

        # Create dataset
        dset = self.h5group.create_dataset(
            name,
            initial_size,
            maxshape=maxshape,
            chunks=True,
            compression=compression,
            **dset_kwargs,
        )

        # Assign attributes to allow dantro to assign dimension labels.
        dset.attrs["dim_names"] = list(dims)

        # For the time dimension, coordinates are clear
        dset.attrs["coords_mode__time"] = "start_and_step"
        dset.attrs["coords__time"] = [self.write_start, self.write_every]

        # For other dimensions, only add coordinates if they are given
        for dim_name, _coords in coords.items():
            if dim_name not in extra_dims:
                raise ValueError(
                    f"Dimension '{dim_name}' was not part of the list of "
                    f"provided `extra_dims`: {', '.join(extra_dims)}"
                )

            if isinstance(_coords, dict):
                mode, vals = _coords["mode"], _coords.get("coords", [])
            else:
                mode, vals = "values", _coords
                if len(vals) != sizes[dim_name]:
                    raise ValueError(
                        f"Given coordinate size ({len(vals)}) does not match "
                        f"size of '{dim_name}' dimension ({sizes[dim_name]})!"
                    )

            dset.attrs[f"coords_mode__{dim_name}"] = mode
            dset.attrs[f"coords__{dim_name}"] = vals

        return dset
