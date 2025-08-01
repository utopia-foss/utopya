"""Implementation of the :py:class:`~utopya.multiverse.Multiverse` class which
sits at the heart of utopya and supplies the main user interface for the
frontend. It allows to run a simulation and then evaluate it.
"""

import copy
import glob
import itertools
import logging
import os
import random
import re
import time
import warnings
from collections import defaultdict
from shutil import copy2
from tempfile import TemporaryDirectory
from typing import Dict, List, Literal, Optional, Tuple, Union

import paramspace as psp
from dantro._import_tools import get_resource_path

from ._cluster import parse_node_list
from ._resources import SNIPPETS
from .cfg import get_cfg_path as _get_cfg_path
from .eval import DataManager, PlotManager
from .exceptions import (
    MultiverseError,
    MultiverseRunAlreadyFinished,
    SkipUniverse,
    SkipUniverseAfterSetup,
    UniverseSetupError,
)
from .model_registry import ModelInfoBundle, get_info_bundle, load_model_cfg
from .parameter import ValidationError
from .project_registry import PROJECTS
from .reporter import WorkerManagerReporter
from .tools import make_columns, parse_num_steps, pformat, recursive_update
from .workermanager import WorkerManager
from .yaml import load_yml, write_yml

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class Multiverse:
    """The Multiverse is where a single simulation run is orchestrated from.

    It spawns multiple universes, each of which represents a single simulation
    of the selected model with the parameters specified by the meta
    configuration.
    The :py:class:`~utopya.workermanager.WorkerManager` takes care to perform
    these simulations in parallel.

    The :py:class:`.Multiverse` then interfaces with the :py:mod:`dantro` data
    processing pipeline using classes specialized in :py:mod:`utopya.eval`:
    The :py:class:`~utopya.eval.datamanager.DataManager` loads the created
    simulation output, making it available in a uniformly accessible and
    hierarchical data tree.
    Then, the :py:class:`~utopya.eval.plotmanager.PlotManager` handles
    plotting of that data.
    """

    RUN_DIR_TIME_FSTR = "%y%m%d-%H%M%S"
    """The time format string for the run directory"""

    BASE_META_CFG_PATH = get_resource_path("utopya", "cfg/base_cfg.yml")
    """Where the default meta-configuration can be loaded from.
    """

    UTOPYA_BASE_PLOTS_PATH = get_resource_path("utopya", "cfg/base_plots.yml")
    """Where the utopya base plots configuration can be found; this is passed
    to the :py:class:`~utopya.eval.plotmanager.PlotManager`.
    """

    USER_CFG_SEARCH_PATH = _get_cfg_path("user")
    """Where to look for the user configuration"""

    # .........................................................................

    def __init__(
        self,
        *,
        model_name: str = None,
        info_bundle: ModelInfoBundle = None,
        run_cfg_path: str = None,
        user_cfg_path: str = None,
        _shared_worker_manager: WorkerManager = None,
        **update_meta_cfg,
    ):
        """Initialize the Multiverse.

        Args:
            model_name (str, optional): The name of the model to run
            info_bundle (ModelInfoBundle, optional): The model information
                bundle that includes information about the executable path etc.
                If not given, will attempt to read it from the model registry.
            run_cfg_path (str, optional): The path to the run configuration.
            user_cfg_path (str, optional): If given, this is used to update the
                base configuration. If None, will look for it in the default
                path, see Multiverse.USER_CFG_SEARCH_PATH.
            _shared_worker_manager (WorkerManager, optional): If given, this
                already existing WorkerManager instance (and its reporter)
                will be used instead of initializing new instances.

                .. warning::

                    This argument is only exposed for internal purposes.
                    It should not be used for production code and behavior of
                    this argument may change at any time.

            **update_meta_cfg: Can be used to update the meta configuration
                generated from the previous configuration levels
        """
        # First things first: get the info bundle
        if info_bundle is None:
            info_bundle = get_info_bundle(
                model_name=model_name, info_bundle=info_bundle
            )
        self._info_bundle = info_bundle

        log.progress(
            "Initializing Multiverse for '%s' model ...", self.model_name
        )

        # Setup property-managed attributes
        self._dirs = dict()
        self._model_executable = None
        self._tmpdir = None
        self._resolved_cluster_params = None
        self._run_tags: List[str] = ["main"]

        # Create meta configuration and list of used config files
        mcfg, cfg_parts = self._create_meta_cfg(
            run_cfg_path=run_cfg_path,
            user_cfg_path=user_cfg_path,
            update_meta_cfg=update_meta_cfg,
        )
        self._meta_cfg = mcfg
        log.info("Built meta configuration.")
        log.remark("  Debug level:  %d", self.debug_level)
        self._apply_debug_level()

        # In cluster mode, need to make some adjustments via additional dicts
        dm_cluster_kwargs = dict()
        wm_cluster_kwargs = dict()
        if self.cluster_mode:
            log.note("Cluster mode enabled.")
            self._resolved_cluster_params = self._resolve_cluster_params()
            rcps = self.resolved_cluster_params  # creates a deep copy

            log.note(
                "This is node %d of %d.",
                rcps["node_index"] + 1,
                rcps["num_nodes"],
            )

            # Changes to the meta configuration
            # To avoid config file collisions in the PlotManager:
            self._meta_cfg["plot_manager"]["cfg_exists_action"] = "skip"

            # _Additional_ arguments to pass to *Manager initializations below
            # ... for DataManager
            timestamp = rcps["timestamp"]
            dm_cluster_kwargs = dict(
                out_dir_kwargs=dict(timestamp=timestamp, exist_ok=True)
            )

            # ... for WorkerManager
            wm_cluster_kwargs = dict(
                cluster_mode=True, resolved_cluster_params=rcps
            )

        # Create the run directory and write the meta configuration into it.
        self._create_run_dir(**self.meta_cfg["paths"])
        log.note("Run directory:\n  %s", self.dirs["run"])

        # Backup involved files, if not in cluster mode or on the relevant node
        if (
            not self.cluster_mode
            or self.resolved_cluster_params["node_index"] == 0
        ):
            # If not in cluster mode, should backup in any case.
            # In cluster mode, the first node is responsible for backing up
            # the configuration; all others can relax.
            self._perform_backup(
                **self.meta_cfg["backups"], cfg_parts=cfg_parts
            )

        else:
            log.debug(
                "Not backing up config files, because it was already "
                "taken care of by the first node."
            )
            # NOTE Not taking a try-except approach here because it might get
            #      messy when multiple nodes try to backup the configuration
            #      at the same time ...

        # Validate the parameters specified in the meta configuration
        self._validate_meta_cfg()

        # Prepare the executable
        self._prepare_executable(**self.meta_cfg["executable_control"])

        # Create a DataManager instance
        self._dm = DataManager(
            self.dirs["run"],
            name=f"{self.model_name}_data",
            **self.meta_cfg["data_manager"],
            **dm_cluster_kwargs,
        )
        log.progress("Initialized DataManager.")

        # Either create a WorkerManager instance and its associated reporter
        # or use an already existing WorkerManager that is also used elsewhere
        if not _shared_worker_manager:
            self._wm = WorkerManager(
                **self.meta_cfg["worker_manager"], **wm_cluster_kwargs
            )
            self._reporter = WorkerManagerReporter(
                self.wm,
                mv=self,
                report_dir=self.dirs["run"],
                **self.meta_cfg["reporter"],
            )
        else:
            self._wm = _shared_worker_manager
            self._reporter = self.wm.reporter
            log.info("Using a shared WorkerManager instance and reporter.")

        # And instantiate the PlotManager with the model-specific plot config
        self._pm = self._setup_pm()

        log.progress("Initialized Multiverse.\n")

    # Properties ..............................................................

    @property
    def debug_level(self) -> int:
        """The debug level"""
        return self.meta_cfg.get("debug_level", 0)

    @property
    def info_bundle(self) -> ModelInfoBundle:
        """The model info bundle for this Multiverse"""
        return self._info_bundle

    @property
    def model_name(self) -> str:
        """The model name associated with this Multiverse"""
        return self.info_bundle.model_name

    @property
    def model_executable(self) -> str:
        """The path to the model executable"""
        if self._model_executable is not None:
            # Use the executable from a temporary directory
            return self._model_executable

        execpath = self.info_bundle.executable
        if not execpath:
            raise ValueError(
                f"Model '{self.model_name}' does not have an executable "
                "registered that can be used to perform a simulation run!\n"
                "If you want to run simulations, specify an executable. "
                "In case you only want to use utopya's evaluation routines, "
                "no executable is needed, but only the evaluation pipeline is "
                "available and it seems like you tried to run a simulation."
            )

        return execpath

    @property
    def model(self) -> "utopya.model.Model":
        """A model instance, created ad-hoc using the associated info bundle"""
        from .model import Model

        return Model(info_bundle=self.info_bundle)

    @property
    def meta_cfg(self) -> dict:
        """The meta configuration."""
        return self._meta_cfg

    @property
    def dirs(self) -> dict:
        """Information on managed directories."""
        return self._dirs

    @property
    def status_file_paths(self) -> List[str]:
        """Retrieves status file paths in this Multiverse's run directory"""
        return get_status_file_paths(self.dirs["run"])

    @property
    def cluster_mode(self) -> bool:
        """Whether the Multiverse should run in cluster mode"""
        return self.meta_cfg["cluster_mode"]

    @property
    def cluster_params(self) -> dict:
        """Returns a copy of the cluster mode configuration parameters"""
        return copy.deepcopy(self.meta_cfg["cluster_params"])

    @property
    def resolved_cluster_params(self) -> dict:
        """Returns a copy of the cluster configuration with all parameters
        resolved. This makes some additional keys available on the top level.
        """
        # Return the cached value as a _copy_ to secure it against changes
        return copy.deepcopy(self._resolved_cluster_params)

    @property
    def skipping(self) -> dict:
        """The skipping control parameters"""
        return self.meta_cfg["skipping"]

    @property
    def dm(self) -> DataManager:
        """The Multiverse's DataManager."""
        return self._dm

    @property
    def wm(self) -> WorkerManager:
        """The Multiverse's WorkerManager."""
        return self._wm

    @property
    def pm(self) -> PlotManager:
        """The Multiverse's PlotManager."""
        return self._pm

    # Public methods ..........................................................

    def run(self, *, sweep: bool = None):
        """Starts a simulation run.

        Specifically, this method adds simulation tasks to the associated
        WorkerManager, locks its task list, and then invokes the
        :py:meth:`~utopya.workermanager.WorkerManager.start_working` method
        which performs all the simulation tasks.

        If cluster mode is enabled, this will split up the parameter space into
        (ideally) equally sized parts and only run one of these parts,
        depending on the cluster node this Multiverse is being invoked on.

        .. note::

            As this method locks the task list of the
            :py:class:`~utopya.workermanager.WorkerManager`, no further tasks
            can be added henceforth. This means, that each Multiverse instance
            can only perform a single simulation run.

        Args:
            sweep (bool, optional): Whether to perform a sweep or not. If None,
                the value will be read from the ``perform_sweep`` key of the
                meta-configuration.
        """
        log.hilight("Preparing for simulation run ...")
        self._add_sim_tasks(sweep=sweep)
        self._start_working(**self.meta_cfg["run_kwargs"])

    def run_single(self):
        """Runs a single simulation using the parameter space's default value.

        See :py:meth:`~utopya.multiverse.Multiverse.run` for more information.
        """
        return self.run(sweep=False)

    def run_sweep(self):
        """Runs a parameter sweep.

        See :py:meth:`~utopya.multiverse.Multiverse.run` for more information.
        """
        return self.run(sweep=True)

    def renew_plot_manager(self, **update_kwargs):
        """Tries to set up a new PlotManager. If this succeeds, the old one is
        discarded and the new one is associated with this Multiverse.

        Args:
            **update_kwargs: Passed on to PlotManager.__init__
        """
        try:
            pm = self._setup_pm(**update_kwargs)

        except Exception as exc:
            raise ValueError(
                "Failed setting up a new PlotManager! "
                "The old PlotManager remains."
            ) from exc

        self._pm = pm

    # Helpers .................................................................

    @classmethod
    def _load_user_cfg(cls, user_cfg_path: str = None) -> Tuple[str, dict]:
        """Loads the user configuration from a path; if no path is given,
        searches for it ..."""
        if user_cfg_path is None:
            log.debug(
                "Looking for user configuration file in default location, %s",
                cls.USER_CFG_SEARCH_PATH,
            )

            if os.path.isfile(cls.USER_CFG_SEARCH_PATH):
                user_cfg_path = cls.USER_CFG_SEARCH_PATH
            else:
                # No user cfg will be loaded
                log.debug("No file found at the default search location.")

        elif user_cfg_path is False:
            log.remark("Ignoring default user configuration.")

        user_cfg = None
        if user_cfg_path:
            user_cfg = load_yml(user_cfg_path)

        return user_cfg_path, user_cfg

    @classmethod
    def _load_meta_cfg_parts(
        cls, *, info_bundle: ModelInfoBundle, user_cfg_path: str = None
    ) -> Tuple[Dict[str, Optional[str]], Dict[str, Optional[dict]]]:
        """Loads the various parts of the meta-configuration for a model and
        returns a dict of their paths and one of the loaded dictionaries."""
        # Read in the base meta configuration
        base_cfg_path = cls.BASE_META_CFG_PATH
        base_cfg = load_yml(base_cfg_path)

        # Framework- and project-level configuration files
        framework_cfg_path = None
        framework_cfg = {}

        project_cfg_path = None
        project_cfg = {}

        model_mv_cfg_path = None
        model_mv_cfg = {}

        project_name = info_bundle.project_name
        if project_name:
            project = info_bundle.project

            # Framework-level
            framework_name = project.get("framework_name")
            if framework_name:
                framework_project = PROJECTS[framework_name]
                framework_cfg_path = framework_project["paths"].get(
                    "mv_project_cfg"
                )

                if framework_cfg_path:
                    framework_cfg = load_yml(framework_cfg_path)

            # Project level
            if project_name != framework_name:
                project_cfg_path = info_bundle.project["paths"].get(
                    "mv_project_cfg"
                )

                if project_cfg_path:
                    project_cfg = load_yml(project_cfg_path)

        # There might be a model-specific configuration
        if model_mv_cfg_path := info_bundle.paths.get("mv_model_cfg"):
            model_mv_cfg = load_yml(model_mv_cfg_path)

        # Decide whether to read in the user configuration from the default
        # search location or use a user-passed one
        user_cfg_path, user_cfg = cls._load_user_cfg(user_cfg_path)

        # Assemble into two dicts
        cfg_paths = dict(
            base=base_cfg_path,
            framework=framework_cfg_path,
            project=project_cfg_path,
            model_mv=model_mv_cfg_path,
            user=user_cfg_path,
        )
        cfgs = dict(
            base=base_cfg,
            framework=framework_cfg,
            project=project_cfg,
            model_mv=model_mv_cfg,
            user=user_cfg,
        )

        return cfg_paths, cfgs

    @classmethod
    def _assemble_meta_cfg_base_layers(
        cls, *, info_bundle: ModelInfoBundle, user_cfg_path: str = None
    ) -> Tuple[dict, Dict[str, str], Dict[str, dict]]:
        """Assembles the meta-configuration base layers, i.e. *without* the
        model default configuration or any *run-specific* updates.

        It includes the following layers:

            - ``base``
            - ``framework``
            - ``project``
            - ``model_mv`` (model-specific multiverse updates)
            - ``user``

        Other layers are applied later.

        Returns a 3-tuple of (assembled meta config, cfg paths, cfg dicts).
        """
        # Load the base layers
        cfg_paths, cfgs = cls._load_meta_cfg_parts(
            info_bundle=info_bundle, user_cfg_path=user_cfg_path
        )

        # Now perform the recursive update steps, starting with the base.
        meta_tmp = dict()
        for cfg_name in ("base", "framework", "project", "model_mv", "user"):
            cfg = cfgs[cfg_name]
            if cfg:
                log.debug("Updating with %s configuration ...", cfg_name)
                meta_tmp = recursive_update(meta_tmp, cfg)

        return meta_tmp, cfg_paths, cfgs

    def _create_meta_cfg(
        self, *, run_cfg_path: str, user_cfg_path: str, update_meta_cfg: dict
    ) -> dict:
        """Create the meta configuration from several parts and store it.

        The final configuration dict is built from multiple components,
        where one is always recursively updating the previous level.
        The resulting configuration is the meta configuration and is stored
        to the ``meta_cfg`` attribute.

        The parts are recorded in the ``cfg_parts`` dict and returned such that
        a backup can be created.

        Args:
            run_cfg_path (str): path to the run configuration
            user_cfg_path (str): path to the user configuration file
            update_meta_cfg (dict): will be used to update the resulting dict

        Returns:
            dict: dict of the parts that were needed to create the meta config.
                The dict-key corresponds to the part name, the value is the
                payload which can be either a path to a cfg file or a dict
        """
        log.info("Building meta-configuration ...")

        # Load the base layers
        meta_tmp, cfg_paths, cfgs = self._assemble_meta_cfg_base_layers(
            info_bundle=self.info_bundle, user_cfg_path=user_cfg_path
        )

        # Read in the configuration corresponding to the chosen model
        (model_cfg, model_cfg_path, params_to_validate) = load_model_cfg(
            info_bundle=self.info_bundle
        )
        cfg_paths["model"] = model_cfg_path
        cfgs["model"] = model_cfg
        # NOTE Unlike the other configuration files, this does not attach at
        # root level of the meta configuration but parameter_space.<model_name>
        # in order to allow it to be used as the default configuration for an
        # _instance_ of that model.

        # Read in the run configuration
        run_cfg = None
        if run_cfg_path:
            log.note("Run configuration:\n  %s", run_cfg_path)
            try:
                run_cfg = load_yml(run_cfg_path)
            except FileNotFoundError as err:
                raise FileNotFoundError(
                    f"No run config could be found at {run_cfg_path}!"
                ) from err

            # Make sure its parameter_space entry is a true dict and not a
            # ParamSpace object, which needs to be resolved to a dict.
            if isinstance(run_cfg.get("parameter_space"), psp.ParamSpace):
                run_cfg["parameter_space"] = run_cfg["parameter_space"]._dict
                # FIXME Should not be using the private interface here. This is
                #       only necessary in the first place because ParamSpace
                #       does not behave like a dict as much as it should...
                #       Once recursive_update works within ParamSpace, this
                #       can be removed again.

        else:
            log.note(
                "Using default model configuration for run:\n  %s\n",
                model_cfg_path,
            )

        cfg_paths["run"] = run_cfg_path
        cfgs["run"] = run_cfg

        # In order to incorporate the model config, the parameter space is
        # needed. We can already be sure that the parameter_space key exists,
        # because it is added as part of the base_cfg.
        pspace = meta_tmp["parameter_space"]

        # Adjust parameter space to include model configuration at a specified
        # key; also communicate that key explicitly.
        log.debug(
            "Updating parameter space with default model configuration for "
            "model '%s' ...",
            self.model_name,
        )
        pspace[self.model_name] = recursive_update(
            pspace.get(self.model_name, {}), model_cfg
        )
        pspace["root_model_name"] = self.model_name
        # NOTE this works because meta_tmp is a dict and thus mutable :)

        # On top of all of that: add the run configuration, if given
        if run_cfg:
            log.debug("Updating with run configuration ...")
            meta_tmp = recursive_update(meta_tmp, run_cfg)

        # ... and the update_meta_cfg dictionary
        if update_meta_cfg:
            log.debug("Updating with given `update_meta_cfg` dictionary ...")
            meta_tmp = recursive_update(
                meta_tmp, copy.deepcopy(update_meta_cfg)
            )
            # NOTE using deep copy to make sure that usage of the dict
            #      elsewhere will not interfere with the Multiverse

        # Make `parameter_space` a ParamSpace object
        pspace = meta_tmp["parameter_space"]
        meta_tmp["parameter_space"] = psp.ParamSpace(pspace)
        log.debug("Converted parameter_space to ParamSpace object.")

        # Add the parameters that require validation
        meta_tmp["parameters_to_validate"] = params_to_validate
        log.debug(
            "Added %d parameters requiring validation.",
            len(params_to_validate),
        )

        # Prepare dict to store paths for config files in (for later backup)
        cfg_parts: Dict[str, Union[dict, str, None]] = dict()
        cfg_parts.update(cfg_paths)
        cfg_parts["model"] = model_cfg_path
        cfg_parts["run"] = run_cfg_path
        cfg_parts["update"] = update_meta_cfg

        return meta_tmp, cfg_parts

    def _apply_debug_level(self, lvl: int = None):
        """Depending on the debug level, applies certain settings to the
        Multiverse and the runtime environment.

        .. note::

            This does *not* (yet) set the corresponding debug flags for the
            ``PlotManager``, ``DataManager``, or ``WorkerManager``!
        """
        lvl = lvl if lvl is not None else self.debug_level

        if lvl >= 2:
            warnings.simplefilter("always", DeprecationWarning)

    def _create_run_dir(
        self,
        *,
        out_dir: str,
        model_note: str = None,
        dir_permissions: dict = None,
    ) -> None:
        """Create the folder structure for the run output.

        For the chosen model name and current timestamp, the run directory
        will be of form <timestamp>_<model_note> and be part of the following
        directory tree:

        ::

            utopya_output
                model_a
                    180301-125410_my_model_note
                        config
                        data
                            uni000
                            uni001
                            ...
                        eval
                model_b
                    180301-125412_my_first_sim
                    180301-125413_my_second_sim

        If running in cluster mode, the cluster parameters are resolved and
        used to determine the name of the simulation. The pattern then does not
        include a timestamp as each node might return not quite the same value.
        Instead, a value from an environment variable is used.
        The resulting path can have different forms, depending on which
        environment variables were present; required parts are denoted by a
        ``*`` in the following pattern; if the value of the other entries is
        not available, the connecting underscore will not be used:

        ::

            {timestamp}_{job id*}_{cluster}_{job account}_{job name}_{note}

        Args:
            out_dir (str): The base output directory, where all Utopia output
                is stored.
            model_note (str, optional): The note to add to the run directory
                of the current run.
            dir_permissions (Dict[str, str]): If given, will set directory
                permissions on the specified managed directories of this
                Multiverse. The keys of this dict should be entries of the
                :py:attr:`.dirs` attribute, values should be octal permissions
                values given as a string.

        Raises:
            RuntimeError: If the simulation directory already existed. This
                should not occur, as the timestamp is unique. If it occurs,
                you either started two simulations very close to each other or
                something is seriously wrong. Strange time zone perhaps?
        """
        # Define a list of format string parts, starting with timestamp
        fstr_parts = ["{timestamp:}"]

        # Add respective information, depending on mode
        if not self.cluster_mode:
            # Available information is only the timestamp and the model note
            fstr_kwargs = dict(
                timestamp=time.strftime(self.RUN_DIR_TIME_FSTR),
                model_note=model_note,
            )

        else:
            # In cluster mode, need to resolve cluster parameters first
            rcps = self.resolved_cluster_params

            # Now, gather all information for the format string that will
            # determine the name of the output directory. Make all the info
            # available that was supplied from environment variables
            fstr_kwargs = {
                k: v for k, v in rcps.items() if k not in ("custom_out_dir",)
            }

            # Parse timestamp and model note separately
            timestr = time.strftime(
                self.RUN_DIR_TIME_FSTR, time.gmtime(rcps["timestamp"])
            )
            fstr_kwargs["timestamp"] = timestr  # overwrites existing
            fstr_kwargs["model_note"] = model_note  # may be None

            # Add the additional run dir format string parts; its the user's
            # responsibility to supply something reasonable here.
            if self.cluster_params.get("additional_run_dir_fstrs"):
                fstr_parts += self.cluster_params["additional_run_dir_fstrs"]

            # Now, also allow a custom output directory
            if rcps.get("custom_out_dir"):
                out_dir = rcps["custom_out_dir"]

        # Have the model note as suffix
        if model_note:
            fstr_parts += ["{model_note:}"]

        # fstr_parts and fstr_kwargs ready now. Carry out the format operation.
        fstr = "_".join(fstr_parts)
        run_dir_name = fstr.format(**fstr_kwargs)
        log.debug("Determined run directory name:  %s", run_dir_name)

        # Parse the output directory, then build the run directory path
        log.debug("Creating path for run directory inside %s ...", out_dir)
        out_dir = os.path.expanduser(str(out_dir))

        run_dir = os.path.join(out_dir, self.model_name, run_dir_name)
        log.debug("Built run directory path:  %s", run_dir)
        self.dirs["run"] = run_dir

        # ... and create it. In cluster mode, it may already exist.
        try:
            os.makedirs(run_dir, exist_ok=self.cluster_mode)

        except OSError as err:
            raise RuntimeError(
                "Simulation directory already exists. This "
                "should not have happened and is probably due "
                "to two simulations having been started at "
                "almost the same time. Try to start the "
                "simulation again or add a unique model note."
            ) from err

        log.debug("Created run directory.")

        # Create the subfolders that are always assumed to be present
        for subdir in ("config", "data", "eval"):
            subdir_path = os.path.join(run_dir, subdir)
            os.makedirs(subdir_path, exist_ok=self.cluster_mode)
            self.dirs[subdir] = subdir_path

        log.debug("Created subdirectories:  %s", self._dirs)

        # May want to adapt directory permissions
        if not dir_permissions:
            return

        for dirname, mode in dir_permissions.items():
            if mode is None:
                continue
            mode = int(str(mode), 8)
            log.debug(
                "Setting permissions on %s directory to %s ...",
                dirname,
                oct(mode),
            )
            os.chmod(self.dirs[dirname], mode)

    def _get_run_dir(
        self, *, out_dir: Optional[str], run_dir: Optional[str], **__
    ):
        """Helper function to find the run directory from arguments given
        to :py:meth:`~utopya.multiverse.Multiverse.__init__`.
        This is not actually used in :py:class:`~utopya.multiverse.Multiverse`
        but in :py:class:`~utopya.multiverse.FrozenMultiverse` and
        :py:class:`~utopya.multiverse.DistributedMultiverse`.

        Args:
            out_dir (str): The Model output directory. If unknown (None), will
                try to deduce it from an absolute run directory path or from
                the info bundle.
            run_dir (str): The run directory to use; if not known will try to
                find the latest run directory.
            ``**__``: ignored

        Raises:
            IOError: No directory found to use as run directory
            TypeError: When run_dir was not a string
        """
        # The timestamp pattern to match against. Note that the timestamp
        # absolutely NEEDS to be there, while the appended note is optional.
        PATTERN = r"\d{6}-\d{6}_?.*"

        # May need to deduce the output directory
        if out_dir is None:
            if run_dir and os.path.isabs(run_dir):
                out_dir = os.path.abspath(os.path.join(run_dir, ".."))
            else:
                # Need to make a good guess which directory is meant. The best
                # we can do at this point (without the actual meta-config) is
                # to guess the output directory, which is defined in the
                # assembled meta-configuration. This will be correct _unless_
                # a different directory was specified in the run config (in
                # which case a user should not expect that we can magically
                # find that directory...)
                incompl_meta_cfg, *_ = self._assemble_meta_cfg_base_layers(
                    info_bundle=self._info_bundle
                )
                out_dir = incompl_meta_cfg["paths"]["out_dir"]

        # Create model directory path (where the to-be-loaded data is expected)
        out_dir = os.path.expanduser(str(out_dir))
        model_dir = os.path.join(out_dir, self.model_name)

        log.note("Assumed model output directory:\n  %s", model_dir)

        if not os.path.isdir(model_dir):
            # Just create it, there's no harm in that ...
            os.makedirs(model_dir)

        # Distinguish different types of values for the run_dir argument
        if run_dir is None:
            log.info("Trying to identify the most recent run directory ...")

            # Create list of _directories_ matching timestamp pattern
            dirs = [
                d
                for d in sorted(os.listdir(model_dir))
                if os.path.isdir(os.path.join(model_dir, d))
                and re.match(PATTERN, os.path.basename(d))
            ]

            if not dirs:
                raise FileNotFoundError(
                    "Could not find a run directory to load for evaluation "
                    f"of model '{self.model_name}'!\n"
                    f"Model output directory:  {model_dir}\n\n"
                    "Did you perform a simulation yet? If you are using this "
                    "model only for evaluation, place your data in a new "
                    "subdirectory in that folder (using timestamp as name)."
                )

            # Use the latest to choose the run directory
            run_dir = os.path.join(model_dir, dirs[-1])

        elif isinstance(run_dir, str):
            run_dir = os.path.expanduser(run_dir)

            # Distinguish absolute and relative paths and those starting with
            # a timestamp-like pattern, which can be looked up from the model
            # directory.
            if os.path.isabs(run_dir):
                log.debug("Received absolute run_dir, using that one.")

            elif re.match(PATTERN, run_dir):
                # Looks like a relative path within the model directory, which
                # may be incomplete
                log.info(
                    "Received timestamp '%s' for run_dir; trying to find "
                    "one within the model output directory ...",
                    run_dir,
                )
                # Check if it's already complete, i.e. if such a directory
                # exists. If not: check against all that start with the same
                # timestamp; this is sufficient because the PATTERN ensures
                # that the given run_dir starts with the timestamp.
                _run_dir = os.path.join(model_dir, run_dir)
                if os.path.isdir(_run_dir):
                    run_dir = _run_dir
                else:
                    _run_dirs = [
                        d
                        for d in sorted(os.listdir(model_dir))
                        if os.path.isdir(os.path.join(model_dir, d))
                        and d.startswith(run_dir)
                    ]
                    if len(_run_dirs) != 1:
                        raise ValueError(
                            f"Got partial run directory name '{run_dir}' that "
                            "does not uniquely match one and only one run "
                            f"directory! It matched {len(_run_dirs)} "
                            f"subdirectories of  {model_dir}  :\n"
                            f"  {',  '.join(_run_dirs)}"
                        )
                    run_dir = os.path.join(model_dir, _run_dirs[0])

            else:
                # Is not an absolute path and not a timestamp; assume it is
                # a path relative to the current working directory that does
                # not conform with the expected pattern but may still be valid
                run_dir = os.path.join(os.getcwd(), run_dir)

        else:
            raise TypeError(
                "Argument run_dir needs to be None, an absolute "
                "path, or a path relative to the model output "
                f"directory, but it was: {run_dir}"
            )

        # Check if the directory exists
        if not os.path.isdir(run_dir):
            raise OSError(f"No run directory found at '{run_dir}'!")

        # Store the path and associate the subdirectories
        self.dirs["run"] = run_dir

        for subdir in ("config", "eval", "data"):
            subdir_path = os.path.join(run_dir, subdir)
            if not os.path.exists(subdir_path):
                raise FileNotFoundError(
                    f"Missing '{subdir}' subdirectory inside "
                    f"run directory {run_dir}!"
                )
            self.dirs[subdir] = subdir_path

        return run_dir

    def _setup_pm(self, **update_kwargs) -> PlotManager:
        """Helper function to setup a PlotManager instance"""
        pm_kwargs = copy.deepcopy(self.meta_cfg["plot_manager"])

        if update_kwargs:
            pm_kwargs = recursive_update(pm_kwargs, update_kwargs)

        base_cfg_pools = pm_kwargs.pop(
            "base_cfg_pools", ["utopya_base", "model_base"]
        )

        log.info("Initializing PlotManager ...")
        pm = PlotManager(
            dm=self.dm,
            _model_info_bundle=self.info_bundle,
            default_plots_cfg=self.info_bundle.paths.get("default_plots"),
            base_cfg_pools=self._parse_base_cfg_pools(base_cfg_pools),
            **pm_kwargs,
        )

        log.progress("Initialized PlotManager.")
        log.note(
            "Available base plot configuration pools:\n  %s",
            ", ".join(pm.base_cfg_pools.keys()),
        )
        log.note(
            "Output directory:  %s",
            pm._out_dir if pm._out_dir else "\n  " + self.dm.dirs["out"],
        )

        return pm

    def _parse_base_cfg_pools(
        self, base_cfg_pools: List[Union[str, Tuple[str, Union[str, dict]]]]
    ) -> List[Tuple[str, Union[str, dict]]]:
        """Prepares the ``base_cfg_pools`` argument to be valid input to the
        PlotManager. This method resolves format strings and thus allows to
        more generically define base config pools.

        Possible formats for each entry of ``base_cfg_pools`` argument are:

            - A 2-tuple ``(name, pool dict)`` which specifies the name of the
              base config pool alongside with the pool entries.
            - A 2-tuple ``(name, path to pool config file)``, which is later
              loaded by the PlotManager
            - A shortcut key which resolves to the corresponding 2-tuple.
              Available shortcuts are:  ``utopya_base``, ``framework_base``,
              ``project_base``, and ``model_base``.

        Both the pool name and path may be format strings which get resolved
        with the ``model_name`` key and (in the case of the path) the full
        ``paths`` dict of the current model's info bundle. A format string may
        look like this:

            "{paths[source_dir]}/{model_name}_more_plots.yml"
            "~/some/more/plots/{model_name}/plots.yml"

        If such a path cannot be resolved, an error is logged and an empty pool
        is used instead; this allows for more flexibility in defining locations
        for additional config pools.

        Args:
            base_cfg_pools (List[Union[str, Tuple[str, Union[str, dict]]]]):
                The unparsed specification of config pools.
        """

        def parse_entry(
            entry: Union[str, list, tuple], replacements: dict
        ) -> Tuple[str, Union[str, dict]]:
            """Unpacks an entry into (name, pool) format and resolves any
            remaining format specifiers in the name or pool path.
            """
            if isinstance(entry, str):
                try:
                    pool_name, pool = replacements[entry]
                except KeyError as err:
                    _avail = ", ".join(replacements)
                    raise ValueError(
                        f"Invalid base config pool shortcut key '{entry}'! "
                        f"Available shortcuts are: {_avail}. "
                        "Use one of those or specify the config pool as a "
                        "2-tuple in form (name, path to pool)."
                    ) from err
            else:
                pool_name, pool = entry

            # Parse pool name and the path to the pool config file
            pool_name = pool_name.format(model_name=self.model_name)
            if isinstance(pool, str):
                pool = pool.format(model_name=self.model_name, paths=paths)
                pool = os.path.abspath(os.path.expanduser(pool))
                if not os.path.isfile(pool):
                    log.error(
                        "No base plot config pool file found at:\n  %s", pool
                    )
                    log.caution("Using an empty pool instead.")
                    pool = {}

            # Make sure it is either a dict or a string, not a Path-like object
            if not isinstance(pool, dict):
                pool = str(pool)

            return pool_name, pool

        if not isinstance(base_cfg_pools, list):
            raise TypeError(
                "Base config pools need to be specified as a list of "
                f"2-tuples or strings, got {type(base_cfg_pools)}!"
            )

        paths = self.info_bundle.paths
        replacements = dict(
            utopya_base=("utopya", self.UTOPYA_BASE_PLOTS_PATH),
            framework_base=("framework", {}),
            project_base=("project", {}),
            model_base=("{model_name:}_base", paths.get("base_plots", {})),
        )

        project = self.info_bundle.project
        if project:
            fw_name = project.get("framework_name")
            if fw_name:
                fw_project = PROJECTS[fw_name]
                replacements["framework_base"] = (
                    "framework",
                    fw_project["paths"].get("project_base_plots"),
                )

            # Only add a project-level replacement if it is different from the
            # framework-level replacement
            if self.info_bundle.project_name != fw_name and project[
                "paths"
            ].get("project_base_plots"):
                replacements["project_base"] = (
                    "project",
                    project["paths"].get("project_base_plots"),
                )

        return [parse_entry(p, replacements) for p in base_cfg_pools]

    def _perform_backup(
        self,
        *,
        cfg_parts: dict,
        backup_cfg_files: bool = True,
        backup_executable: bool = False,
        include_git_info: bool = True,
    ) -> None:
        """Performs a backup of that information that can be used to recreate a
        simulation.

        The configuration files are backed up into the ``config`` subdirectory
        of the run directory. All other relevant information is stored in an
        additionally created ``backup`` subdirectory.

        .. warning::

            These backups are created prior to the start of the actual
            simulation run and contains information known at that point.
            Any changes to the meta configuration made *after* initialization
            of the Multiverse will not be reflected in these backups.

            In particular, the ``perform_sweep`` and ``parameter_space``
            entries of the meta configuration may not reflect which form of
            parameter space iteration was actually performed, because the
            ``run_single`` and ``run_sweep`` methods overwrite this behavior.
            To that end, that information is separately stored once the ``run``
            methods are invoked.

        Args:
            cfg_parts (dict): A dict of either paths to configuration files or
                dict-like data that is to be dumped into a configuration file.
            backup_cfg_files (bool, optional): Whether to backup the individual
                configuration files (i.e. the ``cfg_parts`` information). If
                false, the meta configuration will still be backed up.
            backup_executable (bool, optional): Whether to backup the
                executable. Note that these files can sometimes be quite large.
            include_git_info (bool, optional): If True, will store information
                about the state of the project's (and framework's, if existent)
                git repository.
        """
        log.info("Performing backups ...")
        cfg_dir = self.dirs["config"]

        # Write the meta config to the config directory.
        write_yml(self.meta_cfg, path=os.path.join(cfg_dir, "meta_cfg.yml"))
        log.note("  Backed up meta configuration.")

        # Store the *full* parameter space and its metadata
        # NOTE This data may not be equivalent to the parameter space that is
        #      used for a simulation run; another backup is performed when
        #      adding the corresponding simulation tasks.
        _pspace_info = dict(perform_sweep=self.meta_cfg.get("perform_sweep"))
        self._perform_pspace_backup(
            self.meta_cfg["parameter_space"],
            filename="full_parameter_space",
            **_pspace_info,
        )

        # If configured, backup the other cfg files one by one.
        if backup_cfg_files:
            log.debug(
                "Backing up %d involved configuration parts...", len(cfg_parts)
            )

            for part_name, val in cfg_parts.items():
                _path = os.path.join(cfg_dir, part_name + "_cfg.yml")

                # Distinguish two types of payload that will be saved:
                if isinstance(val, str):
                    # Assumed to be path to a config file; copy it
                    log.debug("Copying %s config ...", part_name)
                    copy2(val, _path)

                elif isinstance(val, dict):
                    log.debug("Dumping %s config dict ...", part_name)
                    write_yml(val, path=_path)

            log.note("  Backed up all involved configuration files.")

        # If enabled, back up the executable as well
        if backup_executable:
            backup_dir = os.path.join(self.dirs["run"], "backup")
            os.makedirs(backup_dir, exist_ok=True)

            copy2(
                self.model_executable,
                os.path.join(backup_dir, self.model_name),
            )
            log.note("  Backed up executable.")

        # If enabled, store git repository information
        if include_git_info:
            prj = self.info_bundle.project
            if prj is not None:
                prj_info = prj.get_git_info(include_patch_info=True)

                patch = prj_info.pop("git_diff")
                _patch_path = os.path.join(cfg_dir, "git_diff_project.patch")
                prj_info["git_diff"] = _patch_path

                # write info
                _path = os.path.join(cfg_dir, "git_info_project.yml")
                write_yml(prj_info, path=_path)

                # write patch file
                with open(_patch_path, "w") as f:
                    f.write(patch)

                log.note("  Stored project's git info and patch.")

                fw = prj.framework_project
                if fw is not None:
                    fw_info = fw.get_git_info(include_patch_info=True)

                    patch = fw_info.pop("git_diff")
                    _patch_path = os.path.join(
                        cfg_dir, "git_diff_framework.patch"
                    )
                    fw_info["git_diff"] = _patch_path

                    # write info
                    _path = os.path.join(cfg_dir, "git_info_framework.yml")
                    write_yml(fw_info, path=_path)

                    # write patch file
                    with open(_patch_path, "w") as f:
                        f.write(patch)

                    log.note("  Stored framework's git info and patch.")

    def _perform_pspace_backup(
        self,
        pspace: psp.ParamSpace,
        *,
        filename: str = "parameter_space",
        **info_kwargs,
    ):
        """Stores the given parameter space and its metadata into the
        ``config`` directory.
        Two files will be produced:

            - ``config/{filename}.yml``: the passed ``pspace`` object
            - ``config/{filename}_info.yml``: the passed ``pspace`` object's
                info dictionary containing relevant metadata (and the
                additionally passed ``info_kwargs``)

        .. note::

            This method is separated from the regular backup method
            :py:meth:`Multiverse._perform_backup` because the
            parameter space that is *used* during a simulation run may be a
            lower-dimensional version of the one the Multiverse was
            initialized with.
            To that end, :py:meth:`.run` will invoke this backup function
            again once the relevant information is fully determined. This is
            important because it is needed to communicate the correct
            information about the sweep to objects downstream in the pipeline
            (e.g. :py:class:`~utopya.eval.plotcreators.MultiversePlotCreator`).

        Args:
            pspace (paramspace.paramspace.ParamSpace): The ParamSpace object
                to save as backup.
            filename (str, optional): The filename (without extension!) to use.
                (This is also used for the log message, with underscores
                changed to spaces.)
            **info_kwargs: Additional kwargs that are to be stored in the meta-
                data dict.
        """
        cfg_dir = self.dirs["config"]
        write_yml(pspace, path=os.path.join(cfg_dir, f"{filename}.yml"))
        write_yml(
            dict(**pspace.get_info_dict(), **info_kwargs),
            path=os.path.join(cfg_dir, f"{filename}_info.yml"),
        )
        log.note("  Backed up %s and metadata.", filename.replace("_", " "))

    def _prepare_executable(self, *, run_from_tmpdir: bool = False) -> None:
        """Prepares the model executable, potentially copying it to a temporary
        location.

        Note that ``run_from_tmpdir`` requires the executable to be relocatable
        to another location, i.e. be position-independent.

        Args:
            run_from_tmpdir (bool, optional): Whether to copy the executable
                to a temporary directory that goes out of scope once the
                Multiverse instance goes out of scope.

        Raises:
            FileNotFoundError: On missing file at model binary path
            PermissionError: On wrong access rights of file at the binary path
        """
        execpath = self.model_executable

        # Make sure it exists and is executable
        if not os.path.isfile(execpath):
            raise FileNotFoundError(
                "No file found at the specified executable "
                f"path for model '{self.model_name}'! "
                "If your model needs building, did you build it?\n"
                f"Expected file at:  {execpath}"
            )

        elif not os.access(execpath, os.X_OK):
            raise PermissionError(
                f"The specified executable path for model '{self.model_name}' "
                "does not point to an executable file. Did you set the "
                f"correct access rights?\n"
                "Use the chmod command to mark the file as executable:\n\n"
                f"  chmod +x {execpath}\n"
            )

        if run_from_tmpdir:
            self._tmpdir = TemporaryDirectory(prefix=self.model_name)
            tmp_execpath = os.path.join(
                self._tmpdir.name, os.path.basename(execpath)
            )

            log.info("Copying executable to temporary directory ...")
            log.debug("  Original:   %s", execpath)
            log.debug("  Temporary:  %s", tmp_execpath)
            copy2(execpath, tmp_execpath)
            execpath = tmp_execpath

        self._model_executable = execpath

    def _resolve_cluster_params(self) -> dict:  # TODO Outsource!
        """This resolves the cluster parameters, e.g. by setting parameters
        depending on certain environment variables. This function is called by
        the resolved_cluster_params property.

        Returns:
            dict: The resolved cluster configuration parameters

        Raises:
            ValueError: If a required environment variable was missing or empty
        """

        log.debug("Resolving cluster parameters from environment ...")

        # Get a copy of the meta configuration parameters
        cps = self.cluster_params

        # Determine the environment to use; defaults to os.environ
        env = cps.get("env") if cps.get("env") else dict(os.environ)

        # Get the mapping of environment variables to target variables
        mngr = cps["manager"]
        var_map = cps["env_var_names"][mngr]

        # Resolve the variables from the environment, requiring them to not
        # be empty
        resolved = {
            target_key: env.get(var_name)
            for target_key, var_name in var_map.items()
            if env.get(var_name)
        }

        # Check that all required keys are available
        required = ("job_id", "num_nodes", "node_list", "node_name")
        if any([var not in resolved for var in required]):
            _missing = ", ".join([k for k in required if k not in resolved])
            raise ValueError(
                f"Missing required environment variable(s):  {_missing} ! "
                "Make sure that the corresponding environment variables are "
                "set and that the mapping is correct!\n"
                f"  Mapping for manager '{mngr}':\n{pformat(var_map)}\n\n"
                f"  Full environment:\n{pformat(env)}\n\n"
            )

        # Now do some postprocessing on some of the values
        # Ensure integers
        resolved["job_id"] = int(resolved["job_id"])
        resolved["num_nodes"] = int(resolved["num_nodes"])

        if "num_procs" in resolved:
            resolved["num_procs"] = int(resolved["num_procs"])

        if "timestamp" in resolved:
            resolved["timestamp"] = int(resolved["timestamp"])

        # Ensure reproducible node list format: ordered list
        parse_mode = self.cluster_params["node_list_parser_params"][mngr]
        try:
            node_list = parse_node_list(
                resolved["node_list"], mode=parse_mode, rcps=resolved
            )
        except Exception as exc:
            raise ValueError(
                f"Failed parsing node list {resolved['node_list']} into a "
                f"uniform format using parsing mode '{parse_mode}' and "
                f"cluster manager '{mngr}'! "
                "Check the cluster mode configuration, the relevant "
                "environment variables, and the chained error message.\n"
                f"Cluster parameters:\n{pformat(self.cluster_params)}\n\n"
                f"Parameters resolved so far:\n{pformat(resolved)}"
            ) from exc

        resolved["node_list"] = node_list

        # Calculated values, needed in Multiverse.run
        # node_index: the offset in the modulo operation
        resolved["node_index"] = node_list.index(resolved["node_name"])

        # Return the resolved values
        log.debug("Resolved cluster parameters:\n%s", pformat(resolved))
        return resolved

    def _setup_universe(
        self,
        *,
        worker_kwargs: dict,
        model_name: str,
        model_executable: str,
        uni_cfg: dict,
        uni_basename: str,
    ) -> dict:
        """Setup function for individual universes. These are realised through
        individual :py:class:`~utopya.task.WorkerTask` instances, where this
        function is called as part of the setup routine, before a task is run.

        This is called before the worker process starts working on the
        universe.

        Args:
            worker_kwargs (dict): the current status of the worker_kwargs
                dictionary; is always passed to a task setup function
            model_name (str): The name of the model
            model_executable (str): path to the binary to execute
            uni_cfg (dict): the configuration to create a yml file from
                which is then needed by the model
            uni_basename (str): Basename of the universe to use for folder
                creation, i.e.: zero-padded universe number, e.g. uni0042

        Returns:
            dict: kwargs for the process to be run when task is grabbed by
                Worker.
        """

        # Generate paths
        uni_dir = os.path.join(self.dirs["data"], uni_basename)
        uni_cfg_path = os.path.join(uni_dir, "config.yml")

        # Create universe directory and configuration
        self._setup_universe_dir(uni_dir, uni_basename=uni_basename)
        uni_cfg = self._setup_universe_config(
            uni_cfg=uni_cfg, uni_dir=uni_dir, uni_cfg_path=uni_cfg_path
        )
        wk = self._setup_universe_worker_kwargs(
            model_executable=model_executable,
            uni_dir=uni_dir,
            uni_cfg_path=uni_cfg_path,
            uni_cfg=uni_cfg,
            **worker_kwargs,
        )

        # Might not want to perform work at all, in which case we mark this
        # task as to-be-skipped.
        if self.skipping["skip_after_setup"]:
            raise SkipUniverseAfterSetup(f"Skipping work on '{uni_basename}'.")

        return wk

    def _setup_universe_dir(self, uni_dir: str, *, uni_basename: str) -> None:
        """Determines the universe directory and, if needed, creates it.

        This is invoked from :py:meth:`~._setup_universe` and is carried out
        directly before work on that universe starts.

        Args:
            uni_basename (str): The basename of the universe to create the run
                directory for.
        """
        try:
            os.mkdir(uni_dir)
        except FileExistsError as err:
            self._maybe_skip("existing_uni_cfg", exc=err, desc=uni_basename)

        log.debug("Created universe directory:\n  %s", uni_dir)

    def _setup_universe_config(
        self,
        *,
        uni_cfg: dict,
        uni_dir: str,
        uni_cfg_path: str,
        mode: str = "x",
    ) -> dict:
        """Sets up the universe configuration and writes it to a file.

        This is invoked from :py:meth:`~._setup_universe` and is carried out
        directly before work on that universe starts.

        Args:
            uni_cfg (dict): The given universe configuration
            uni_dir (str): The universe directory, added to the configuration
            uni_cfg_path (str): Where to store the uni configuration at
            mode (str): File mode of the config file. Use ``w`` for overwriting
                an existing file and ``x`` for creating a new file.

        Returns:
            dict: The (potentially updated) universe configuration
        """
        # Store output directory and determine a path to the output hdf5 file
        uni_cfg["output_dir"] = uni_dir
        uni_cfg["output_path"] = os.path.join(uni_dir, "data.h5")

        # Parse the potentially string-valued number of steps values, and
        # other step-like arguments. Raises an error if they are negative.
        uni_cfg["num_steps"] = parse_num_steps(uni_cfg["num_steps"])
        uni_cfg["write_every"] = parse_num_steps(uni_cfg["write_every"])
        uni_cfg["write_start"] = parse_num_steps(uni_cfg["write_start"])

        # Write the universe config to file (by default: a _new_ file)
        try:
            write_yml(uni_cfg, path=uni_cfg_path, mode=mode)
        except FileExistsError as err:
            self._maybe_skip("existing_uni_cfg", exc=err, desc=uni_cfg_path)

        return uni_cfg

    def _setup_universe_worker_kwargs(
        self,
        *,
        model_executable: str,
        uni_cfg_path: str,
        uni_cfg: dict,
        uni_dir: str,
        save_streams: bool = False,
        **worker_kwargs,
    ) -> dict:
        """Assembles worker kwargs for a specific universe.

        This is invoked from :py:meth:`~._setup_universe` and is carried out
        directly before work on that universe starts.

        Returns:
            dict: the combined worker kwargs, including ``args`` for running
                the model executable.
        """
        # Build args tuple for task assignment; only need to pass the path
        # to the configuration file
        args = (model_executable, uni_cfg_path)

        # Assemble the worker_kwargs dict
        wk = dict(
            args=args,
            read_stdout=True,
            stdout_parser="yaml_dict",
            save_streams=save_streams,
            **worker_kwargs,
        )

        # Determine where to save the streams to, if enabled
        if save_streams:
            wk["save_streams_to"] = os.path.join(uni_dir, "{name:}.log")

        return wk

    def _maybe_skip(
        self,
        context: str,
        *,
        desc: str,
        exc: Exception = None,
    ):
        """Called from the universe setup function in certain situations, this
        method checks how to proceed. It may trigger skipping of the task,
        raise an error (e.g. if skipping is disabled), or just continue without
        either of those, potentially causing an error later."""
        skipping = self.skipping

        # Retrieve the desired action for the specified context
        try:
            ctx_action = skipping[f"on_{context}"]
        except KeyError as err:
            raise ValueError(
                f"Missing argument for skipping context '{context}'!\n"
                f"Skipping parameters were:  {skipping}"
            ) from err

        # Evaluate
        if ctx_action == "raise" or not skipping["enabled"]:
            if exc:
                raise UniverseSetupError(f"{context}: {desc}") from exc
            raise UniverseSetupError(f"{context}: {desc}")

        elif ctx_action == "skip":
            raise SkipUniverse(f"{context}: {desc}")

        elif ctx_action == "continue":
            pass

        else:
            raise ValueError(
                f"Invalid argument '{ctx_action}' for skipping context "
                f"'{context}'! Choose from:  skip, raise, continue"
            )

    def _add_sim_task(
        self, *, uni_id_str: str, uni_cfg: dict, is_sweep: bool
    ) -> None:
        """Helper function that handles task assignment to the WorkerManager.

        This function creates a WorkerTask that will perform the following
        actions **once it is grabbed and worked at**:

          - Create a universe (folder) for the task (simulation)
          - Write that universe's configuration to a yaml file in that folder
          - Create the correct arguments for the call to the model binary

        To that end, this method gathers all necessary arguments and registers
        a WorkerTask with the WorkerManager.

        Args:
            uni_id_str (str): The zero-padded uni id string
            uni_cfg (dict): given by ParamSpace. Defines how many simulations
                should be started
            is_sweep (bool): Flag is needed to distinguish between sweeps
                and single simulations. With this information, the forwarding
                of a simulation's output stream can be controlled.

        Raises:
            RuntimeError: If adding the simulation task failed
        """
        # Generate the universe basename, which will be used for the folder
        # and the task name
        uni_basename = f"uni{uni_id_str}"

        # Create the dict that will be passed as arguments to setup_universe
        setup_kwargs = dict(
            model_name=self.model_name,
            model_executable=self.model_executable,
            uni_cfg=uni_cfg,
            uni_basename=uni_basename,
        )

        # Pre-process some worker_kwargs
        wk = copy.deepcopy(self.meta_cfg["worker_kwargs"])

        if wk and wk.get("forward_streams") == "in_single_run":
            # Reverse the flag to determine whether to forward streams
            wk["forward_streams"] = not is_sweep
            wk["forward_kwargs"] = dict(forward_raw=True)

        # Try to add a task to the worker manager
        try:
            self.wm.add_task(
                name=uni_basename,
                priority=None,
                setup_func=self._setup_universe,
                setup_kwargs=setup_kwargs,
                worker_kwargs=wk,
                skippable=self.skipping["enabled"],
            )

        except Exception as err:
            # Something didn't work. For instance:
            # Task list was locked, probably because there already was a run
            raise MultiverseError(
                f"Could not add simulation task for universe "
                f"'{uni_basename}'! Did you already perform a run with this "
                "Multiverse?\n\nWhile adding the universe task, got a "
                f"{type(err).__name__}: {err}"
            ) from err

        log.debug("Added simulation task:  %s", uni_basename)

    def _add_sim_tasks(self, *, sweep: bool = None) -> int:
        """Adds the simulation tasks needed for a single run or for a sweep.

        Args:
            sweep (bool, optional): Whether tasks for a parameter sweep should
                be added or only for a single universe. If None, will read the
                ``perform_sweep`` key from the meta-configuration.

        Returns:
            int: The number of added tasks.

        Raises:
            ValueError: On ``sweep == True`` and zero-volume parameter space.
        """
        if sweep is None:
            sweep = self.meta_cfg.get("perform_sweep", False)

        pspace = self.meta_cfg["parameter_space"]

        if not sweep:
            # Only need the default state of the parameter space
            uni_cfg = pspace.default

            # Custom report invocation when only adding single task
            self.wm._invoke_report("before_adding_single_task")

            # Make a backup of the parameter space that is *actually* used
            self._perform_pspace_backup(
                psp.ParamSpace(uni_cfg),
                filename="parameter_space",
                perform_sweep=False,
            )

            # Add the task to the worker manager.
            log.progress("Adding task for simulation of a single universe ...")
            self._add_sim_task(uni_id_str="0", uni_cfg=uni_cfg, is_sweep=False)

            return 1
        # -- else: tasks for parameter sweep needed

        if pspace.volume < 1:
            raise ValueError(
                "The parameter space has no sweeps configured! "
                "Refusing to run a sweep. You can either call "
                "the run_single method or add sweeps to your "
                "run configuration using the !sweep YAML tags."
            )

        # Get the parameter space iterator and the number of already-existing
        # tasks (to later compute the number of _added_ tasks)
        psp_iter = pspace.iterator(with_info="state_no_str")
        _num_tasks = len(self.wm.tasks)

        # Distinguish whether to do a regular sweep or we are in cluster mode
        if not self.cluster_mode:
            # Make a backup of the parameter space that is *actually* used
            self._perform_pspace_backup(
                pspace, filename="parameter_space", perform_sweep=True
            )

            # Custom reporter invocation for sweep tasks
            self.wm._invoke_report("before_adding_sweep_tasks")

            # Do a sweep over the whole activated parameter space
            vol = pspace.volume
            log.progress(
                "Adding tasks for simulation of %d universes ...", vol
            )

            for i, (uni_cfg, uni_id_str) in enumerate(psp_iter):
                self._add_sim_task(
                    uni_id_str=uni_id_str, uni_cfg=uni_cfg, is_sweep=True
                )

                print(
                    f"  Added simulation task:  {uni_id_str}  ({i+1}/{vol})",
                    end="\r",
                )

        else:
            # Prepare a cluster mode sweep
            log.hilight("Preparing cluster mode sweep ...")

            # Get the resolved cluster parameters
            # These include the following values:
            #    num_nodes:   The total number of nodes to simulate on. This
            #                 is what determines the modulo value.
            #    node_index:  Equivalent to the modulo offset, which depends
            #                 on the position of this Multiverse's node in the
            #                 sequence of all nodes.
            rcps = self.resolved_cluster_params
            num_nodes = rcps["num_nodes"]
            node_index = rcps["node_index"]

            # Back up the actually-used parameter space. Do this only on the
            # first node to avoid file-writing conflicts between nodes
            if node_index == 0:
                self._perform_pspace_backup(
                    pspace, filename="parameter_space", perform_sweep=True
                )

            # Custom reporter invocation for sweep tasks
            self.wm._invoke_report("before_adding_sweep_tasks")

            # Inform about the number of universes to be simulated
            log.progress(
                "Adding tasks for cluster-mode simulation of "
                "%d universes on this node (%d of %d) ...",
                (
                    pspace.volume // num_nodes
                    + (pspace.volume % num_nodes > node_index)
                ),
                node_index + 1,
                num_nodes,
            )

            for i, (uni_cfg, uni_id_str) in enumerate(psp_iter):
                # Skip if this node is not responsible
                if (i - node_index) % num_nodes != 0:
                    log.debug("Skipping:  %s", uni_id_str)
                    continue

                # Is valid for this node, add the simulation task
                self._add_sim_task(
                    uni_id_str=uni_id_str, uni_cfg=uni_cfg, is_sweep=True
                )

        num_new_tasks = len(self.wm.tasks) - _num_tasks
        log.info("Added %d tasks.", num_new_tasks)
        return num_new_tasks

    def _validate_meta_cfg(self) -> bool:
        """Goes through the parameters that require validation, validates them,
        and creates a useful error message if there were invalid parameters.

        Returns:
            bool: True if all parameters are valid; None if no check was done.
                Note that False will never be returned, but a ValidationError
                will be raised instead.

        Raises:
            ValidationError: If validation failed.
        """
        to_validate = self.meta_cfg.get("parameters_to_validate", {})

        if not to_validate:
            log.info("Skipping parameter validation: nothing to validate.")
            return None

        elif not self.meta_cfg.get("perform_validation", True):
            log.info("Skipping parameter validation: is deactivated.")
            return None

        log.info("Validating %d parameters ...", len(to_validate))
        pspace = self.meta_cfg["parameter_space"]
        log.remark("Parameter space volume:      %d", pspace.volume)

        if pspace.volume >= 1000:
            log.note(
                "This may take a few seconds. To skip validation, set "
                "the `perform_validation` flag to False."
            )

        # The dict to collect details on invalid parameters in.
        #   - Keys are key sequences (tuple of str)
        #   - Values are sets of error _messages_, hence suppressing duplicates
        invalid_params = defaultdict(set)

        # Iterate over the whole parameter space, including the default point
        # TODO Can improve performance by directly checking sweep dimensions.
        #      ... but be very careful about robustness here!
        for params in itertools.chain(pspace, [pspace.default]):
            for key_seq, param in to_validate.items():
                # Retrieve the value from this point in parameter space
                value = psp.tools.recursive_getitem(params, keys=key_seq)

                # Validate it and store the error _message_ if invalid
                try:
                    param.validate(value)

                except ValidationError as exc:
                    invalid_params[key_seq].add(str(exc))

        if not invalid_params:
            log.note("All parameters valid.")
            return True

        # else: Validation failed. Create an informative error message
        msg = (
            f"Validation failed for {len(invalid_params)} "
            f"parameter{'s' if len(invalid_params) > 1 else ''}:\n\n"
        )

        # Get the length of longest key sequence (used for alignment)
        _nd = max(len(".".join(ks)) for ks in invalid_params.keys())

        for key_seq, errs in invalid_params.items():
            path = ".".join(key_seq)

            if len(errs) == 1:
                msg += f"  - {path:<{_nd}s}  :  {list(errs)[0]}\n"
            else:
                _details = "\n".join([f"     - {e}" for e in errs])
                msg += (
                    f"  - {path:<{_nd}s}  :  validation failed for "
                    f"{len(errs)} sweep values:\n{_details}\n"
                )

        msg += (
            "\nInspect the details above and adjust the run configuration "
            "accordingly.\n"
        )
        raise ValidationError(msg)

    def _start_working(self, *, lock_tasks: bool = True, **kwargs):
        """Wrapper that helps to invoke the WorkerManager"""
        # Maybe prevent adding further tasks
        if lock_tasks:
            self.wm.tasks.lock()

        # Adapt the run kind to better communicate what happened
        if self.skipping["skip_after_setup"]:
            self._run_tags.append("skipped after setup")

        # Tell the WorkerManager to start working (is a blocking call)
        wm_status = self.wm.start_working(**kwargs)

        # Done; finish up ...
        self._conclude_working(wm_status)

        return wm_status

    def _conclude_working(self, wm_status: str):
        """Called after working and provides some final messaging at the
        end of the simulation run."""

        # A friendly success (or failure) message
        if "success" in wm_status:
            log.success(
                "Successfully finished simulation run. %s\n",
                random.choice(SNIPPETS["yay"]),
            )
        else:
            log.caution("Simulation run %s.\n", wm_status)

        # Inform about potential other distributed workers
        dws = get_distributed_work_status(self.dirs["run"])
        if len(dws) > 1:
            fstr = "  {host_name_short:12s} - {pid:7d}: {status:10s}  ({tags})"
            dws_info: str = self._reporter._parse_distributed_work_status(
                fstr=fstr,
                distributed_work_status=dws,
                include_header=False,
            ).replace("report", "process")
            log.progress(
                "Detected %d Multiverses working together on this run.",
                len(dws),
            )
            log.note("Their current name and status is:\n\n%s\n", dws_info)

            if any(ws["status"] != "finished" for ws in dws.values()):
                log.remark(
                    "These other Multiverses may still be working ...\n"
                )
            else:
                log.progress("All other Multiverses have finished working.\n")


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------


