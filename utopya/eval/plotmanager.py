"""Implements a plotting framework based on dantro

In order to make the plotting framework specific to Utopia, this module derives
both from the dantro PlotManager and some PlotCreator classes.
"""

import contextlib
import copy
import importlib
import logging
import os
import sys
from typing import Dict, Union

import dantro
import dantro._import_tools
import dantro.plot.creators
import dantro.plot.utils
import dantro.plot_mngr

from ..model_registry import ModelInfoBundle
from ._plot_func_resolver import PlotFuncResolver
from .plotcreators import (
    MultiversePlotCreator,
    PyPlotCreator,
    UniversePlotCreator,
)

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class PlotManager(dantro.plot_mngr.PlotManager):
    """This is the Utopia-specific version of the dantro ``PlotManager``.

    It registers the Utopia-specific plot creators and allows for custom
    interface specifications, e.g. by preloading custom modules.
    """

    CREATORS: Dict[str, type] = dict(
        base=dantro.plot.creators.BasePlotCreator,
        external=PyPlotCreator,
        pyplot=PyPlotCreator,
        universe=UniversePlotCreator,
        multiverse=MultiversePlotCreator,
    )
    """Supported plot creator classes"""

    MODEL_PLOTS_MODULE_NAME = "model_plots"
    """Name under which the model-specific plots are made importable"""

    PLOT_FUNC_RESOLVER: type = PlotFuncResolver
    """The custom plot function resolver type to use."""

    # .........................................................................

    def __init__(
        self, *args, _model_info_bundle: ModelInfoBundle = None, **kwargs
    ):
        """Sets up a PlotManager.

        This specialization of the :py:class:`dantro.plot_mngr.PlotManager`
        additionally stores some utopya-specific metadata in form of a
        :py:class:`~utopya.model_registry.info_bundle.ModelInfoBundle` that
        describes the model this PlotManager is used with.
        That information is then used to load some additional model-specific
        information once a creator is invoked.

        Furthermore, the :py:meth:`._preload_modules` method takes care to make
        model-, project-, or framework-specific plot functions available.

        Args:
            *args: Positional arguments passed to
                :py:class:`~dantro.plot_mngr.PlotManager`.
            _model_info_bundle (ModelInfoBundle, optional): The internally-used
                argument to pass model information to the plot manager.
            **kwargs: Keyword arguments passed on to
                :py:class:`~dantro.plot_mngr.PlotManager`.
        """
        super().__init__(*args, **kwargs)

        self._model_info_bundle = copy.deepcopy(_model_info_bundle)

        self._preload_modules()

    @property
    def common_out_dir(self) -> str:
        """The common output directory of all plots that were created with
        this plot manager instance. This uses the plot output paths stored in
        the plot information dict, specifically the ``target_dir`` entry.

        If there was no plot information yet, the return value will be empty.
        """
        p = os.path.commonprefix([d["target_dir"] for d in self.plot_info])
        if not os.path.exists(p):
            p = os.path.dirname(p)
        return p

    def plot_from_cfg(
        self, *args, plots_cfg: Union[str, dict] = None, **kwargs
    ):
        """Thin wrapper around parent method that shows which plot
        configuration file will be used.
        """
        log.hilight(
            "Now creating plots for '%s' model ...",
            self._model_info_bundle.model_name,
        )
        if isinstance(plots_cfg, str):
            log.note("Plots configuration:\n  %s\n", plots_cfg)

        elif plots_cfg is None:
            log.note(
                "Using default plots configuration:\n  %s\n",
                self._model_info_bundle.paths.get("default_plots"),
            )

        return super().plot_from_cfg(*args, plots_cfg=plots_cfg, **kwargs)

    def _get_plot_func_resolver(self, **init_kwargs) -> PlotFuncResolver:
        """Instantiates the plot function resolver object.

        Additionally attaches the model info bundle to the resolver, such that
        it can use that information for plot function lookup.
        """
        return self.PLOT_FUNC_RESOLVER(
            **init_kwargs, _model_info_bundle=self._model_info_bundle
        )

    def _get_plot_creator(
        self, *args, **kwargs
    ) -> dantro.plot.creators.BasePlotCreator:
        """Sets up the BasePlotCreator and attaches a model information bundle
        to it such that this information is available downstream.
        """
        creator = super()._get_plot_creator(*args, **kwargs)
        creator._model_info_bundle = copy.deepcopy(self._model_info_bundle)

        return creator

    def _preload_modules(self):
        """Pre-loads the model-, project-, and framework-specific plot
        function modules.
        This allows to execute code (like registering model-specific dantro
        data operations) and have them available prior to the invocation of
        the creator and independently from the module that contains the plot
        function (which may be part of dantro, for instance).

        Uses :py:func:`dantro._import_tools.import_module_from_path`
        """
        import_module_from_path = dantro._import_tools.import_module_from_path
        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        # A simple exception handling context

        @contextlib.contextmanager
        def exception_handling(ExcType, scope: str):
            try:
                yield

            except ExcType as exc:
                _msg = (
                    f"{scope.title()}-specific plot module "
                    "could not be imported!"
                )
                if self.raise_exc:
                    raise ExcType(
                        f"{_msg}\n\nError was: {exc}\n\n"
                        "For debugging, inspect the traceback. Disable debug "
                        "mode to ignore exception and continue, even if this "
                        "may cause errors during plotting."
                    ) from exc
                log.warning(_msg)
                log.caution(
                    "This may lead to errors during plotting. "
                    "Enable debug mode to get a traceback."
                )

        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

        mib = self._model_info_bundle
        _preloaded = []

        if mib is not None:
            log.note("Pre-loading plot modules ...")

            mod_path = mib.paths.get("py_plots_dir")
            if mod_path and os.path.exists(mod_path):
                with exception_handling(ImportError, "model"):
                    log.debug("  Loading model-specific plot module ...")
                    _ms = f"{self.MODEL_PLOTS_MODULE_NAME}.{mib.model_name}"
                    import_module_from_path(
                        mod_path=mod_path,
                        mod_str=_ms,
                    )
                    _preloaded.append("model")

            # Also do this on the project and framework level
            # TODO Should make module name configurable separately! See #9
            project = mib.project
            if (
                project
                and project.paths.py_plots_dir
                and project.settings.preload_project_py_plots in (None, True)
            ):
                with exception_handling(ImportError, "project"):
                    log.debug("  Loading project-specific plot module ...")
                    dantro._import_tools.import_module_from_path(
                        mod_path=project.paths.py_plots_dir,
                        mod_str=f"{self.MODEL_PLOTS_MODULE_NAME}",
                    )
                    _preloaded.append("project")

            if (
                project
                and project.framework_project
                and project.settings.preload_framework_py_plots in (None, True)
            ):
                fw = project.framework_project
                if fw and fw.paths.py_plots_dir:
                    with exception_handling(ImportError, "framework"):
                        log.debug(
                            "  Loading framework-specific plot module ..."
                        )
                        import_module_from_path(
                            mod_path=fw.paths.py_plots_dir,
                            mod_str=f"{self.MODEL_PLOTS_MODULE_NAME}",
                        )
                        _preloaded.append("framework")

        if _preloaded:
            log.remark(
                "  Pre-loaded plot modules of:  %s", ", ".join(_preloaded)
            )
        else:
            log.remark(
                "  No `py_plots_dir` available or pre-loading deactivated."
            )
