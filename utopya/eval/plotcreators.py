"""Implements utopya-specializations of dantro plot creators"""

import logging
import os
import traceback
from types import ModuleType
from typing import Dict

import dantro
import dantro.plot_creators

from .._import_tools import temporary_sys_modules as _tmp_sys_modules
from .._import_tools import temporary_sys_path as _tmp_sys_path
from .plothelper import PlotHelper

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class ExternalPlotCreator(dantro.plot_creators.ExternalPlotCreator):
    """This is the Utopia-specific version of dantro's ``ExternalPlotCreator``.

    Its main purpose is to define common settings for plotting. By adding this
    extra layer, it allows for future extensibility as well.

    One of the common settings is that it sets as ``BASE_PKG`` the utopya
    :py:mod:`utopya.plot_funcs`, which is an extension of those functions
    supplied by dantro.
    """

    EXTENSIONS = "all"
    """Which file extensions to support.
    A value of ``all`` leads to no checks being performed on the extension.
    """

    DEFAULT_EXT = "pdf"
    """Default plot file extension"""

    BASE_PKG = "utopya.eval.plots"
    """Which package to use as base package for relative module imports"""

    PLOT_HELPER_CLS = PlotHelper
    """The PlotHelper class to use; here, the utopya-specific one"""

    def _get_custom_module_paths(self) -> Dict[str, str]:
        """Aggregates a dict of module paths from which imports are attempted.

        Uses model- or project-specific information, if available:

            - A model's ``py_plots_dir``
            - A project's ``py_plots_dir``
            - A project's additional ``py_modules``
        """
        p = dict()
        mib = getattr(self, "_model_info_bundle", None)
        if mib is None:
            return p

        if mib.paths.get("py_plots_dir"):
            p["model's py_plots_dir"] = mib.paths["py_plots_dir"]

        project = mib.project
        if project:
            if project["paths"].get("py_plots_dir"):
                p["project's py_plots_dir"] = project["paths"]["py_plots_dir"]

            for label, mod_path in project["custom_py_modules"].items():
                p[f"custom module '{label}'"] = mod_path

        return p

    def _get_module_via_import(self, module: str) -> ModuleType:
        """Extends the parent method by making the custom modules available if
        the regular import failed.
        """
        try:
            return super()._get_module_via_import(module)

        except ModuleNotFoundError as err:
            # Are there additional modules that are to be searched for imports?
            custom_module_paths = self._get_custom_module_paths()

            if not custom_module_paths:
                log.note(
                    "No custom module paths available to import '%s' from.",
                    module,
                )
                raise

        log.debug(
            "Module '%s' could not be imported with a default sys.path, "
            "but custom plot modules are available. Attempting to "
            "import it with %d additional path(s) being available.",
            module,
            len(custom_module_paths),
        )

        # Go over the specified custom paths and try to import them, gathering
        # detailed error information if that fails
        errors = dict()
        for key, mod_path in custom_module_paths.items():
            # In order to be able to import modules at the given path, the
            # sys.path needs to include the _parent_ directory of this path.
            parent_dir = os.path.dirname(mod_path)

            # Enter two context managers, taking care to return both sys.path
            # and sys.modules back to the same state as they were before their
            # invocation.
            # The latter context manager is crucial because module imports lead
            # to a cache entry even if a subsequent attempt to import a part of
            # the module string was the cause of an error (which makes sense).
            # Example: a failing `model_plots.foo` import would still lead to a
            # cache entry of the `model_plots` module; however, attempting to
            # then import `model_plots.bar` will make the lookup _only_ in the
            # cached module. As we want several import attempts here, the cache
            # is not desired.
            _tmp_sys_path = _tmp_sys_path(parent_dir)
            _tmp_sys_modules = _tmp_sys_modules(reset_only_on_fail=True)
            with _tmp_sys_path, _tmp_sys_modules:
                try:
                    mod = super()._get_module_via_import(module)

                except ModuleNotFoundError as err:
                    _tb = err.__traceback__
                    errors[parent_dir] = dict(
                        err=err,
                        tb=_tb,
                        tb_lines=traceback.format_tb(_tb),
                    )

                else:
                    log.debug(
                        "Found module '%s' after having added custom plot "
                        "module path labelled '%s' (%s) to the sys.path.",
                        mod,
                        key,
                        mod_path,
                    )
                    return mod

        # All imports failed. Inform extensively about errors to help debugging
        err_info = "\n".join(
            f"-- Error at custom plot module path {p} : {e['err']}\n\n"
            "  Abbreviated traceback:\n"
            f"{e['tb_lines'][0]} ...\n"
            f"{e['tb_lines'][-1]}"
            for p, e in errors.items()
        )
        raise ModuleNotFoundError(
            f"Could not import module '{module}'! It was found neither among "
            "the installed packages nor among the custom plot modules.\n"
            "\n"
            "The following errors were encountered at the respective custom "
            "plot module search paths:\n\n"
            f"{err_info}\n"
            "NOTE: This error can have two reasons:\n"
            f"  (1) the '{module}' module does not exist in the specified "
            " search location.\n"
            "  (2) during import of the plot module you specified, an "
            "_unrelated_ ModuleNotFoundError occurred somewhere inside _your_ "
            "code.\n"
            "To debug, check the error messages and tracebacks above to find "
            "out which of the two is preventing module import."
        )


class UniversePlotCreator(
    dantro.plot_creators.UniversePlotCreator, ExternalPlotCreator
):
    """Makes plotting with data from a single universe more convenient"""

    PSGRP_PATH = "multiverse"
    """The path within the data tree to arrive at the ParamSpaceGroup that this
    UniversePlotCreator expects universes to be located in.
    """


class MultiversePlotCreator(
    dantro.plot_creators.MultiversePlotCreator, ExternalPlotCreator
):
    """Makes plotting with data from *all* universes more convenient"""

    PSGRP_PATH = "multiverse"
    """The path within the data tree to arrive at the ParamSpaceGroup"""
