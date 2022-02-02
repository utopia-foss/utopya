"""All model registry related error types

.. todo::

    Should be migrated to utopya.exceptions
"""


class ModelRegistryError(ValueError):
    """Raised on errors with model registry"""


class BundleExistsError(ModelRegistryError):
    """Raised when a bundle that compared equal already exists."""
