"""This module implements the :py:class:`.BaseModel` class which can be
inherited from for implementing a utopya-controlled model."""

import os
import time

import h5py as h5
import numpy as np

from .logging import backend_logger as _backend_logger
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

        # Time step information
        self.log.info("Extracting time step parameters ...")
        self._time = 0
        self._num_steps = self._cfg["num_steps"]
        self._write_every = self._cfg["write_every"]
        self._write_start = self._cfg["write_start"]

        # Monitoring
        self.log.info("Extracting monitoring settings ...")
        self._last_emit = 0
        self._monitor_info = dict()
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
        self.log.info(
            "Commencing model run with %s iterations ...", self._num_steps
        )

        while self._time < self._num_steps:
            self.iterate()
            # TODO Interrupt handling

            self.log.debug(
                f"Finished iteration {self._time} / {self._num_steps}."
            )

        self.log.info("Simulation run finished.\n")

    def iterate(self):
        """Performs a single iteration: a simulation step, monitoring, and
        writing data"""
        self.perform_step()
        self._time += 1

        if self._monitor_should_emit():
            self.monitor()

        if (
            self._time > self._write_start
            and self._time % (self._write_every - self._write_start) == 0
        ):
            self.write_data()

    # .. Monitoring ...........................................................

    def _monitor_should_emit(self) -> bool:
        """Evaluates whether the monitor should emit. This method will only
        return True once after a monitor emit interval has passed.
        """
        t = time.time()
        if t > self._last_emit + self._monitor_emit_interval:
            self._last_emit = t
            return True
        return False

    def monitor(self):
        """Emits monitoring information to STDOUT"""
        # TODO Use YAML for creating the monitor string
        progress = str(self._time / self._num_steps)
        print(
            "!!map { progress: "
            + progress
            + ", "
            + self.name
            + ": "
            + repr(self._monitor_info)
            + "}",
            flush=True,
        )

    # .. Abstract (to-be-subclassed) methods ..................................

    def setup(self):
        raise NotImplementedError("setup")

    def perform_step(self):
        raise NotImplementedError("perform_step")

    def write_data(self):
        raise NotImplementedError("write_data")
