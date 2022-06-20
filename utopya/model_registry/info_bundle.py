"""Implements the ModelInfoBundle class, which holds a single bundle of
information about a model.
"""
import copy
import logging
import os
import time
from typing import Sequence, Tuple, Union

from ..exceptions import MissingProjectError
from ..tools import load_selected_keys, load_yml, pformat, recursive_update

log = logging.getLogger(__name__)

TIME_FSTR = "%y%m%d-%H%M%S"
"""Format string to use for generating readable time stamps"""

# -----------------------------------------------------------------------------


class ModelInfoBundle:
    """A bundle of model information; behaves like a read-only dict"""

    SRC_DIR_SEARCH_PATHS = {
        "model_info": "{model_name:}_info.yml",
        "default_cfg": "{model_name:}_cfg.yml",
        "default_plots": "{model_name:}_plots.yml",
        "base_plots": "{model_name:}_base_plots.yml",
    }
    """Path keys that can be searched within the source directory.
    Values are format strings that are evaluated with additional information
    being available (``model_name``).
    The resulting paths are interpreted as paths relative to the source
    directory.
    """

    FSTR_SUFFIX = "_fstr"
    """A suffix used to detect format strings in the path parsing routine.

    If a key ends with such a suffix, the corresponding value is assumed to be
    a format string and is evaluated. The resulting path is stored, dropping
    the suffix.
    """

    PATHS_SCHEMA = (
        ("executable", str, True),
        ("model_info", str),
        ("source_dir", str),
        ("default_cfg", str),
        ("default_plots", str),
        ("base_plots", str),
        ("py_tests_dir", str),
        ("py_plots_dir", str),
    )
    """Schema to use for a bundle's ``paths`` entry"""

    METADATA_SCHEMA = (
        ("version", str),
        ("long_name", str),
        ("description", str),
        ("long_description", str),
        ("license", str),
        ("author", str),
        ("email", str),
        ("website", str),
        ("utopya_compatibility", str),
        ("language", str),
        ("requirements", list),
        ("misc", dict),
    )
    """Schema to use for a bundle's ``metadata`` entry"""

    # .........................................................................

    def __init__(
        self,
        *,
        model_name: str,
        paths: dict,
        metadata: dict = None,
        project_name: str = None,
        eval_after_run: bool = None,
        registration_time: str = None,
        missing_path_action: str = "log",
        extract_model_info: bool = False,
    ):
        """Initialize a ModelInfoBundle

        Args:
            model_name (str): Name of the model this info bundle describes
            paths (dict): A dictionary of paths
            metadata (dict, optional): A dictionary of metadata entries
            project_name (str, optional): The project this model is part of
            eval_after_run (bool, optional): Whether a model run should be
                followed by an evaluation.
            registration_time (str, optional): Timestamp of registration
            missing_path_action (str, optional): Action upon a path in the
                ``paths`` dict that does not exist.
                Can be ``ignore``, ``log``, ``warn``, ``raise``.
            extract_model_info (bool, optional): Whether to use the information
                from a potentially existing file at the ``model_info`` path
                to pre-populate this bundle. Any explicitly given arguments
                take precedence over the information from that file.
        """
        self._model_name = model_name
        self._reg_time = (
            registration_time
            if registration_time is not None
            else time.strftime(TIME_FSTR)
        )

        # Parse paths that were passed as argument here
        paths = self._parse_paths(
            **{k: os.path.expanduser(p) for k, p in paths.items() if p},
            missing_path_action=missing_path_action,
        )

        # If a model info file is known at this point, use it to pre-populate
        # the data dict.
        self._d = dict(
            paths=dict(),
            metadata=dict(),
            project_name=project_name,
            eval_after_run=eval_after_run,
        )

        if extract_model_info and paths.get("model_info"):
            self._d = recursive_update(
                self._d,
                self._load_and_parse_model_info(paths["model_info"]),
            )

        # Now populate the data dict with the explicitly passed arguments,
        # which should take precedence over the information from the model info
        err_msg_fstr = "Failed loading {} info for '{}' model info bundle!"

        load_selected_keys(
            paths,
            add_to=self.paths,
            keys=self.PATHS_SCHEMA,
            err_msg_prefix=err_msg_fstr.format("paths", model_name),
        )

        load_selected_keys(
            (metadata if metadata is not None else {}),
            add_to=self.metadata,
            keys=self.METADATA_SCHEMA,
            err_msg_prefix=err_msg_fstr.format("metadata", model_name),
        )

        log.debug(
            "Created configuration bundle for model '%s'.", self.model_name
        )

    # Magic methods ...........................................................

    def __eq__(self, other) -> bool:
        """Compares equality by comparing the stored configuration. Only if
        another ModelInfoBundle is compared against does the model name also
        take part in the comparison.
        """
        if isinstance(other, ModelInfoBundle):
            return self._d == other._d and self._model_name == other.model_name
        return self._d == other

    # Formatting ..............................................................

    def __str__(self) -> str:
        return "<Info bundle for '{}' model>\n{}\n".format(
            self._model_name, pformat(self._d)
        )

    # General Access ..........................................................

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def registration_time(self) -> str:
        """Registration time string of this bundle"""
        return self._reg_time

    @property
    def as_dict(self) -> dict:
        """Returns a deep copy of all bundle data. This does NOT include the
        model name and the registration time."""
        return copy.deepcopy(self._d)

    def __getitem__(self, key: str):
        """Direct access to the full bundle data"""
        return self._d[key]

    @property
    def executable(self) -> str:
        """The path to the model executable"""
        return self._d["paths"]["executable"]

    @property
    def paths(self) -> dict:
        """Access to the paths information of the bundle"""
        return self._d["paths"]

    @property
    def metadata(self) -> dict:
        """Access to the metadata information of the bundle"""
        return self._d["metadata"]

    @property
    def project_name(self) -> str:
        """Access to the Utopia project name information of the bundle"""
        return self._d["project_name"]

    @property
    def eval_after_run(self) -> Union[bool, None]:
        """Whether a model run should be followed by the evaluation routine."""
        return self._d["eval_after_run"]

    @property
    def project(self) -> Union[None, dict]:
        """Load the project information corresponding to this project. Will be
        None if no project is associated.
        """
        if not self.project_name:
            return None

        from .. import PROJECTS

        return PROJECTS[self.project_name]

    @property
    def missing_paths(self) -> dict:
        """Returns those paths where os.path.exists did not evaluate to True"""
        return {k: p for k, p in self.paths.items() if not os.path.exists(p)}

    # Helpers .................................................................

    def _load_and_parse_model_info(self, path: str) -> dict:
        """Loads the model info file from the given path and parses it.

        Parsing steps:
            - Remove entries ``model_name`` or ``label`` that are not
              relevant at this point.

        Args:
            path (str): Path to the model info YAML file
        """
        d = load_yml(path)

        for key in ("model_name", "label"):
            d.pop(key, None)

        return d

    def _parse_paths(
        self,
        *,
        missing_path_action: str,
        executable: str,
        source_dir: str = None,
        base_executable_dir: str = None,
        base_source_dir: str = None,
        model_info: str = None,
        **more_paths,
    ) -> dict:
        """Given the path arguments, parse them into absolute paths.
        There are the following parsing steps:

            1. Evaluate ``executable`` and ``source_dir``, potentially using
               the ``base_*`` arguments to resolve relative paths.
            2. If a ``model_info`` path is given, the directory of that file
               is used for any *missing* ``base_*`` argument.
            3. If a ``source_dir`` was given, that directory is searched for
               further existing paths using ``SRC_DIR_SEARCH_PATHS``.
            4. Empty entries in ``more_paths`` are skipped
            5. Remaining entries in ``more_paths`` that end with the suffix
               specified by the ``FSTR_SUFFIX`` class attribute are interpreted
               as format strings and resolved by providing information on the
               ``model_name`` and all available ``paths``. Relative paths are
               interpreted as relative to the source directory.
            6. For all paths, it is checked whether they exist. The
               ``missing_path_action`` argument determines what to do if not.
        """
        paths = dict()

        # Make sure the base_* are not None (makes os.path.join call easier)
        base_executable_dir = (
            base_executable_dir if base_executable_dir is not None else ""
        )
        base_source_dir = (
            base_source_dir if base_source_dir is not None else ""
        )

        # If a model info file is given, can use its directory as a base
        # directory to determine the missing base_* arguments
        model_info_dir = ""
        if model_info:
            if not os.path.isabs(model_info):
                raise ValueError(
                    "The path to the model info file needs to be absolute, "
                    f"but was:  {model_info}"
                )
            model_info_dir = os.path.dirname(model_info)

            if not base_source_dir:
                base_source_dir = model_info_dir

            if not base_executable_dir:
                base_executable_dir = model_info_dir

            paths["model_info"] = model_info

        # Evaluate the executable file path
        paths["executable"] = os.path.join(base_executable_dir, executable)

        # Prepare an absolute version of the source directory path
        abs_source_dir_path = None
        if source_dir:
            abs_source_dir_path = os.path.realpath(
                os.path.join(base_source_dir, source_dir)
            )

        # If a source directory is given, store it, then auto-detect some files
        if abs_source_dir_path:
            paths["source_dir"] = abs_source_dir_path

            for key, fname_fstr in self.SRC_DIR_SEARCH_PATHS.items():
                # Build the full file path, making the model name available.
                # If that path points to an existing file or directory, add it.
                fname = fname_fstr.format(model_name=self.model_name)
                fpath = os.path.join(abs_source_dir_path, fname)

                if os.path.exists(fpath):
                    paths[key] = fpath

        # Parse remaining path entries
        for key, path in more_paths.items():
            if path is None:
                continue

            # Evaluate potentially existing format string style paths, adding
            # them to the paths dict *without* the suffix that was used to
            # identify them.
            if key.endswith(self.FSTR_SUFFIX):
                subkey = key[: -len(self.FSTR_SUFFIX)]
                path = path.format(model_name=self.model_name, paths=paths)
                if subkey in paths or not os.path.exists(path):
                    continue

                # Path exists and was not yet added; store it under the subkey
                key = subkey

            # Interpret relative paths as relative to the source directory
            if not os.path.isabs(path):
                # Is relative. Try to resolve it, starting with a path relative
                # to the source directory. As a fallback, can still attempt to
                # interpret it relative to the model info file.
                if key in self.SRC_DIR_SEARCH_PATHS and abs_source_dir_path:
                    path = os.path.join(abs_source_dir_path, path)

                elif model_info_dir:
                    path = os.path.join(model_info_dir, path)

                else:
                    raise ValueError(
                        f"Given `{key}` path ({path}) was relative, but "
                        "no source directory was specified relative to which "
                        "this path could be interpreted and no model "
                        "information file was available either!"
                    )

            # All good, can now store it. If it was a path that is not to be
            # seen as relative to the source directory, that will lead to an
            # error being thrown below ...
            paths[key] = path

        # Done populating paths dict.
        # Make sure paths are all absolute and exist.
        for key, path in paths.items():
            if not os.path.isabs(path):
                raise ValueError(
                    f"The given `{key}` path ({path}) for info bundle "
                    f"of model '{self.model_name}' was not absolute! "
                    "Please provide only absolute paths (may include ~)."
                )

            if not os.path.exists(path):
                msg = (
                    f"Given '{key}' path for model '{self.model_name}' does "
                    f"not exist: {path}"
                )

                if missing_path_action == "warn":
                    log.warning(msg)

                elif missing_path_action in ("log", "ignore"):
                    log.debug(msg)

                elif missing_path_action == "raise":
                    raise ValueError(
                        msg + "\nEither adjust the corresponding model info "
                        "bundle or place the expected file at that path. "
                        "To ignore this error, pass the `missing_path_action` "
                        "argument to ModelInfoBundle."
                    )

                else:
                    raise ValueError(
                        f"Invalid missing_path_action '{missing_path_action}'!"
                        " Choose from: ignore, log, warn, raise."
                    )

        return paths

    # YAML representation .....................................................

    @classmethod
    def to_yaml(cls, representer, node):
        """Creates a YAML representation of the data stored in this bundle.

        Args:
            representer (ruamel.yaml.representer): The representer module
            node (ModelInfoBundle): The node to represent, i.e. an instance of
                this class.

        Returns:
            A YAML representation of the given instance of this class.
        """
        return representer.represent_data(node._d)
