"""A module supplying tools for registration and manipulation of projects

.. todo::

    Improve schema handling and consider using a similar approach as with the
    info bundles. There should also be a better way to define defaults values.
"""

import logging
import os
from typing import Dict

from .cfg import load_from_cfg_dir, write_to_cfg_dir
from .exceptions import MissingProjectError
from .tools import load_selected_keys, load_yml, pformat, recursive_update

log = logging.getLogger(__name__)

PROJECT_INFO_FILE_SEARCH_PATHS = (
    ".utopya_project.yml",
    ".utopya-project.yml",
)
"""Potential names of project info files, relative to base directory"""

PROJECT_SCHEMA = (
    ("project_name", str, True),
    ("framework_name", str),
    ("paths", dict),
    ("metadata", dict),
    ("custom_py_modules", dict),
    ("output_files", dict),  # TODO needs sub-schema
    ("run_cfg_format", str),
    ("debug_level_updates", dict),  # TODO Implement... here or elsewhere?
)
"""Schema to use for an entry in the projects file, i.e.: a single project.

Note that some of the dict-like entries have additional schemas defined.
"""

PATHS_SCHEMA = (
    ("base_dir", str, True),
    ("project_info", str),
    ("models_dir", str),
    ("py_tests_dir", str),
    ("py_plots_dir", str),
    ("mv_project_cfg", str),
    ("project_base_plots", str),
)
"""Schema to use for a project's ``paths`` entry"""
# TODO What about the BatchTaskManager configuration?

METADATA_SCHEMA = (
    ("version", str),
    ("long_name", str),
    ("description", str),
    ("long_description", str),
    ("license", str),
    ("authors", list),
    ("email", str),
    ("website", str),
    ("utopya_compatibility", str),
    ("language", str),
    ("requirements", list),
    ("misc", dict),
)
"""Schema to use for a project's ``metadata`` entry"""


# -----------------------------------------------------------------------------


def load_projects() -> Dict[str, dict]:
    """Loads the project registry file"""
    return load_from_cfg_dir("projects")


def load_project(project_name: str) -> dict:
    """Load a specific project"""
    projects = load_projects()
    try:
        return projects[project_name]

    except KeyError as err:
        raise MissingProjectError(
            f"No project named '{project_name}' registered! "
            f"Available projects:  {', '.join(projects)}"
        ) from err


