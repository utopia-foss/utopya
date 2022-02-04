"""Implements utopya-specializations of dantro plot creators"""

import logging
import os
import traceback

import dantro
import dantro.plot_creators

from ..cfg import load_from_cfg_dir as _load_from_cfg_dir
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

    CUSTOM_PLOT_MODULE_NAME = "model_plots"
    """The name to use for the module containing model-specific plots"""

    CUSTOM_PLOT_MODULE_PATHS = _load_from_cfg_dir("plot_module_paths")
    """The path to import the model-specific plot module"""

    def _get_module_via_import(self, module: str):
        """Extends the parent method by making the custom modules available if
        the regular import failed.
        """
        try:
            return super()._get_module_via_import(module)

        except ModuleNotFoundError as err:
            if (
                not self.CUSTOM_PLOT_MODULE_NAME
                or not self.CUSTOM_PLOT_MODULE_PATHS
                or not module.startswith(self.CUSTOM_PLOT_MODULE_NAME)
            ):
                # Should raise.
                # This also implicitly asserts that no python package with a
                # name equal to the prefix may be installed.
                raise

        log.debug(
            "Module '%s' could not be imported with a default sys.path, "
            "but is marked as a custom plot module. Attempting to "
            "import it from %d additional path(s).",
            module,
            len(self.CUSTOM_PLOT_MODULE_PATHS),
        )

        # A dict to gather error information in
        errors = dict()

        # Go over the specified custom paths and try to import them
        for key, path in self.CUSTOM_PLOT_MODULE_PATHS.items():
            # In order to be able to import modules at the given path, the
            # sys.path needs to include the _parent_ directory of this path.
            parent_dir = os.path.join(*os.path.split(path)[:-1])

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
            with _tmp_sys_path(parent_dir), _tmp_sys_modules():
                try:
                    mod = super()._get_module_via_import(module)

                except ModuleNotFoundError as err:
                    # Gather some information on the error
                    tb = err.__traceback__
                    errors[parent_dir] = dict(
                        err=err, tb=tb, tb_lines=traceback.format_tb(tb)
                    )

                else:
                    log.debug(
                        "Found module '%s' after having added custom "
                        "plot module path labelled '%s' (%s) to the "
                        "sys.path.",
                        mod,
                        key,
                        path,
                    )
                    return mod

        # All imports failed. Inform extensively about errors to help debugging
        err_info = "\n".join(
            [
                f"-- Error at custom plot module path {p} : {e['err']}\n\n"
                "  Abbreviated traceback:\n"
                f"{e['tb_lines'][0]} ...\n"
                f"{e['tb_lines'][-1]}"
                for p, e in errors.items()
            ]
        )
        raise ModuleNotFoundError(
            f"Could not import module '{module}'! It was found neither among "
            "the installed packages nor among the custom plot module paths.\n"
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