class FrozenMultiverse(Multiverse):
    """A frozen Multiverse is like a Multiverse, but frozen.

    It is initialized from a finished :py:class:`~utopya.multiverse.Multiverse`
    run and re-creates all the attributes from that data, e.g.: the meta
    configuration, a DataManager, and a PlotManager.

    .. note::

        A frozen multiverse is no longer able to perform any simulations.
    """

    def __init__(
        self,
        *,
        model_name: str = None,
        info_bundle: ModelInfoBundle = None,
        run_dir: str = None,
        run_cfg_path: str = None,
        user_cfg_path: str = None,
        use_meta_cfg_from_run_dir: bool = False,
        **update_meta_cfg,
    ):
        """Initializes the FrozenMultiverse from a model name and the name
        of a run directory.

        Note that this also takes arguments to specify the run configuration to
        use.

        Args:
            model_name (str): The name of the model to load. From this, the
                model output directory is determined and the run_dir will be
                seen as relative to that directory.
            info_bundle (ModelInfoBundle, optional): The model information
                bundle that includes information about the binary path etc.
                If not given, will attempt to read it from the model registry.
            run_dir (str, optional): The run directory to load. Can be a path
                relative to the current working directory, an absolute path,
                or the timestamp of the run directory. If not given, will use
                the most recent timestamp.
            run_cfg_path (str, optional): The path to the run configuration.
            user_cfg_path (str, optional): If given, this is used to update the
                base configuration. If None, will look for it in the default
                path, see Multiverse.USER_CFG_SEARCH_PATH.
            use_meta_cfg_from_run_dir (bool, optional): If True, will load the
                meta configuration from the given run directory; only works for
                absolute run directories.
            **update_meta_cfg: Can be used to update the meta configuration
                generated from the previous configuration levels
        """
        # First things first: get the info bundle
        self._info_bundle = get_info_bundle(
            model_name=model_name, info_bundle=info_bundle
        )
        log.progress(
            "Initializing FrozenMultiverse for '%s' model ...", self.model_name
        )

        # Initialize property-managed attributes
        self._meta_cfg = None
        self._dirs = dict()
        self._resolved_cluster_params = None

        # Decide whether to load the meta configuration from the given run
        # directory or the currently available one.
        if (
            use_meta_cfg_from_run_dir
            and isinstance(run_dir, str)
            and os.path.isabs(run_dir)
        ):
            raise NotImplementedError("use_meta_cfg_from_run_dir")

            # Find the meta config backup file and load it
            # Alternatively, create it from the singular backup files ...
            # log.info("Trying to load meta configuration from given absolute "
            #          "run directory ...")
            # Update it with the given update_meta_cfg dict

        else:
            # Need to create a meta configuration from the currently available
            # values.
            mcfg, _ = self._create_meta_cfg(
                run_cfg_path=run_cfg_path,
                user_cfg_path=user_cfg_path,
                update_meta_cfg=update_meta_cfg,
            )

        # Only keep selected entries from the meta configuration. The rest is
        # not needed and is deleted in order to not confuse the user with
        # potentially varying versions of the meta config.
        self._meta_cfg = {
            k: v
            for k, v in mcfg.items()
            if k
            in (
                "debug_level",
                "paths",
                "data_manager",
                "plot_manager",
                "cluster_mode",
                "cluster_params",
            )
        }
        log.info("Built meta configuration.")
        log.remark("  Debug level:  %d", self.debug_level)
        self._apply_debug_level()

        # Need to make some DataManager adjustments; do so via update dicts
        dm_cluster_kwargs = dict()
        if self.cluster_mode:
            log.note("Cluster mode enabled.")
            self._resolved_cluster_params = self._resolve_cluster_params()
            rcps = self.resolved_cluster_params  # creates a deep copy

            log.note(
                "This is node %d of %d.",
                rcps["node_index"] + 1,
                rcps["num_nodes"],
            )

            # Changes to the meta configuration
            # To avoid config file collisions in the PlotManager:
            self._meta_cfg["plot_manager"]["cfg_exists_action"] = "skip"

            # _Additional_ arguments to pass to DataManager.__init__ below
            timestamp = rcps["timestamp"]
            dm_cluster_kwargs = dict(
                out_dir_kwargs=dict(timestamp=timestamp, exist_ok=True)
            )

        # Generate the path to the run directory that is to be loaded
        self._get_run_dir(**self.meta_cfg["paths"], run_dir=run_dir)
        log.note("Run directory:\n  %s", self.dirs["run"])

        # Create a data manager
        self._dm = DataManager(
            self.dirs["run"],
            name=f"{self.model_name}_data",
            **self.meta_cfg["data_manager"],
            **dm_cluster_kwargs,
        )
        log.progress("Initialized DataManager.")

        # Instantiate the PlotManager via the helper method
        self._pm = self._setup_pm()

        log.progress("Initialized FrozenMultiverse.\n")

    def _create_run_dir(self, *_, **__):
        """Overload of parent method, for safety: we should not create a new
        run directory."""
        raise AttributeError(
            f"`_create_run_dir` method should not be called from {type(self)}"
        )


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------


