"""This submodule implements a registry of Utopia models, which is used to
provide the required model information to the frontend and use it throughout.
"""
from ..exceptions import BundleExistsError, ModelRegistryError
from .entry import ModelRegistryEntry

# Make names of class definitions available
from .info_bundle import ModelInfoBundle

# Import the registry class only as "private"; should only be instantiated once
from .registry import ModelRegistry as _ModelRegistry

MODELS = _ModelRegistry()
"""The model registry"""

# Make utility functions available which work on the created model registry
from .utils import get_info_bundle, load_model_cfg
