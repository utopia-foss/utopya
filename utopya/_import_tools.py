"""Helper module that contains tools useful for module imports or manipulation
of the system path

.. todo::

    Consider migrating these to dantro._import_tools
"""

import copy
import importlib
import logging
import os
import sys
from types import ModuleType
from typing import Sequence, Union

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class temporary_sys_path:
    """A ``sys.path`` context manager, temporarily adding a path and removing
    it again upon exiting.
    If the given path already exists in the ``sys.path``, it is neither added
    nor removed and the ``sys.path`` remains unchanged.

    .. todo::

        Expand to allow multiple paths being added
    """

    def __init__(self, path: str):
        self.path = path
        self.path_already_exists = self.path in sys.path

    def __enter__(self):
        if not self.path_already_exists:
            log.debug("Temporarily adding '%s' to sys.path ...")
            sys.path.insert(0, self.path)

    def __exit__(self, *_):
        if not self.path_already_exists:
            log.debug("Removing temporarily added path from sys.path ...")
            sys.path.remove(self.path)


class temporary_sys_modules:
    """A context manager for the ``sys.modules`` cache, ensuring that it is in
    the same state after exiting as it was before entering the context manager.
    """

    def __init__(self, *, reset_only_on_fail: bool = False):
        """
        Set up the context manager for a temporary ``sys.modules`` cache.

        Args:
            reset_only_on_fail (bool, optional): If True, will reset the cache
                only in case the context is exited with an exception.
        """
        self._modules = copy.copy(sys.modules)
        self.reset_only_on_fail = reset_only_on_fail

    def __enter__(self):
        pass

    def __exit__(self, exc_type: type, *_):
        if self.reset_only_on_fail and exc_type is None:
            return

        elif sys.modules == self._modules:
            return

        # else: Reset module cache
        sys.modules = self._modules
        log.debug(
            "Resetted sys.modules cache to state before the "
            "context manager was added."
        )


def import_module_from_path(
    *, mod_path: str, mod_str: str, debug: bool = True
) -> Union[None, ModuleType]:
    """Helper function to import a module that is importable only when adding
    the module's parent directory to ``sys.path``.

    Args:
        mod_path (str): Path to the module's root directory
        mod_str (str): Name under which the module can be imported with
            ``mod_path`` being in ``sys.path``. This is also used to add the
            module to the ``sys.modules`` cache.
        debug (bool, optional): Whether to raise exceptions if import failed

    Returns:
        Union[None, ModuleType]: The imported module or None, if importing
            failed and ``debug`` evaluated to False.

    Raises:
        ImportError: If ``debug`` is set and import failed for whatever reason
    """
    # Need the parent directory in the path: import is only possible from there
    mod_parent_dir = os.path.dirname(os.path.dirname(mod_path))

    try:
        # Use the temporary environments to prevent that a *failed* import ends
        # up generating an erroneous sys.modules cache entry.
        _tmp_sys_path = temporary_sys_path(mod_parent_dir)
        _tmp_sys_modules = temporary_sys_modules(reset_only_on_fail=True)
        with _tmp_sys_path, _tmp_sys_modules:
            mod = importlib.import_module(mod_str)

    except Exception as exc:
        if debug:
            raise ImportError(
                f"Failed importing module '{mod_str}'!\n"
                f"Make sure that {mod_path}/__init__.py can be loaded without "
                "errors (with its parent directory being part of sys.path). "
                "To debug, inspect the chained traceback."
            ) from exc

        log.debug(
            "Importing module '%s' from %s failed: %s", mod_str, mod_path, exc
        )
        return

    else:
        log.debug("Successfully imported module '%s'.", mod_str)

    return mod
