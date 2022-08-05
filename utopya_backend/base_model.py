"""This module implements the :py:class:`.BaseModel` class which can be
inherited from for implementing a utopya-controlled model."""

import os
import signal
import sys
import time
from typing import Union

import h5py as h5
import numpy as np

from .logging import backend_logger as _backend_logger
from .signal import SIG_STOPCOND, SIGNAL_INFO, attach_signal_handlers
from .tools import load_cfg_file as _load_cfg_file

# -----------------------------------------------------------------------------


class BaseModel:
    """A base model class that can be inherited from to implement a model.
    This class provides basic simulation infrastructure in a way that it
    couples to utopya as a frontend.

    This class:

    - provides a shared RNG instance and a logger.
    - includes logic to evaluate ``num_steps`` and ``write_{start,every}``
    - emits monitor information to the frontend, informing the utopya frontend
      about simulation progress
    """

    def __init__(self, *, cfg_file_path: str, _log: "logging.Logger" = None):
        """Initialize the model instance, constructing an RNG and HDF5 group
        to write the output data to.

        .. note::

            This base class is not meant for hierarchically nested models.
            It is not meant to be instantiated on its own and does not
            represent something like a "root model".

        Args:
            cfg_file_path (str): The path to the config file.
            _log (logging.Logger, optional): The logger instance from which to
                create a child logger for this model. If not given, will use
                the backend logger instance.
        """
        if _log is None:
            _log = _backend_logger

        _log.info("Loading configuration file ...\n  %s", cfg_file_path)
        self._cfg = _load_cfg_file(cfg_file_path)

        # Carry over the name
        self._name = self._cfg["root_model_name"]
        _log.info("Setting up model infrastructure ...")
        _log.info("  Class name:       %s", type(self).__name__)
        _log.info("  Instance name:    %s", self.name)

        # Can now set up the loggers
        self._log = None
        self._setup_loggers(_log)

        # Attach signal handlers for stop conditions and interrupts
        self.log.info("Attaching signal handlers ...")
        attach_signal_handlers()

        # Time step information
        self.log.info("Extracting time step parameters ...")
        self._time = 0
        self._num_steps = self._cfg["num_steps"]
        self._write_every = self._cfg["write_every"]
        self._write_start = self._cfg["write_start"]

        # Monitoring
        self.log.info("Extracting monitoring settings ...")
        self._last_emit = 0
        self.monitor_info = dict()
        self._monitor_emit_interval = self._cfg["monitor_emit_interval"]

        # RNG
        seed = self._cfg["seed"]
        self.log.info(f"Creating shared RNG (seed: {seed}) ...")
        self._rng = np.random.default_rng(seed)

        # HDF5 file
        self.log.info(
            "Creating HDF5 output file at:\n  %s\n", self._cfg["output_path"]
        )
        self._h5file = h5.File(self._cfg["output_path"], mode="x")
        self._h5group = self._h5file.create_group(self._name)

        # Actual model initialization
        self.log.info("Invoking model setup ...")
        self._model_cfg = self._cfg[self._name]
        self.setup(**self._model_cfg)
        self.log.info("Model setup finished.\n")

        # May want to write initial state
        if self._write_start <= 0:
            self.log.info("Writing initial state ...")
            self.write_data()

        # First monitoring
        self.monitor()
        self._last_emit = time.time()

        # Done.
        self.log.info(
            "Initialized %s named '%s'.\n", type(self).__name__, self.name
        )

    def __del__(self):
        """Takes care of tearing down the model"""
        self.log.debug("Tearing down model instance ...")

        self._h5file.close()

        self.log.debug("Teardown complete.")

    # .. Setup helpers ........................................................

    def _setup_loggers(self, _log: "logging.Logger"):
        """Sets up the model logger and configures"""
        from .logging import get_level

        _log.info("Setting up loggers ...")

        # TODO Allow changing log formatters globally

        # Model logger and its level
        self._log = _log.getChild(self.name)

        log_level = self._cfg["log_levels"]["model"]
        self._log.setLevel(get_level(log_level))
        self.log.info("  Model logger initialized with '%s' level.", log_level)

        # May want to adjust the backend logger
        backend_log_level = self._cfg["log_levels"].get("backend")
        if backend_log_level is not None:
            _backend_logger.setLevel(get_level(backend_log_level))
            self.log.info(
                "  Set backend logger's level to '%s'.", backend_log_level
            )

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
    def time(self) -> int:
        """Returns the current time"""
        return self._time

    @property
    def num_steps(self) -> int:
        """Returns the ``num_steps`` parameter of this model instance"""
        return self._num_steps

    @property
    def write_start(self) -> int:
        """Returns the ``write_start`` parameter of this model instance"""
        return self._write_start

    @property
    def write_every(self) -> int:
        """Returns the ``write_every`` parameter of this model instance"""
        return self._write_every

    # .. Simulation control ...................................................

    def run(self):
        """Performs a simulation run for this model, calling the iterate
        method until the number of desired steps has been carried out.
        """
        self._invoke_prolog()

        self.log.info(
            "Commencing model run with %s iterations ...", self.num_steps
        )

        while self._time < self._num_steps:
            self.iterate()

            self.log.debug(
                "Finished iteration %d / %d.", self.time, self.num_steps
            )

            # Handle signals, which may lead to a sys.exit
            if (exit_code := self._handle_signal(SIGNAL_INFO)) is not None:
                self._invoke_epilog(finished_run=False)
                self.log.info(
                    "Now exiting after iteration %d / %d ...",
                    self.time,
                    self.num_steps,
                )
                sys.exit(exit_code)

        self._invoke_epilog(finished_run=True)
        self.log.info("Simulation run finished.\n")

    def iterate(self):
        """Performs a single iteration: a simulation step, monitoring, and
        writing data"""
        # Step iteration
        self.perform_step()
        self._time += 1

        # Monitoring
        self.monitor()

        # Writing data
        if (
            self._time > self._write_start
            and self._time % (self._write_every - self._write_start) == 0
        ):
            self.write_data()

        # TODO Prolog and Epilog

    # .. Helpers, Signalling, Monitoring ......................................

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

    def _handle_signal(self, signal_info: dict) -> Union[None, int]:
        """Evaluates whether the iteration should stop due to an (expected)
        signal, e.g. from a stop condition or an interrupt.
        If it should stop, will return an integer, which can then be passed
        into :py:func:`sys.exit`.

        Exit codes will be ``128 + abs(signum)``, as is convention. This is
        also expected by :py:class:`~utopya.workermanager.WorkerManager` and is
        used to behave differently on a stop-condition-related signal than on
        an interrupt signal.

        Args:
            signal_info (dict): The signal info dict, containing the keys
                ``got_signal`` and ``signum``.

        Returns:
            Union[None, int]: An integer if the signal denoted that there
                should be a system exit; None otherwise.
        """
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

    def _monitor_should_emit(self, *, force: bool = False) -> bool:
        """Evaluates whether the monitor should emit. This method will only
        return True once after a monitor emit interval has passed.

        Args:
            force (bool, optional): If True, will update time and return True.

        Returns:
            bool: Whether to emit or not.
        """
        t = time.time()
        if force or t > self._last_emit + self._monitor_emit_interval:
            self._last_emit = t
            return True
        return False

    def _emit_monitor(self):
        """Actually emits the monitoring information to STDOUT"""
        # TODO Use YAML for creating the monitor string
        progress = str(self._time / self._num_steps)
        print(
            "!!map { progress: "
            + progress
            + ", "
            + self.name
            + ": "
            + repr(self.monitor_info)
            + "}",
            flush=True,
        )

    def monitor(self, *, force: bool = False):
        """Invokes monitoring:

        Checks whether it's time to emit. If so, updates monitor information
        and then calls :py:meth:`._emit_monitor`.
        """
        if self._monitor_should_emit(force=force):
            self.update_monitor_info()
            self._emit_monitor()

    # .. To-be-subclassed methods .............................................

    def setup(self):
        """Called upon initialization of the model"""
        raise NotImplementedError(
            "Your derived class needs to implement a `setup` method."
        )

    def perform_step(self):
        """Called upon each iteration"""
        raise NotImplementedError(
            "Your derived class needs to implement a `perform_step` method."
        )

    def write_data(self):
        """Called for periodically writing data"""
        raise NotImplementedError(
            "Your derived class needs to implement a `write_data` method."
        )

    # .. Optionally subclassable methods ......................................

    def update_monitor_info(self):
        """Called when a monitor emission is imminent; should be used to
        update the model-specific ``monitor_info`` attribute."""
        pass

    def prolog(self):
        """Always invoked after :py:meth:`.setup` and before the first
        iteration."""
        pass

    def epilog(self, *, finished_run: bool):
        """Always invoked after iteration has finished.

        This may happen either after the pre-defined ``num_steps`` have been
        iterated, or any time before that, e.g. due to an interrupt signal or
        a stop condition. In the latter case, ``finished_run`` will be False.
        """
        pass
