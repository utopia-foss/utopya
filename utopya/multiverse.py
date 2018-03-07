"""Implementation of the Multiverse class.

The Multiverse supplies the main user interface of the frontend.
"""
from utopya.tools import recursive_update, read_yml, write_yml
from utopya.workermanager import WorkerManager
from utopya.workermanager import enqueue_json

import os
import time
import logging

log = logging.getLogger(__name__)


class Multiverse:
    UTOPIA_EXEC = "utopia"

    def __init__(self, *, metaconfig: str="metaconfig.yml", userconfig: str=None):
        """Initialize the setup.

        Load default configuration file and adjust parameters given
        by metaconfig and userconfig.
        """
        self._config = self._configure(metaconfig, userconfig)

        # set the model name for folder setup
        self.model_name = self._config['model_name']

        # Initialise empty dict for keeping track of directory paths
        self.dirs = dict()

        # Now create the simulation directory and its internal subdirectories
        self._create_sim_dir(**self._config['multiverse']['output_path'])

        # create a WorkerManager instance
        self._wm = WorkerManager(**self._config['multiverse']['worker_manager'])

    def _configure(self, *, metaconfig: str, userconfig: str=None) -> dict:
        """Read default configuration file and adjust parameters.

        The default metaconfig file, the user/machine-specific file (if
        existing) and the regular metaconfig file are read in and the default
        metaconfig is adjusted accordingly to create a single output file.

        Args:
            metaconfig: path to metaconfig. An empty or invalid path raises
                FileNotFoundError.
            userconfig: optional user/machine-specific configuration file

        Returns:
            dict: returns the updated default metaconfig to be processed
                further or to be written out.
        """
        # In the following, the final configuration dict is built from three components:
        # The base is the default configuration, which is always present
        # If a userconfig is present, this recursively updates the defaults
        # Then, the given metaconfig recursively updates the created dict
        log.debug("Reading default metaconfig.")
        defaults = read_yml("default_metaconfig.yml",
                            error_msg="default_metaconfig.yml is not present.")

        if userconfig is not None:
            log.debug("Reading userconfig from {}.".format(userconfig))
            userconfig = read_yml(userconfig,
                                  error_msg="{0} was given but userconfig"
                                            " could not be found."
                                            "".format(userconfig))

        log.debug("Reading metaconfig from {}.".format(metaconfig))
        metaconfig = read_yml(metaconfig,
                              error_msg="{0} was given but metaconfig"
                                        " could not be found."
                                        "".format(metaconfig))

        # TODO: typechecks of values should be completed below here.
        # after this point it is assumed that all values are valid

        # Now perform the recursive update steps
        log.debug("Updating default metaconfig with given configurations.")
        if userconfig is not None:  # update default with user spec
            defaults = recursive_update(defaults, userconfig)

        # update default_metaconfig with metaconfig
        defaults = recursive_update(defaults, metaconfig)

        return defaults

    def _create_sim_dir(self, *, out_dir: str, model_note: str=None) -> None:
        """Create the folder structure for the simulation output.

        The following folder tree will be created
        utopia_output/   # all utopia output should go here
            model_a/
                180301-125410_my_model_note/
                    config/
                    eval/
                    universes/
                        uni000/
                        uni001/
                        ...
            model_b/
                180301-125412_my_first_sim/
                180301-125413_my_second_sim/


        Args:
            model_name (str): Description
            out_dir (str): Description
            model_note (str, optional): Description

        Raises:
            RuntimeError: If the simulation directory already existed. This
                should not occur, as the timestamp is unique. If it occurs,
                something is seriously wrong. Or you are in a strange time
                zone.
        """
        # NOTE could check if the model name is valid

        # Create the folder path to the simulation directory
        log.debug("Expanding user %s", out_dir)
        out_dir = os.path.expanduser(out_dir)
        sim_dir = os.path.join(out_dir,
                               self.model_name,
                               time.strftime("%Y%m%d-%H%M%S"))

        # Append a model note, if needed
        if model_note:
            sim_dir += "_" + model_note

        # Inform and store to directory dict
        log.debug("Expanded user and time stamp to %s", sim_dir)
        self.dirs['sim_dir'] = sim_dir

        # Recursively create the whole path to the simulation directory
        try:
            os.makedirs(sim_dir)
        except OSError as err:
            raise RuntimeError("Simulation directory already exists. This "
                               "should not have happened. Try to start the "
                               "simulation again.") from err

        # Make subfolders
        for subdir in ('config', 'eval', 'universes'):
            subdir_path = os.path.join(sim_dir, subdir)
            os.mkdir(subdir_path)
            self.dirs[subdir] = subdir_path

        log.debug("Finished creating simulation directory. Now registered: %s",
                  self.dirs)

    def _create_uni_dir(self, *, uni_id: int, max_uni_id: int) -> str:
        """The _create_uni_dir generates the folder for a single universe.

        Within the universes directory, create a subdirectory uni### for the
        given universe number, zero-padded such that they are sortable.

        Args:
            uni_id (int): ID of the universe whose folder should be created
            max_uni_id (int): highest ID, needed for correct zero-padding
        """
        # Use a format string for creating the uni_path
        fstr = "{id:>0{digits:}d}"
        uni_path = os.path.join(self.dirs['universes'],
                                fstr.format(id=uni_id, digits=len(max_uni_id)))

        # Now create the folder
        os.mkdir(uni_path)
        log.debug("Created universe path: %s", uni_path)
        return uni_path

    def _add_sim_task(self, *, uni_id: int, max_uni_id: int, cfg_dict: dict, ) -> None:
        """Helper function that handles task assignment to the WorkerManager.

        This function performs the following steps:
            - Creating a universe (folder) for the task (simulation).
            - Writing the necessary part of the metaconfig to a file
            - Passing a functional setup_func and its arguments to WorkerManager.add_task

        Args:
            uni_id (int): ID of the universe whose folder should be created
            max_uni_id (int): highest ID, needed for correct zero-padding
            cfg_dict (dict): given by ParamSpace. Defines how many simulations
                should be started
        """
        def setup_func(*, utopia_exec: str, model_name: str, uni_id: int, max_uni_id: int, cfg_dict: dict) -> dict:
            """Sub-helper function to be returned as functional.

            Creates universe for the task, writes configuration, calls
            WorkerManager.add_task.

            Args:
                utopia_exec (str): class constant for utopia executable
                model_name (str): name of the model *derpface*
                uni_id (int): ID of the universe whose folder should be created
                max_uni_id (int): highest ID, needed for correct zero-padding
                cfg_dict (dict): given by ParamSpace. Defines how many simulations
                    should be started

            Returns:
                dict: kwargs for the process to be run when task is grabbed by
                    Worker.
            """
            # create universe directory
            uni_dir = self._create_uni_dir(uni_id=uni_id,
                                           max_uni_id=max_uni_id)

            # write essential part of config to file:
            uni_cfg_path = os.path.join(uni_dir, "config.yml")
            write_yml(d=cfg_dict, path=uni_cfg_path)

            # building args tuple for task assignment
            # assuming there exists an attribute for the executable and for the
            # model
            args = (utopia_exec, model_name, uni_cfg_path)

            # setup kwargs
            worker_kwargs = dict(args=args,  # passing the arguments
                                 read_stdout=True,
                                 line_read_func=enqueue_json)  # Callable
            return worker_kwargs

        setup_kwargs = dict(utopia_exec=self.UTOPIA_EXEC,
                            model_name=self.model_name,
                            uni_id=uni_id, max_uni_id=max_uni_id,
                            cfg_dict=cfg_dict)

        self._wm.add_task(priority=None,
                          setup_func=setup_func,
                          setup_kwargs=setup_kwargs)