class DistributedMultiverse(FrozenMultiverse):
    """A distributed Multiverse is like a Multiverse, but initialized from an
    existing meta-configuration.

    Unlike the FrozenMultiverse, it is able to continue, join or repeat an
    existing simulation run.
    """

    def __init__(
        self,
        *,
        run_dir: str,
        model_name: str = None,
        info_bundle: ModelInfoBundle = None,
        no_reports: bool = False,
    ):
        """Initializes a DistributedMultiverse from a model name and an
        existing run directory.

        Args:
            run_dir (str, optional): The run directory to load. Can be a path
                relative to the current working directory, an absolute path,
                or the timestamp of the run directory. If not given, will use
                the most recent timestamp.
            model_name (str): The name of the model to load. From this, the
                model output directory is determined and the run_dir will be
                seen as relative to that directory.
            info_bundle (ModelInfoBundle, optional): The model information
                bundle that includes information about the binary path etc.
                If not given, will attempt to read it from the model registry.
            no_reports (bool, optional): If True, will not write work status or
                other simulation report files. Set this, if invoking this with
                many *individual* ``universes`` and in order to avoid creating
                as many report files.
        """
        # First things first: get the info bundle
        if info_bundle is None:
            info_bundle = get_info_bundle(
                model_name=model_name, info_bundle=info_bundle
            )
        self._info_bundle = info_bundle

        log.progress(
            "Initializing DistributedMultiverse for '%s' model ...",
            self.model_name,
        )

        # Initialize property-managed attributes
        self._dirs = dict()
        self._model_executable = None
        self._tmpdir = None

        self._run_tags: List[str] = ["distributed"]

        # Generate the path to the run directory that is to be loaded.
        # At this point, we don't know the output directory, but we can deduce
        # it from the path (or from the user config) ...
        run_dir = self._get_run_dir(out_dir=None, run_dir=run_dir)
        log.note("Run directory:\n  %s", self.dirs["run"])

        # Load the meta config
        meta_cfg_path = os.path.join(run_dir, "config", "meta_cfg.yml")
        if not os.path.isfile(meta_cfg_path):
            raise ValueError(
                "No meta configuration file found in specified run directory! "
                f"Expected it at:  {meta_cfg_path}"
            )

        log.note(
            "Loading existing meta configuration from:\n  %s", meta_cfg_path
        )
        mcfg = load_yml(meta_cfg_path)

        # Only keep selected entries from the meta configuration. The rest is
        # not needed and is deleted in order to not confuse the user with
        # potentially varying versions of the meta config. Also, this way we
        # will notice if certain keys are accessed that shouldn't be used here.
        self._meta_cfg = {
            k: v
            for k, v in mcfg.items()
            if k
            not in (
                "data_manager",
                "plot_manager",
                "cluster_params",
            )
        }
        log.info("Restored meta-configuration.")

        log.remark("  Debug level:  %d", self.debug_level)
        self._apply_debug_level()

        # Prepare executable and WorkerManager
        self._prepare_executable(**self.meta_cfg["executable_control"])

        self._wm = WorkerManager(**self.meta_cfg["worker_manager"])

        # Reporter
        reporter_kwargs = self.meta_cfg["reporter"]
        if no_reports:
            rfs = reporter_kwargs["report_formats"]
            rfs["report_file"]["write_to"]["file"]["skip_if_dmv"] = True
            rfs["work_status"]["write_to"]["file"]["skip_if_dmv"] = True

        self._reporter = WorkerManagerReporter(
            self.wm,
            mv=self,
            report_dir=self.dirs["run"],
            **reporter_kwargs,
        )

        # TODO Should the DistributedMultiverse have a DataManager and a
        #      PlotManager as well? In principle, if it's allowed to perform a
        #      run, why shouldn't it also be allowed to load and evaluate?

        log.progress("Initialized DistributedMultiverse.\n")

    def run_single(self, *_, **__):
        raise NotImplementedError(f"{type(self).__name__}.run_single")

    def run_sweep(self, *_, **__):
        raise NotImplementedError(f"{type(self).__name__}.run_sweep")

    def run(
        self,
        *,
        universes: Union[Literal["all"], str, List[str]] = "all",
        num_workers: int = None,
        timeout: float = None,
        on_existing_uni_dir: str = "continue",
        on_existing_uni_cfg: str = "continue",
        on_existing_uni_output: str = "raise",
    ):
        """Starts a simulation run for all or a specified subset of universes,
        working on the existing run directory.

        Using the ``on_existing_uni_output`` argument, it is possible to skip
        universes that already created output; alternatively, the output can
        be removed, effectively repeating the universe simulation.

        Args:
            universes (Union[Literal["all"], str, List[str]], optional): Which
                universes to run again. Can either be ``all`` (default)
                to run all universes, or a selection of universe IDs.
                The selection can be given as a list of ID strings or a string
                of comma-separated IDs. Example for valid formats:

                    ['uni01', 'uni02', 'uni03']
                    'uni01,uni02,uni03'
                    ['01', '02', '03']
                    1,2,3

                Leading zeros and ``uni`` are optional.
            num_workers (int, optional): Specify the number of workers
                to use, overwriting the setting from the meta-configuration.
            timeout (float, optional): If given, overwrites the existing value
                for the WorkerManager timeout, which may have been set
                in the original Multiverse run.
            on_existing_uni_dir (str, optional): How to proceed if a universe
                directory already exists; can be ``skip``, ``raise``, or
                ``continue``. Set this to ``continue`` if you previously
                generated all universe output directories.
            on_existing_uni_cfg (str, optional): How to proceed if a universe
                configuration already exists; can be ``skip``, ``raise``, or
                ``continue``. Set this to ``continue`` if you previously
                generated all universe config files.
            on_existing_uni_output (str, optional): What to do if universe
                output already exists. Options are ``skip``, ``raise``,
                ``continue`` or ``clear``; the latter will remove existing
                output files without prompting for this again!
        """

        def parse_uni_id_str(s: str) -> Tuple[str, int]:
            if s.lower().startswith("uni"):
                s = s[3:]
            return s, int(s)

        if self.cluster_mode:
            raise MultiverseError("Cannot run again in cluster mode, sorry.")

        log.info("Preparing to run or continue existing simulation ...")

        # Update skipping options to allow running on a previously started
        # simulation, meaning that at least some (or all) universe data
        # directories will exist and they may contain a config. Some of them
        # may even contain output data...
        skipping_updates = dict(
            enabled=True,
            skip_after_setup=False,
            on_existing_uni_dir=on_existing_uni_dir,
            on_existing_uni_cfg=on_existing_uni_cfg,
            on_existing_uni_output=on_existing_uni_output,
        )
        self.skipping.update(skipping_updates)

        log.note(
            "Updated skipping configuration accordingly:\n%s\n",
            "\n".join(f"  {k}: {v}" for k, v in self.skipping.items()),
        )

        # If clearing existing output, unlock task list ...
        if on_existing_uni_output == "clear":
            self.wm.tasks.unlock()
            log.note(
                "Unlocked task list to allow re-running with clearing output."
            )

        # Add the tasks, depending on whether all or a selection of universes
        # should be carried out
        if universes == "all":
            log.note("Adding tasks for all universes ...")
            self._add_sim_tasks()
            self._run_tags = ["run existing", "all"]
            lock_tasks = True

        elif isinstance(universes, (str, tuple, list)):
            # Add only a selection of universe tasks.

            # Bring selection into uniform format.
            # Initial format can be ['uni01', 'uni02', …] but also of form
            # ['uni01,uni02', 'uni03', …] so it's easiest and most robust to
            # just join them all together to a string and then split them again
            if isinstance(universes, (tuple, list)):
                universes = ",".join([str(u) for u in universes])

            universes = set(
                [u.strip() for u in universes.split(",") if u.strip()]
            )
            is_sweep = len(universes) > 1

            log.note(
                "Adding tasks for %d universe%s ...",
                len(universes),
                "s" if is_sweep else "",
            )
            if len(universes) < 64:
                log.remark(
                    "Selected universe%s:\n\n%s\n",
                    "s" if is_sweep else "",
                    make_columns(universes, wrap_width=60),
                )

            # For that, first create all possible parameter space combinations:
            pspace = self.meta_cfg["parameter_space"]
            psp_iter = pspace.iterator(with_info="state_no_str")
            uni_cfgs: Dict[int, dict] = {
                int(uni_id_str): uni_cfg for uni_cfg, uni_id_str in psp_iter
            }

            lock_tasks = len(universes) >= pspace.volume

            # Now, add the respective tasks, if they are part of the selection:
            for i, uni_id_str in enumerate(universes):
                uni_id_str, uni_id = parse_uni_id_str(uni_id_str)

                uni_cfg = uni_cfgs.get(uni_id)
                if uni_cfg is None:
                    raise MultiverseError(
                        f"A universe with ID '{uni_id_str}' does not exist! "
                        "Make sure the universe IDs are part of the specified "
                        "parameter space."
                    )

                self._add_sim_task(
                    uni_id_str=uni_id_str,
                    uni_cfg=uni_cfg,
                    is_sweep=is_sweep,
                )

            log.info("Added %d tasks.", i + 1)
            self._run_tags = ["run existing", "selection"]

        else:
            raise TypeError(
                "Argument `universes` should be 'all' or a string or list of "
                f"universe IDs! Was {type(universes)} with value: {universes}"
            )

        # Start working with the specified number of workers
        if num_workers is not None:
            self.wm.num_workers = num_workers

        run_kwargs = copy.deepcopy(self.meta_cfg["run_kwargs"])
        if timeout is not None:
            run_kwargs["timeout"] = timeout

        self._start_working(lock_tasks=lock_tasks, **run_kwargs)

    def join_run(
        self,
        *,
        num_workers: int = None,
        shuffle_tasks: bool = True,
        timeout: float = None,
    ):
        """Joins an already-running simulation and performs tasks that have not
        been taken up yet.

        Args:
            num_workers (int, optional): Set number of workers to use.
            shuffle_tasks (bool, optional): If given, will overwrite
                the ``shuffle_tasks`` run arguments.
                When joining an already-running simulation run, it is advisable
                to set this to True to reduce competition for new tasks.
            timeout (float, optional): If given, will overwrite the existing
                value for the WorkerManager timeout, which may have been set
                in the original Multiverse run.
        """
        log.hilight("Preparing to join simulation run ...")
        meta_cfg = self.meta_cfg
        skipping = self.skipping

        # Can we even join this run? We need skipping enabled and a sweep!
        if not skipping["enabled"]:
            raise MultiverseError(
                "Cannot join a Multiverse run that was started with "
                "`skipping.enabled` set to False!"
            )

        if not meta_cfg["perform_sweep"]:
            raise MultiverseError(
                "Cannot join existing run if it is not a parameter sweep."
            )

        pspace = meta_cfg["parameter_space"]
        num_uni_dirs = len(glob.glob(os.path.join(self.dirs["data"], "uni*")))
        if num_uni_dirs >= pspace.volume:
            raise MultiverseRunAlreadyFinished(
                f"There are already {num_uni_dirs} universe directories for a "
                f"parameter space of {pspace.volume}. This means that there "
                "are no tasks left to join in on or the Multiverse run has "
                "already finished previously.\n\n"
                "Are you trying to join the correct Multiverse run?\n"
                f"  {self.dirs['run']}\n"
            )

        # Ok, all good. Add _all_ tasks, some of which will not need to run.
        self._add_sim_tasks(sweep=True)
        self._run_tags = ["joined"]

        # We may want to overwrite some settings.
        if num_workers is not None:
            self.wm.num_workers = num_workers

        run_kwargs = copy.deepcopy(self.meta_cfg["run_kwargs"])
        if shuffle_tasks is not None:
            run_kwargs["shuffle_tasks"] = shuffle_tasks
        if timeout is not None:
            run_kwargs["timeout"] = timeout

        # Now we can start working ...
        self._start_working(**run_kwargs)

    # .........................................................................

    def _prepare_executable(self, *args, **kwargs) -> None:
        if self.meta_cfg["backups"]["backup_executable"]:
            execpath = os.path.join(
                self.dirs["run"], "backup", self.model_name
            )
            if not os.path.isfile(execpath):
                raise FileNotFoundError(f"No executable found at {execpath}!")
            log.remark("Restored executable at:\n  %s", execpath)

            self._model_executable = execpath

        return super()._prepare_executable(*args, **kwargs)

    def _perform_pspace_backup(*args, **kwargs):
        log.debug(
            "  Skipping parameter space backup (was already read from backup)."
        )

    # .. Overloads for universe setup .........................................

    def _setup_universe_dir(self, uni_dir: str, *, uni_basename: str):
        """Overload of parent method that allows for universe directories to
        already exist."""

        if not os.path.isdir(uni_dir):
            # Set up from scratch ... if it does not exist yet (checked also
            # in parent method, potentially raising SkipExistingUniverse)
            return super()._setup_universe_dir(
                uni_dir=uni_dir,
                uni_basename=uni_basename,
            )

        # else: already exists.
        self._maybe_skip("existing_uni_dir", desc=uni_basename)

        # Check whether the directory is empty
        ALLOWED_FILES = ("config.yml",)
        existing_output = [
            f for f in os.listdir(uni_dir) if f not in ALLOWED_FILES
        ]
        if not existing_output:
            # No output yet, can simply continue.
            return

        # else: output was already created.
        # We may want to respond to this by raising, clearing or skipping.
        if self.skipping["on_existing_uni_output"] == "clear":
            for fname in existing_output:
                os.remove(os.path.join(uni_dir, fname))
        else:
            self._maybe_skip("existing_uni_output", desc=uni_basename)

    def _setup_universe_config(self, *, uni_cfg_path: str, **kwargs) -> dict:
        """Overload of parent method that checks if a universe config already
        exists and, if so, loads that one instead of storing a new one.
        """
        if os.path.isfile(uni_cfg_path):
            self._maybe_skip(
                "existing_uni_cfg",
                desc=uni_cfg_path,
            )

            log.debug("Restoring universe config from:\n  %s.", uni_cfg_path)
            return load_yml(uni_cfg_path)

        # else: Need to create it, which will not work if it was done before.
        return super()._setup_universe_config(
            uni_cfg_path=uni_cfg_path, **kwargs, mode="x"
        )


