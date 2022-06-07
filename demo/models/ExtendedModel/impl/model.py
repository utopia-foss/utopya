"""This module implements the actual model, making use of the BaseModel"""

from .base_model import BaseModel


class Model(BaseModel):
    """The actual model implementation"""

    def setup(
        self,
        *,
        distribution_params: dict,
        state_size: int,
    ):
        """Sets up the model: stores parameters, sets up the state, created
        datasets"""

        self._distribution_params = distribution_params

        # Setup state as random values in [0, 1)
        self._state = self._rng.uniform(
            **self._distribution_params, size=(state_size,)
        )

        # Setup chunked datasets to store the state data in
        self._dsets = dict()
        self._dsets["state"] = self._h5group.create_dataset(
            "state",
            (0, state_size),
            maxshape=(None, state_size),
            chunks=True,
            compression=3,
        )
        self._dsets["mean_state"] = self._h5group.create_dataset(
            "mean_state",
            (0,),
            maxshape=(None,),
            chunks=True,
            compression=3,
        )

        # TODO Add labelling attributes?

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