def register_project(
    *,
    base_dir: str,
    info_file: str = None,
    custom_project_name: str = None,
    require_matching_names: bool = None,
    exists_action: str = "raise",
    _log=log,
) -> dict:
    """Register or update information of an Utopia project, i.e. a repository
    that implements models.

    Args:
        base_dir (str): Project base directory
        info_file (str, optional): Path to info file which contains further
            path information and metadata (may be relative to base directory).
            If not given, will use some defaults to search for it.
        custom_project_name (str, optional): Custom project name, overwrites
            the one given in the info file
        require_matching_names (bool, optional): If set, will require that the
            custom project name is equal to the one given in the project info
            file. This allows checking that the file content does not diverge
            from some outside state.
        exists_action (str, optional): Action to take upon existing project
        _log (TYPE, optional): A logger-like object

    Returns:
        dict: Project information for the new or validated project
    """
    _log.info("Commencing project registration ...")

    # The project dict to populate, providing default values
    project = dict(
        project_name=None,
        paths=dict(),
        metadata=dict(),
        custom_py_modules=dict(),
        output_files=dict(),
        run_cfg_format="yaml",
    )

    # Parse base directory and info file; if not given, search for it
    base_dir = os.path.abspath(os.path.expanduser(base_dir))
    _log.remark("Project base directory:\n  %s", base_dir)

    if info_file:
        info_file = os.path.realpath(
            os.path.join(base_dir, os.path.expanduser(info_file))
        )
        _log.remark("Have project info file available:\n  %s", info_file)

    else:
        for _relpath in PROJECT_INFO_FILE_SEARCH_PATHS:
            _abspath = os.path.join(base_dir, _relpath)
            if os.path.isfile(_abspath):
                info_file = _abspath
                _log.remark("Found project info file:\n  %s", info_file)
                break

        else:
            _locs = "\n".join(
                f"  - {p}" for p in PROJECT_INFO_FILE_SEARCH_PATHS
            )
            raise ValueError(
                "Missing project info file!\n"
                "Either explicitly supply a path or add one at the following "
                f"search locations relative to the base directory:\n{_locs}"
            )

    # Load and parse the info file
    _log.note("Loading project information from file ...")

    project_info = dict(paths=dict(base_dir=base_dir))
    _project_info = load_yml(info_file)
    _project_info = _project_info if _project_info else {}

    # Warn if base_dir was given in info file; the base directory given
    # explicitly should always take precedence
    if _project_info.get("paths", {}).get("base_dir"):
        _log.caution(
            "The project info file contains a `paths.base_dir` entry, "
            "which will be ignored!"
        )

    project_info = recursive_update(_project_info, project_info)
    project_info["paths"]["project_info"] = info_file

    # Regularize paths, evaluating relative ones towards the base directory
    for path_name, path in project_info["paths"].items():
        if path_name in ("base_dir", "project_info"):
            continue

        project_info["paths"][path_name] = os.path.realpath(
            os.path.join(base_dir, path)
        )

    # May want to use a custom project name
    if custom_project_name:
        _project_name = project_info.get("project_name")
        if require_matching_names and custom_project_name != _project_name:
            raise ValueError(
                "The custom project name '{}' does not match the name given "
                "in the project info file, '{}'! Either ensure that the names "
                "match exactly or unset the `require_matching_names` flag."
                "".format(custom_project_name, project_info["project_name"])
            )

        project_info["project_name"] = custom_project_name
        _log.remark("Using a custom project name:  %s", custom_project_name)
        _log.remark(
            "Note that this creates a mismatch between the project "
            "info file and the registered project!"
        )

    # Now, load data into project dict, using the schemas and starting at the
    # root level. And then again for paths and metadata. After that, no longer
    # need the project_info; delete it to prohibit accidental usage
    _log.note("Parsing project information ...")
    load_selected_keys(
        project_info,
        add_to=project,
        keys=PROJECT_SCHEMA,
        err_msg_prefix="Failed loading (root-level) project information!",
    )
    load_selected_keys(
        project_info["paths"],
        add_to=project["paths"],
        keys=PATHS_SCHEMA,
        err_msg_prefix="Failed loading project `paths` entry!",
    )
    load_selected_keys(
        project_info.get("metadata", {}),
        add_to=project["metadata"],
        keys=METADATA_SCHEMA,
        err_msg_prefix="Failed loading project `metadata` entry!",
    )

    del project_info

    # Load existing project dict and compare
    project_name = project["project_name"]
    projects = load_projects()

    if project_name in projects:
        _log.remark("A project named '%s' already exists.", project_name)
        if exists_action == "raise":
            raise ValueError(
                f"A project named '{project_name}' already exists!\n"
                "Either use a different name or set the `exists_action` "
                "argument to 'validate', 'overwrite', or 'update'."
            )

        elif exists_action == "validate":
            _log.note(
                "Validating information against already existing project ..."
            )
            if projects[project_name] != project:
                # Generate a diff such that its clearer where they differ
                import difflib

                diff = "\n".join(
                    difflib.Differ().compare(
                        pformat(projects[project_name]).split("\n"),
                        pformat(project).split("\n"),
                    )
                )

                raise ValueError(
                    f"Validation of project '{project_name}' failed!\n"
                    "The to-be-added project information did not compare "
                    "equal to the already existing one for that project.\n"
                    "Either change the `exists_action` argument to "
                    "'overwrite' or 'update' or make sure the information is "
                    f"equal; their diff is as follows:\n\n{diff}"
                )

            _log.success("Validation of project '%s' succeeded.", project_name)
            return projects[project_name]

        elif exists_action == "overwrite":
            _log.note("Overwriting already existing project information ...")

        elif exists_action == "update":
            _log.note("Updating already existing project information ...")
            project = recursive_update(projects[project_name], project)

        else:
            raise ValueError(
                f"Invalid `exists_action` '{exists_action}'!\n"
                "Possible values:  raise, validate, update, overwrite"
            )

    # Update and store back
    projects[project_name] = project
    write_to_cfg_dir("projects", projects)
    _log.success("Successfully stored '%s' project information.", project_name)
    _log.remark(
        "NOTE: Changes to the project info file are *not* automatically "
        "tracked!\nTo update project information, repeat this procedure."
    )

    return projects[project_name]
