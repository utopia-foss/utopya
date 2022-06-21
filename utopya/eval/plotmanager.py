"""Implements a plotting framework based on dantro

In order to make the plotting framework specific to Utopia, this module derives
both from the dantro PlotManager and some PlotCreator classes.
"""

import copy
import importlib
import logging
import os
import sys
from typing import Union

import dantro
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

    CREATORS = dict(
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

        This additionally stores some Utopia-specific metadata about the
        model this PlotManager is used with. That information is then used to
        load some additional model-specific information once a creator is
        invoked.
        """
        super().__init__(*args, **kwargs)

        self._model_info_bundle = copy.deepcopy(_model_info_bundle)

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

    def _get_plot_creator(self, *args, **kwargs):
        """Before actually retrieving the plot creator, invokes module
        pre-loading via :py:meth:`._preload_modules`.
        """
        self._preload_modules()

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
        """

        from .._import_tools import import_module_from_path

        mib = self._model_info_bundle

        if mib is not None:
            log.note("Pre-loading plot modules ...")
            mod_path = mib.paths.get("py_plots_dir")
            if mod_path:
                log.remark("  Loading model-specific modules ...")
                import_module_from_path(
                    mod_path=mod_path,
                    mod_str=f"{self.MODEL_PLOTS_MODULE_NAME}.{mib.model_name}",
                    debug=self.raise_exc,
                )

            # Also do this on the project and framework level
            # TODO Should make module name configurable separately! See #9
            project = mib.project
            if project and project.paths.py_plots_dir:
                log.remark("  Loading project-specific modules ...")
                import_module_from_path(
                    mod_path=project.paths.py_plots_dir,
                    mod_str=f"{self.MODEL_PLOTS_MODULE_NAME}",
                    debug=self.raise_exc,
                )

            if project and project.framework_project:
                fw = project.framework_project
                if fw and fw.paths.py_plots_dir:
                    log.remark("  Loading framework-specific modules ...")
                    import_module_from_path(
                        mod_path=fw.paths.py_plots_dir,
                        mod_str=f"{self.MODEL_PLOTS_MODULE_NAME}",
                        debug=self.raise_exc,
                    )
