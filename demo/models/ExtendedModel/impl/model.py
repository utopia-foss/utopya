"""This module implements the actual model, making use of the base model class
implemented in :py:class:`~utopya_backend.model.step.StepwiseModel`.
"""

from typing import Tuple

import numpy as np

from utopya_backend import StepwiseModel

# -----------------------------------------------------------------------------


class ExtendedModel(StepwiseModel):
    """The actual model implementation"""

    def setup(
        self,
        *,
        distribution_params: dict,
        state_size: int,
        grid_shape: Tuple[int, int],
        dataset_kwargs: dict = None,
    ):
        """Sets up the model: stores parameters, sets up the model's internal
        state, and creates datasets for storing them."""
        self.log.info("Setting up state vector and CA ...")

        self._distribution_params = distribution_params

        # Setup state as random values in [0, 1)
        self._state = self.rng.uniform(
            **self._distribution_params, size=(state_size,)
        )
        self._ca = np.zeros(grid_shape, dtype=int)

        # .. Dataset setup ....................................................
        # Setup chunked datasets to store the state data in and add labelling
        # attributes that are interpreted by dantro to determine dimension
        # names and coordinate labels
        self.log.info("Setting up datasets ...")

        self._dsets = dict()
        dataset_kwargs = dict(
            chunks=True,
            **(dataset_kwargs if dataset_kwargs else {}),
        )
        start_and_step = [self.write_start, self.write_every]

        # The full state vector over time
        self._dsets["state"] = self.h5group.create_dataset(
            "state",
            (0, state_size),
            maxshape=(None, state_size),
            **dataset_kwargs,
        )
        self._dsets["state"].attrs["dim_names"] = ["time", "state_idx"]
        self._dsets["state"].attrs["coords_mode__time"] = "start_and_step"
        self._dsets["state"].attrs["coords__time"] = start_and_step
        self._dsets["state"].attrs["coords_mode__state_idx"] = "trivial"

        # The mean state over time
        self._dsets["mean_state"] = self.h5group.create_dataset(
            "mean_state",
            (0,),
            maxshape=(None,),
            **dataset_kwargs,
        )
        self._dsets["mean_state"].attrs["dim_name__0"] = "time"
        self._dsets["mean_state"].attrs["coords_mode__time"] = "start_and_step"
        self._dsets["mean_state"].attrs["coords__time"] = start_and_step

        # A 2D grid, written as flattened array
        self._dsets["ca"] = self.h5group.create_dataset(
            "ca",
            (0, self._ca.size),
            maxshape=(None, self._ca.size),
            **dataset_kwargs,
        )
        self._dsets["ca"].attrs["dim_name__0"] = "time"
        self._dsets["ca"].attrs["dim_name__1"] = "cell_ids"
        self._dsets["ca"].attrs["coords_mode__time"] = "start_and_step"
        self._dsets["ca"].attrs["coords__time"] = start_and_step
        self._dsets["ca"].attrs["coords_mode__cell_ids"] = "trivial"
        self._dsets["ca"].attrs["content"] = "grid"
        self._dsets["ca"].attrs["grid_shape"] = self._ca.shape
        self._dsets["ca"].attrs["grid_structure"] = "square"
        self._dsets["ca"].attrs["index_order"] = "C"  # numpy default
        self._dsets["ca"].attrs["space_extent"] = self._ca.shape

        self.log.debug("Created datasets: %s", ", ".join(self._dsets))

    def perform_step(self):
        """Performs the model's iteration:

        #. Adds uniformly random integers to the state vector.
        #. Increments the state of a random position on the CA.
        """
        self._state += self.rng.uniform(
            **self._distribution_params, size=(self._state.size,)
        )

        rand_midx = np.unravel_index(
            self.rng.integers(0, self._ca.size), self._ca.shape
        )
        self._ca[rand_midx] += 1

    def monitor(self, monitor_info: dict):
        """Provides information about the current state of the model to the
        monitor, which is then emitted to the frontend."""
        monitor_info["state_mean"] = self._state.mean()
        monitor_info["ca_max"] = self._ca.max()

        return monitor_info

    def write_data(self):
        """Write the current state of the model into corresponding datasets.

        In the case of HDF5 data writing that is used here, this requires to
        extend the dataset size prior to writing; this way, the newly written
        data is always in the last row of the dataset.
        """
        for ds in self._dsets.values():
            ds.resize(ds.shape[0] + 1, axis=0)

        self._dsets["mean_state"][-1] = self._state.mean()
        self._dsets["state"][-1, :] = self._state
        self._dsets["ca"][-1, :] = self._ca.flat
