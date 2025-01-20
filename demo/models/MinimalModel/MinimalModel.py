#!/usr/bin/env python3
"""A minimal implementation of a model that uses the utopya interface"""

import sys
import time

import h5py as h5
import numpy as np
from ruamel.yaml import YAML

yaml = YAML(typ="safe")

# -----------------------------------------------------------------------------
# -- Model implementation -----------------------------------------------------
# -----------------------------------------------------------------------------


class MinimalModel:
    """A minimal model implementation that illustrates the utopya interface.

    This model does not implement any particularly interesting dynamics but
    simply adds up random numbers to a state vector.
    """

    def __init__(
        self,
        name: str,
        *,
        rng: np.random.Generator,
        h5group: h5.Group,
        state_size: int,
        distribution_params: dict,
        sleep_time: float,
        **__,
    ):
        """Initialize the model instance with a previously constructed RNG and
        HDF5 group to write the output data to.

        Args:
            name (str): The name of this model instance
            rng (np.random.Generator): The shared RNG
            h5group (h5.Group): The output file group to write data to
            state_size (int): Size of the state vector
            distribution_params (dict): Passed to the random number
                distribution
            sleep_time (float): how long to sleep each iteration step
            **__: Additional model parameters (ignored)
        """
        self._name = name
        self._time = 0
        self._h5group = h5group
        self._rng = rng

        self._distribution_params = distribution_params
        self._sleep_time = sleep_time

        # Setup state as random values in [0, 1)
        self._state = self._rng.uniform(
            **self._distribution_params, size=(state_size,)
        )

        # Setup chunked dataset to store the state data in
        self._dset_state = self._h5group.create_dataset(
            "state",
            (0, state_size),
            maxshape=(None, state_size),
            chunks=True,
            compression=3,
        )
        self._dset_mean_state = self._h5group.create_dataset(
            "mean_state",
            (0,),
            maxshape=(None,),
            chunks=True,
            compression=3,
        )

        # TODO Add labelling attributes?

    def iterate(self):
        """Performs a single iteration: a simulation step and writing data"""
        self.perform_step()
        self._time += 1

        self.write_data()

    def perform_step(self):
        """Performs the model's state iteration: adding random values to the
        state vector."""
        self._state += self._rng.uniform(
            **self._distribution_params, size=(self._state.size,)
        )

        if self._sleep_time > 0:
            time.sleep(self._sleep_time)

    def write_data(self):
        """Write the current state into the state dataset.

        In the case of HDF5 data writing that is used here, this requires to
        extend the dataset size prior to writing; this way, the newly written
        data is always in the last row of the dataset.
        """
        self._dset_state.resize(self._dset_state.shape[0] + 1, axis=0)
        self._dset_state[-1, :] = self._state

        self._dset_mean_state.resize((self._dset_mean_state.shape[0] + 1,))
        self._dset_mean_state[-1] = self._state.mean()


# -----------------------------------------------------------------------------
# -- Performing the simulation run --------------------------------------------
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    cfg_file_path = sys.argv[1]

    print("Preparing model run ...")
    print(f"  Loading config file:\n    {cfg_file_path}")
    with open(cfg_file_path, "r") as cfg_file:
        cfg = yaml.load(cfg_file)

    model_name = cfg.get("root_model_name", "MinimalModel")
    print(f"Model name:  {model_name}")

    print("  Creating global RNG ...")
    rng = np.random.default_rng(cfg["seed"])

    print(f"  Creating output file at:\n    {cfg['output_path']}")
    h5file = h5.File(cfg["output_path"], mode="w")
    h5group = h5file.create_group(model_name)

    print("\nInitializing model ...")
    model = MinimalModel(
        model_name, rng=rng, h5group=h5group, **cfg[model_name]
    )
    model.write_data()
    print(f"Initialized MinimalModel named '{model_name}'.")

    num_steps = cfg["num_steps"]
    print(f"\nNow commencing model run with {num_steps} iteration steps ...")
    for i in range(num_steps):
        model.iterate()
        # TODO Interrupt handling

        print(f"  Finished iteration {i+1} / {num_steps}.")

    print("\nSimulation run finished.")
    print("  Wrapping up ...")
    h5file.close()

    print("  All done.")
