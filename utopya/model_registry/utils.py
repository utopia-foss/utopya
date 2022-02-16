"""Utility functions that work on the already initialized model registry."""

import logging
from typing import Tuple, Union

from .._yaml import load_yml
from ..parameter import extract_validation_objects
from . import MODELS
from .info_bundle import ModelInfoBundle

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


def get_info_bundle(
    *,
    model_name: str = None,
    info_bundle: ModelInfoBundle = None,
    bundle_label: Union[str, int] = None,
) -> ModelInfoBundle:
    """Determine the model info bundle in cases where both a model name
    and an info bundle are allowed as arguments.

    Args:
        model_name (str, optional): The model name.
        info_bundle (ModelInfoBundle, optional): The info bundle object.
            If given, will directly return this object again.
        bundle_label (Union[str, int], optional): In cases where only the model
            name is given, the bundle_label can be used for item access,
            e.g. in cases where more than one bundle is available and access
            would be ambiguous.

    Returns:
        ModelInfoBundle: The selected info bundle item

    Raises:
        ValueError: If neither or both model_name and info_bundle were None
    """
    if model_name is None == info_bundle is None:  # XOR-check existence
        raise ValueError(
            "Need either of the arguments model_name or "
            "info_bundle, but got both or neither!"
        )

    if info_bundle:
        return info_bundle

    if bundle_label is None:
        return MODELS[model_name].item()
    return MODELS[model_name][bundle_label]


def load_model_cfg(**get_info_bundle_kwargs) -> Tuple[dict, str, dict]:
    """Loads the default model configuration file for the given model name,
    using the path specified in the info bundle.

    Furthermore, :py:func:`~utopya.parameter.extract_validation_objects` is
    called to extract any Parameter objects that require validation, replace
    them with their default values, and gather the Parameter class objects
    into a separate dict.

    Args:
        **get_info_bundle_kwargs: Used to retrieve the info bundle via
            :py:func:`~utopya.model_registry.utils.get_info_bundle`

    Returns:
        Tuple[dict, str, dict]: The corresponding model configuration, the path
            to the model configuration file, and the Parameter class objects
            requiring validation.
            Will be ``{}, None, {}`` if there is no default configuration
            available in the selected info bundle.

    Raises:
        FileNotFoundError: On missing file
    """
    bundle = get_info_bundle(**get_info_bundle_kwargs)
    if "default_cfg" not in bundle.paths:
        log.debug(
            "No default model configuration available for '%s'.",
            bundle.model_name,
        )
        return {}, None, {}

    path = bundle.paths["default_cfg"]

    log.debug(
        "Loading default model configuration for '%s' model ...\n  %s",
        bundle.model_name,
        path,
    )

    try:
        model_cfg = load_yml(path)

    except FileNotFoundError as err:
        raise FileNotFoundError(
            "Could not locate default configuration for "
            f"'{bundle.model_name}' model! Expected to find it at: {path}"
        ) from err

    # Collect the validation objects from the model configuration and replace
    # them with their default values
    model_cfg, to_validate = extract_validation_objects(
        model_cfg, model_name=bundle.model_name
    )
    return model_cfg, path, to_validate
