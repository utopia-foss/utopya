"""This module implements the BaseModel class"""

import logging
import time
from typing import Dict

import h5py as h5
import numpy as np
import ruamel.yaml as yaml

# -----------------------------------------------------------------------------

LOG_LEVELS: Dict[str, int] = {
    "trace": 5,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARN,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "fatal": logging.FATAL,
    "not_set": logging.NOTSET,
    "notset": logging.NOTSET,
    "none": logging.NOTSET,
}
"""A map of log level names to actual level values"""

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

    def __init__(self, *, cfg_file_path: str):
        """Initialize the model instance, constructing an RNG and HDF5 group
        to write the output data to.

        .. note::

            This base class is not meant for hierarchically nested models.
            It is not meant to be instantiated on its own and does not
            represent something like a "root model".

        Args:
            cfg_file_path (str): The path to the config file.
        """
        try:
            with open(cfg_file_path, "r") as cfg_file:
                self._cfg = yaml.load(cfg_file, Loader=yaml.Loader)
        except:
            print(f"Failed loading config file:\n  {cfg_file_path}")
            raise

        # Carry over the name
        self._name = self._cfg["root_model_name"]

        # First thing: setup the logger
        # TODO Log formatting
        log_level = self._cfg["log_levels"]["model"].lower().replace(" ", "_")

        self._log = logging.getLogger(self.name)
        self._log.setLevel(LOG_LEVELS[log_level])
        self.log.info("Logger initialized with level '%s'.", log_level)

        self.log.info("Setting up %s ...", self.name)
        self.log.info("  Configuration file:\n  %s", cfg_file_path)

        # Time step information
        self.log.info("Extracting time step information ...")
        self._time = 0
        self._num_steps = self._cfg["num_steps"]
        self._write_every = self._cfg["write_every"]
        self._write_start = self._cfg["write_start"]

        # Monitoring
        self.log.info("Extracting monitoring information ...")
        self._last_emit = 0
        self._monitor_info = dict()
        self._monitor_emit_interval = self._cfg["monitor_emit_interval"]

        # RNG
        seed = self._cfg["seed"]
        self.log.info(f"Creating shared RNG (seed: {seed}) ...")
        self._rng = np.random.default_rng(seed)

        # HDF5 file
        self.log.info(
            f"Creating output file at:\n    {self._cfg['output_path']}"
        )
        self._h5file = h5.File(self._cfg["output_path"], mode="w")
        self._h5group = self._h5file.create_group(self._name)

        # Actual model initialization
        self.log.info("\nInitializing model ...")
        self._model_cfg = self._cfg[self._name]
        self.setup(**self._model_cfg)

        if self._write_start <= 0:
            self.log.info("Writing initial state ...")
            self.write_data()

        self.log.info(
            f"Initialized {type(self).__name__} named '{self._name}'."
        )

        # First monitoring
        self.monitor()
        self._last_emit = time.time()

    def __del__(self):
        """Takes care of tearing down the model"""
        self.log.debug("Tearing down model instance ...")

        self._h5file.close()

        self.log.debug("Teardown complete.")

    # .. Properties ...........................................................

    @property
    def name(self) -> str:
        """Returns the name of this model instance"""
        return self._name

    @property
    def log(self) -> logging.Logger:
        """Returns the logger instance"""
        return self._log

    # .. Simulation control ...................................................

    def run(self):
        """Performs a simulation run for this model, calling the iterate
        method until the number of desired steps has been carried out.
        """
        self.log.info(
            f"\nCommencing model run with {self._num_steps} iterations ..."
        )

        while self._time < self._num_steps:
            self.iterate()
            # TODO Interrupt handling

            self.log.info(
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
        self.log.info(
            "!!map { progress: "
            + progress
            + ", "
            + self.name
            + ": "
            + repr(self._monitor_info)
            + "}"
        )

    # .. Abstract (to-be-subclassed) methods ..................................

    def setup(self):
        raise NotImplementedError("setup")

    def perform_step(self):
        raise NotImplementedError("perform_step")

    def write_data(self):
        raise NotImplementedError("write_data")
