"""This module implements the actual model, making use of the BaseModel"""

from .base_model import BaseModel


class Model(BaseModel):
    """The actual model implementation"""

    def setup(
        self,
        *,
        distribution_params: dict,
        state_size: int,
        dataset_kwargs: dict = None,
    ):
        """Sets up the model: stores parameters, sets up the state, created
        datasets"""

        self._distribution_params = distribution_params

        # Setup state as random values in [0, 1)
        self._state = self._rng.uniform(
            **self._distribution_params, size=(state_size,)
        )

        # .. Dataset setup ....................................................
        # Setup chunked datasets to store the state data in and add labelling
        # attributes that are interpreted by dantro to determine dimension
        # names and coordinate labels
        self._dsets = dict()
        dataset_kwargs = dict(
            chunks=True, **(dataset_kwargs if dataset_kwargs else {})
        )
        start_and_step = [self._write_start, self._write_every]

        # The full state vector over time
        self._dsets["state"] = self._h5group.create_dataset(
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
        self._dsets["mean_state"] = self._h5group.create_dataset(
            "mean_state",
            (0,),
            maxshape=(None,),
            **dataset_kwargs,
        )
        self._dsets["mean_state"].attrs["dim_name__0"] = "time"
        self._dsets["mean_state"].attrs["coords_mode__time"] = "start_and_step"
        self._dsets["mean_state"].attrs["coords__time"] = start_and_step

        # Add labelling attributes

    def perform_step(self):
        """Performs the model's state iteration: adding random values to the
        state vector."""
        self._state += self._rng.uniform(
            **self._distribution_params, size=(self._state.size,)
        )

    def write_data(self):
        """Write the current state into the state dataset.

        In the case of HDF5 data writing that is used here, this requires to
        extend the dataset size prior to writing; this way, the newly written
        data is always in the last row of the dataset.
        """
        for ds in self._dsets.values():
            ds.resize(ds.shape[0] + 1, axis=0)

        self._dsets["state"][-1, :] = self._state
        self._dsets["mean_state"][-1] = self._state.mean()