# -- Multiverse-related standalone functions ----------------------------------
# .. Work status of distributed Multiverse runs ...............................


def get_status_file_paths(
    run_dir: str, *, status_file_glob=".status*.yml"
) -> List[str]:
    return glob.glob(os.path.join(run_dir, status_file_glob))


def get_distributed_work_status(
    run_dir: str, **kwargs
) -> Dict[str, Optional[dict]]:
    """Finds and loads the work status files in the given directory"""

    def try_load(p: str) -> Optional[dict]:
        try:
            return load_yml(p)
        except Exception:
            return None

    return {
        path: try_load(path)
        for path in sorted(get_status_file_paths(run_dir, **kwargs))
    }


# .. Extracting information from the work status dict .........................


def active_dmvs(dws: Dict[str, Optional[dict]]) -> Dict[str, Optional[dict]]:
    """Returns status of the distributed Multiverse instances that are
    currently ``working``, given a distributed work status dict."""
    return {k: v for k, v in dws.items() if v and v["status"] in ("working",)}


def combined_dmv_progress(dws: Dict[str, Optional[dict]]) -> float:
    """Extracts the sum of individual multiverse's active progress"""
    if not dws:
        return float("nan")

    # TODO consider returning a tuple of (lower bound sum, sum) value, where
    #      the first value ignores nans.
    try:
        return sum(
            s["progress"]["worked_on"] if s else float("nan")
            for s in dws.values()
        )
    except Exception:
        return float("nan")
