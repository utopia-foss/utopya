"""This module implements the :py:class:`.BaseModel` class which can be
inherited from for implementing a utopya-controlled model.

Its main aim is to provide shared simulation infrastructure and does not make
further assumptions about the abstraction a model makes, like the step-wise
iteration done in :py:class:`~utopya_backend.model.step.StepwiseModel`."""

import abc
import os
import signal
import sys
import time
from typing import Union

import h5py as h5
import numpy as np

from ..logging import backend_logger as _backend_logger
from ..logging import get_level as _get_level
from ..signal import SIG_STOPCOND, SIGNAL_INFO, attach_signal_handlers
from ..tools import load_cfg_file as _load_cfg_file

# -----------------------------------------------------------------------------


class BaseModel(abc.ABC):
    """An abstract base model class that can be inherited from to implement a
    model. This class provides basic simulation infrastructure in a way that it
    couples to utopya as a frontend:

    - A shared RNG instance and a logger.
    - includes logic to evaluate ``num_steps`` and ``write_{start,every}``
    - emits monitor information to the frontend, informing the utopya frontend
      about simulation progress

    For more specific purposes, there are specialized classes that are built
    around a shared modelling paradigm like step-wise iteration of the model,
    see :py:class:`~utopya_backend.model.step.StepwiseModel`.
    """

    ATTACH_SIGNAL_HANDLERS: bool = True
    """If true, calls :py:func:`~utopya_backend.signal.attach_signal_handlers`
    to attach signal handlers for stop conditions and interrupts.

    .. hint::

        You may want to disable this in a subclass in case you cannot handle
        a case where a signal is meant to stop your simulation gracefully.
    """

    # .. Initialization and Teardown ..........................................

    def __init__(
        self,
        *,
        cfg_file_path: str,
        _log: "logging.Logger" = None,
    ):
        """Initialize the model instance, constructing an RNG and HDF5 group
        to write the output data to.

        .. todo::

            Allow initializing from a "parent model" such that hierarchical
            nesting of models becomes possible.

        Args:
            cfg_file_path (str): The path to the config file.
            _log (logging.Logger, optional): The logger instance from which to
                create a child logger for this model. If not given, will use
                the backend logger instance.
        """
        if _log is None:
            _log = _backend_logger

        # Get the root configuration and get the instance name from there
        self._root_cfg = self._get_root_cfg(cfg_file_path, _log=_log)
        self._name = self._root_cfg["root_model_name"]

        _bases = (b.__name__ for b in type(self).__bases__)
        _log.info("Setting up model infrastructure ...")
        _log.info("  Class name:       %s", type(self).__name__)
        _log.info("  Parent class:     %s", ", ".join(_bases))
        _log.info("  Instance name:    %s", self.name)

        # Can now set up the loggers
        self._log = None
        self._setup_loggers(_log)

        # Optionally attach signal handlers for stop conditions and interrupts
        if self.ATTACH_SIGNAL_HANDLERS:
            self._signal_info = SIGNAL_INFO
            self._attach_signal_handlers()

        # Monitoring
        self.log.info("Extracting monitoring settings ...")
        self._last_emit = 0
        self._monitor_info = dict()
        self._monitor_emit_interval = self.root_cfg["monitor_emit_interval"]

        # Keep track of number of iterations
        self._n_iterations = 0

        # RNG
        self._rng = self._setup_rng(seed=self.root_cfg["seed"])

        # Create the output file
        self._h5file = self._setup_output_file()
        self._h5group = self._setup_output_group()

        # Allow subclasses to parse root config parameters, potentiaally adding
        # more attributes
        self._parse_root_cfg(**self.root_cfg)

        # Actual model initialization
        self.log.info("Invoking model setup ...")
        self._cfg = self.root_cfg[self.name]
        self.setup(**self.cfg)
        self.log.info("Model setup finished.\n")

        # Allow subclasses to do something after setup has finished
        self._setup_finished()

        # First monitoring
        self.trigger_monitor(force=True)

        # Done.
        self.log.info(
            "Fully initialized %s named '%s'.\n",
            type(self).__name__,
            self.name,
        )

    def __del__(self):
        """Takes care of tearing down the model"""
        self.log.debug("Tearing down model instance ...")

        try:
            self._h5file.close()
        except Exception as exc:
            self.log.error(
                "Closing HDF5 file failed, got %s: %s", type(exc).__name__, exc
            )

        self.log.debug("Teardown complete.")

    # .. Properties ...........................................................

    @property
    def name(self) -> str:
        """Returns the name of this model instance"""
        return self._name

    @property
    def log(self) -> "logging.Logger":
        """Returns the model's logger instance"""
        return self._log

    @property
    def rng(self) -> "numpy.random.Generator":
        """Returns the shared random number generator instance"""
        return self._rng

    @property
    def h5group(self) -> "h5py.Group":
        """The HDF5 group this model should write to"""
        return self._h5group

    @property
    def root_cfg(self) -> dict:
        """Returns the root configuration of the simulation run"""
        return self._root_cfg

    @property
    def cfg(self) -> dict:
        """Returns the model configuration, ``self.root_cfg[self.name]``"""
        return self._cfg

    @property
    def n_iterations(self) -> int:
        """Returns the number of iterations performed by this base class, i.e.
        the number of times :py:meth:`.iterate` was called.

        .. note::

            This may not correspond to potentially existing other measures that
            specialized base classes implement. For instance,
            :py:meth:`utopya_backend.model.step.StepwiseModel.time` is *not*
            the same as the number of iterations.
        """
        return self._n_iterations

    # .. Simulation control ...................................................

    def run(self):
        """Performs a simulation run for this model, calling the
        :py:meth:`.iterate` method while :py:meth:`.should_iterate` is true.
        In addition, it takes care to invoke data writing and monitoring.

        Raises:
            SystemExit: Upon a (handled) signal.
        """
        self._invoke_prolog()

        self.log.info("Commencing model run ...")

        while self.should_iterate():
            self.iterate()
            self._n_iterations += 1

            # Allow to monitor simulation progress
            self.trigger_monitor()

            # Allow writing data
            if self.should_write():
                self.write_data()

            # Inform about the iteration
            self.show_iteration_info()

            # Handle signals, which may lead to a sys.exit
            if (exit_code := self._check_signals()) is not None:
                self._invoke_epilog(finished_run=False)
                self.log.info("Now exiting ...")
                sys.exit(exit_code)

        self._invoke_epilog(finished_run=True)
        self.log.info("Simulation run finished.\n")

    # .. Abstract methods .....................................................

    @abc.abstractmethod
    def setup(self) -> None:
        """Called upon initialization of the model"""

    @abc.abstractmethod
    def should_iterate(self) -> bool:
        """A method that determines whether :py:meth:`.iterate` should be
        called or not."""

    @abc.abstractmethod
    def iterate(self) -> None:
        """Called repeatedly until the end of the simulation, which can be
        either due to"""

    @abc.abstractmethod
    def should_write(self) -> bool:
        """A method that determines whether :py:meth:`.write_data` should be
        called after an iteration or not."""

    @abc.abstractmethod
    def write_data(self) -> None:
        """Performs data writing if :py:meth:`.should_write` returned true."""

    # .. Optionally subclassable methods ......................................

    def _parse_root_cfg(self, **_) -> None:
        """Invoked from within :py:meth:`.__init__`, parses and handles
        configuration parameters.

        .. hint:: This method can be specialized in a subclass.
        """
        pass

    def _setup_finished(self) -> None:
        """Invoked from within :py:meth:`.__init__` after the call to the
        :py:meth:`.setup` method has finished.

        .. hint:: This method can be specialized in a subclass.
        """
        pass

    def monitor(self, monitor_info: dict) -> dict:
        """Called when a monitor emission is imminent; should be used to
        update the (model-specific) monitoring information passed here as
        arguments.

        .. hint:: This method can be specialized in a subclass.
        """
        return monitor_info

    def compute_progress(self) -> float:
        """Computes the progress of the simulation run. Should return a float
        between 0 and 1 and should *always* be monotonic.

        .. hint:: This method can be specialized in a subclass.
        """
        return 0.0

    def show_iteration_info(self) -> None:
        """A method that informs about the current iteration"""
        self.log.debug("Finished iteration %d.", self.n_iterations)

    def prolog(self) -> None:
        """Invoked at the beginning of :py:meth:`.run`, before the first call
        to :py:meth:`.iterate`.

        .. hint:: This method can be specialized in a subclass.
        """
        pass

    def epilog(self, *, finished_run: bool) -> None:
        """Always invoked at the end of :py:meth:`.run`.

        This may happen either after :py:meth:`.should_iterate` returned False
        or any time before that, e.g. due to an interrupt signal or a stop
        condition. In the latter case, ``finished_run`` will be False.

        .. hint:: This method can be specialized in a subclass.
        """
        pass

    # .. Signalling ...........................................................

    def _attach_signal_handlers(self):
        """Invoked from :py:meth:`.__init__`, attaches a signal handler for the
        stop condition signal and other interrupts.

        .. note::

            This should only be overwritten if you want or need to do your own
            signal handling.
        """
        self.log.info("Attaching signal handlers ...")
        attach_signal_handlers()

    def _check_signals(self) -> Union[None, int]:
        """Evaluates whether the iteration should stop due to an (expected)
        signal, e.g. from a stop condition or an interrupt.
        If it should stop, will return an integer, which can then be passed
        into :py:func:`sys.exit`.

        Exit codes will be ``128 + abs(signum)``, as is convention. This is
        also expected by :py:class:`~utopya.workermanager.WorkerManager` and is
        used to behave differently on a stop-condition-related signal than on
        an interrupt signal.

        Returns:
            Union[None, int]: An integer if the signal denoted that there
                should be a system exit; None otherwise.
        """
        signal_info = self._signal_info

        if not signal_info["got_signal"]:
            return None

        # Received a signal
        signum = signal_info["signum"]
        if signum == SIG_STOPCOND:
            self.log.warning("A stop condition was fulfilled.")

        elif signum in (signal.SIGINT, signal.SIGTERM):
            self.log.warning("Was told to stop.")

        else:
            self.log.warning(
                "Got an unexpected signal: %d. Stopping ...", signum
            )

        return 128 + abs(signum)

    # .. Monitoring ...........................................................

    def _monitor_should_emit(self, *, t: float = None) -> bool:
        """Evaluates whether the monitor should emit. This method will only
        return True once a monitor emit interval has passed since the last
        time the monitor was emitted.

        Args:
            t (None, optional): If given, uses this time, otherwise calls
                :py:func:`time.time`.

        Returns:
            bool: Whether to emit or not.
        """
        t = t if t is not None else time.time()

        if t > self._last_emit + self._monitor_emit_interval:
            return True
        return False

    def _emit_monitor(self):
        """Actually emits the monitoring information using :py:func:`print`."""
        # TODO Consider using YAML for creating the monitor string
        def parse_val(v) -> str:
            if isinstance(v, float):
                return f"{v:6g}"
            return repr(v)

        progress = str(self.compute_progress())
        monitor_info = ", ".join(
            f"{k}: {parse_val(v)}" for k, v in self._monitor_info.items()
        )

        # Now emit ...
        # fmt: off
        print(
            "!!map { "
            + "progress: " + progress + ", "
            + "n_iter: " + str(self.n_iterations) + ", "
            + self.name + ": {" + monitor_info + "}"
            + "}",
            flush=True,
        )
        # fmt: on

    def trigger_monitor(self, *, force: bool = False):
        """Invokes the monitoring procedure:

        #. Checks whether :py:meth:`._monitor_should_emit`.
        #. If so, calls :py:meth:`.monitor` to update monitoring information.
        #. Then calls :py:meth:`._emit_monitor` to emit that information.

        If ``force`` is given, will always emit.

        .. hint::

            This method should not be subclassed, but it can be invoked from
            within the subclass at any desired point.
        """
        t = time.time()
        if force or self._monitor_should_emit(t=t):
            self._monitor_info = self.monitor(self._monitor_info)
            self._emit_monitor()
            self._last_emit = t

    # .. Other helpers ........................................................

    def _get_root_cfg(
        self, cfg_file_path: str, *, _log: "logging.Logger"
    ) -> dict:
        """Retrieves the root configuration for this simulation run by loading
        it from the given file path.
        """
        _log.info("Loading configuration file ...\n  %s", cfg_file_path)
        return _load_cfg_file(cfg_file_path)

    def _setup_loggers(self, _log: "logging.Logger"):
        """Sets up the model logger and configures the backend logger according
        to the ``log_levels`` entry set in the root configuration.

        .. todo::

            Allow setting the logging *format* as well.

        Args:
            _log (logging.Logger): The logger to initialize the model logger
                from, typically the
        """
        _log.info("Setting up loggers ...")

        # TODO Allow changing log formatters globally

        # Model logger and its level
        self._log = _log.getChild(self.name)

        log_level = self.root_cfg["log_levels"]["model"]
        self._log.setLevel(_get_level(log_level))
        self.log.info("  Model logger initialized with '%s' level.", log_level)

        # May want to adjust the backend logger
        backend_log_level = self.root_cfg["log_levels"].get("backend")
        if backend_log_level is not None:
            _backend_logger.setLevel(_get_level(backend_log_level))
            self.log.info(
                "  Set backend logger's level to '%s'.", backend_log_level
            )

    def _setup_rng(self, *, seed: int, **kwargs) -> "numpy.random.Generator":
        """Sets up the shared RNG"""
        self.log.info("Creating shared RNG (seed: %s) ...", seed)
        return np.random.default_rng(seed, **kwargs)

    def _setup_output_file(self) -> "h5py.File":
        """Creates the output file for this model; by default, it is a HDF5
        file that is managed by a :py:class:`h5py.File` object.

        .. note::

            This method can be subclassed to implement different output file
            formats. In that case, consider not using the ``_h5file`` and
            ``_h5group`` attributes but something else.
        """
        self.log.info(
            "Creating HDF5 output file at:\n  %s\n",
            self.root_cfg["output_path"],
        )
        return h5.File(self.root_cfg["output_path"], mode="x")

    def _setup_output_group(self, h5file: "h5py.File" = None) -> "h5py.Group":
        """Creates the group that this model's output is written to"""
        if h5file is None:
            h5file = self._h5file
        return h5file.create_group(self.name)

    def _invoke_prolog(self):
        """Helps invoking the :py:meth:`.prolog`"""
        self.log.debug("Invoking prolog ...")
        self.prolog()
        self.log.debug("Prolog finished.\n")

    def _invoke_epilog(self, **kwargs):
        """Helps invoking the :py:meth:`.epilog`"""
        self.log.debug("Invoking epilog ...")
        self.epilog(**kwargs)
        self.log.debug("Epilog finished.\n")
