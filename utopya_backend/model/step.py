"""Implements a model that is optimized for a stepwise iteration paradigm."""

import abc

from .base import BaseModel

# -----------------------------------------------------------------------------


class StepwiseModel(BaseModel):
    """A base class that is optimized for models based on stepwise integration,
    i.e. with constant time increments."""

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
        return bool(
            self._time > self._write_start
            and self._time % (self._write_every - self._write_start) == 0
        )

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

        self.log.info("Extracting time step parameters ...")
        self._num_steps = num_steps
        self._write_every = write_every
        self._write_start = write_start

        self.log.info("  Iteration steps:  %-8d", self.num_steps)
        self.log.info("  Write every:      %-8d", self.write_every)
        self.log.info("  Write start:      %-8d", self.write_start)

    def _setup_finished(self):
        """Called after the model setup has finished."""
        # May want to write initial state
        if self.write_start <= 0:
            self.log.info("Writing initial state ...")
            self.write_data()
            self.log.info("Initial state written.\n")

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
