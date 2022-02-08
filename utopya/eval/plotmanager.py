"""Implements a plotting framework based on dantro

In order to make the plotting framework specific to Utopia, this module derives
both from the dantro PlotManager and some PlotCreator classes.
"""

import importlib
import logging
import os
import sys
from typing import Union

import dantro
import dantro.plot_creators
import dantro.plot_mngr

from .._path_setup import temporary_sys_modules as _tmp_sys_modules
from .._path_setup import temporary_sys_path as _tmp_sys_path
from ..model_registry import ModelInfoBundle
from .plotcreators import MultiversePlotCreator, UniversePlotCreator

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class PlotManager(dantro.plot_mngr.PlotManager):
    """This is the Utopia-specific version of the dantro ``PlotManager``.

    It registers the Utopia-specific plot creators and allows for custom
    interface specifications, e.g. by preloading custom modules.
    """

    CREATORS = dict(
        universe=UniversePlotCreator,
        multiverse=MultiversePlotCreator,
    )
    """Supported creators"""

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

        self._model_info_bundle = _model_info_bundle

    @property
    def common_out_dir(self) -> str:
        """The common output directory of all plots that were created with
        this plot manager instance. This uses the plot output paths stored in
        the plot information dict, specifically the ``target_dir`` entry.

        If there was no plot information yet, the return value will be empty.
        """
        return os.path.commonprefix([d["target_dir"] for d in self.plot_info])

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

    def _get_plot_creator(self, *args, **kwargs):
        """Before actually retrieving the plot creator, pre-loads the
        model-specific plot function module. This allows to register custom
        model-specific dantro data operations and have them available prior to
        the invocation of the creator.
        """

        def preload_module(*, mod_path, model_name):
            """Helper function to carry out preloading of the module"""
            # Compile the module name
            mod_str = "model_plots." + model_name

            # Determine the parent directory from which import is possible
            model_plots_parent_dir = os.path.dirname(os.path.dirname(mod_path))

            # Now, try to import
            try:
                # Use the _tmp_sys_modules environment to prevent that a failed
                # import ends up generating a cache entry. If the import is
                # successful, a cache entry will be added (below) and further
                # importlib.import_module call will use the cached module.
                with _tmp_sys_path(model_plots_parent_dir), _tmp_sys_modules():
                    mod = importlib.import_module(mod_str)

            except Exception as exc:
                if self.raise_exc:
                    raise RuntimeError(
                        "Failed pre-loading the model-specific plot module of "
                        f"the '{model_name}' model! Make sure that "
                        f"{mod_path}/__init__.py can be loaded without "
                        "errors; to debug, inspect the chained traceback "
                        "above to find the cause of this error."
                    ) from exc
                log.debug(
                    "Pre-loading model-specific plot module from %s "
                    "failed: %s",
                    mod_path,
                    exc,
                )
                return

            else:
                log.debug("Pre-loading was successful.")

            # Add the module to the cache
            if mod_str not in sys.modules:
                sys.modules[mod_str] = mod
                log.debug("Added '%s' module to sys.modules cache.", mod_str)

        # Invoke the preloading routine
        mib = self._model_info_bundle

        if mib is not None and mib.paths.get("python_model_plots_dir"):
            mod_path = mib.paths.get("python_model_plots_dir")
            if mod_path:
                preload_module(mod_path=mod_path, model_name=mib.model_name)

        # Now get to the actual retrieval of the plot creator
        return super()._get_plot_creator(*args, **kwargs)
