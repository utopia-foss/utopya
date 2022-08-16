"""This module implements various generic tools"""

import importlib
import os
import sys
from types import ModuleType
from typing import Any, Union

from .logging import backend_logger as _log

# -- YAML ---------------------------------------------------------------------


def load_cfg_file(fpath: str, *, loader: str = None) -> Any:
    """Loads a configuration file from the given file. Allows to automatically
    determine which kind of loading function to use.

    Currently supported loading functions: YAML

    Args:
        fpath (str): Path to the configuration file to load
        loader (str, optional): Name of the loader to use. If not given, will
            determine it from the file extension of ``fpath``.

    Returns:
        Any: The return value of the load function.

    Raises:
        ValueError: On invalid ``loader`` argument or a file extension that
            does not map to a supported loader.
    """
    if loader is None:
        # Determine from file extension
        _, ext = os.path.splitext(fpath)
        loader = ext.replace(".", "")
    loader = loader.lower()

    # Determine load function
    # TODO add toml, json, …
    if loader in ("yaml", "yml"):
        from paramspace.yaml import yaml

        load = yaml.load

    else:
        raise ValueError(
            f"Unsupported loader '{loader}' for configuration file! Check the "
            "file path and the `loader` argument.\n"
            f"  File path:  {fpath}\n"
            f"  Available loaders:  yml, yaml"
        )

    # Load now
    with open(os.path.expanduser(fpath), "r") as f:
        return load(f)


# -----------------------------------------------------------------------------


def import_package_from_dir(
    mod_dir: str, *, mod_str: str = None
) -> ModuleType:
    """Helper function to import a package-like module that is importable only
    when adding the module's parent directory to :py:data:`sys.path`.

    The ``mod_dir`` directory needs to contain an ``__init__.py`` file.
    If that is not the case, you cannot use this function, because the
    directory does not represent a package.

    .. hint::

        This function is very useful to get access to a local package that is
        *not* installed, as might be the case for your model implementation.
        Assuming you have an ``impl`` package right beside the current
        ``__file__`` and that package includes your ``Model`` class
        implementation:

        .. code-block:: text

            - run_model.py         # Current __file__
            - impl/                # Implementation package
              |-- __init__.py      # Exposes impl.model.Model
              |-- model.py         # Implements Model class
              |-- ...

        You can get access to it like this from within ``run_model.py``:

        .. code-block:: python

            import os
            from utopya_backend import import_package_from_dir

            impl = import_package_from_dir(
                os.path.join(os.path.dirname(__file__), "impl")
            )
            Model = impl.Model

    Args:
        mod_dir (str): Path to the module's root *directory*, ``~`` expanded.
            For robustness, relative paths are *not* allowed.
        mod_str (str, optional): Name under which the module can be imported
            with the *parent* of  ``mod_dir`` being in :py:data:`sys.path`.
            If not given, will assume it is equal to the last segment of
            ``mod_dir``.

    Returns:
        ModuleType: The imported module.

    Raises:
        ImportError: If ``debug`` is set and import failed for whatever reason
        FileNotFoundError: If ``mod_dir`` did not point to an existing
            *directory*
    """
    mod_dir = os.path.expanduser(mod_dir)
    if not os.path.isabs(mod_dir):
        raise ValueError(
            f"Need an absolute path for argument `mod_dir` but got:  {mod_dir}"
        )

    elif not os.path.isdir(mod_dir):
        raise FileNotFoundError(
            "The `mod_dir` argument to import a module from a path should be "
            f"the path to an existing directory! Given path:  {mod_dir}"
        )

    # Normalize it to ensure that it does not have a trailing slash
    mod_dir = os.path.realpath(mod_dir)

    # May need to infer module string
    if mod_str is None:
        mod_str = os.path.basename(mod_dir)

    # Need the parent directory in the path, because the import is only
    # possible from there. This, in turn, depends on the depth of the module
    # string, so the parent directory should be chosen accordingly.
    mod_parent_dir = mod_dir
    for _ in mod_str.split("."):
        mod_parent_dir = os.path.dirname(mod_parent_dir)

    _log.debug("Importing module '%s' from directory ...", mod_str)
    try:
        sys.path.insert(0, mod_parent_dir)
        mod = importlib.import_module(mod_str)

    except Exception as exc:
        raise ImportError(
            f"Failed importing module '{mod_str}'!\n"
            f"Make sure that {mod_dir}/__init__.py can be loaded without "
            "errors (with its parent directory being part of sys.path) "
            "and that the `mod_str` argument is correct; if you did not "
            "specify `mod_str` explicitly, consider doing so."
        ) from exc

    _log.debug("Successfully imported module from directory:  %s", mod)
    return mod
