"""Implementation of the utopya project registry"""

import copy
import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from pydantic import DirectoryPath, FilePath

from ._yaml_registry import BaseSchema, RegistryEntry, YAMLRegistry
from .cfg import PROJECT_INFO_FILE_SEARCH_PATHS, UTOPYA_CFG_SUBDIRS
from .tools import load_yml, pformat, recursive_update

log = logging.getLogger(__name__)

# -- Schema definition --------------------------------------------------------
# .. Sub-schemas ..............................................................


class ProjectPaths(BaseSchema):
    """Schema to use for a project's ``paths`` field"""

    base_dir: DirectoryPath
    project_info: Optional[FilePath]
    models_dir: Optional[DirectoryPath]
    py_tests_dir: Optional[DirectoryPath]
    py_plots_dir: Optional[DirectoryPath]
    mv_project_cfg: Optional[FilePath]
    project_base_plots: Optional[FilePath]

    # TODO What about the BatchTaskManager configuration?


class ProjectMetadata(BaseSchema):
    """Schema to use for a project's ``metadata`` field"""

    version: Optional[str]
    long_name: Optional[str]
    description: Optional[str]
    long_description: Optional[str]
    license: Optional[str]
    authors: Optional[List[str]]
    email: Optional[str]
    website: Optional[str]
    utopya_compatibility: Optional[str]
    language: Optional[str]
    requirements: Optional[List[str]]
    misc: Optional[Dict[str, Any]]


class ProjectSettings(BaseSchema):
    """Schema to use for a project's ``settings`` field"""

    preload_project_py_plots: Optional[bool]
    """Whether to preload the project-level plot module (``py_plots_dir``)
    after initialization of the :py:mod:`~utopya.eval.plotmanager.PlotManager`.
    If not given, will load the module.
    """

    preload_framework_py_plots: Optional[bool]
    """Whether to preload the framework-level plot module (``py_plots_dir``)
    after initialization of the :py:mod:`~utopya.eval.plotmanager.PlotManager`.
    If not given, will load the module.
    """


# .............................................................................


class ProjectSchema(BaseSchema):
    """The data model for a project registry entry"""

    project_name: str
    framework_name: Optional[str]
    paths: ProjectPaths
    metadata: ProjectMetadata
    settings: ProjectSettings = {}
    run_cfg_format: str = "yaml"
    cfg_set_abs_search_dirs: Optional[List[str]]
    cfg_set_model_source_subdirs: Optional[List[str]]
    custom_py_modules: Optional[Dict[str, DirectoryPath]]
    output_files: Optional[dict]  # TODO Needs sub-schema
    debug_level_updates: Optional[Dict[str, dict]]  # TODO Implement


# -- Project ------------------------------------------------------------------


class Project(RegistryEntry):
    """A registry entry that describes a project"""

    SCHEMA = ProjectSchema

    @property
    def framework_project(self) -> Optional["Project"]:
        """If a framework project is defined, retrieve it from the registry"""
        if not self.framework_name:
            return None

        from . import PROJECTS

        return PROJECTS[self.framework_name]

    def get_git_info(self, *, include_patch_info: bool = False) -> dict:
        """Returns information about the state of this project's git repository
        using the ``python-git-info`` package.

        If no git information is retrievable, e.g. because the project's
        ``base_dir`` does not contain a git repository, will still return a
        dict but with ``have_git_info`` entry set to False.

        Otherwise the git information will be in the ``latest_commit`` entry.

        Args:
            include_patch_info (bool, optional): If True, will attempt a
                subprocess call to ``git`` and store patch information
                alongside in the ``diff`` entry. In that case, the ``dirty``
                entry will denote whether there were uncommitted changes.

        Returns:
            dict: A dict containing information about the associated git repo.
        """
        import subprocess

        import gitinfo  # PyPI package `python-git-info`

        base_dir = str(self.paths.base_dir)
        sp_kws = dict(cwd=base_dir, capture_output=True, text=True)

        d = dict(
            project_name=self.project_name,
            project_base_dir=base_dir,
            have_git_repo=False,
            latest_commit=None,
            dirty="unknown",
            git_status=[],
            git_diff="",
        )

        # Get git information (without requiring git)
        info = gitinfo.get_git_info(base_dir)
        if info:
            d["have_git_repo"] = True
            d["latest_commit"] = info

        if info and include_patch_info:
            # Attempt subprocess git calls to find out more.
            # Make sure these commands work in the first place.
            try:
                git_status = subprocess.run(
                    ["git", "status", "--short"], **sp_kws, check=True
                )

            except Exception as exc:
                log.caution(
                    "Failed retrieving git patch information for "
                    f"{self.project_name} because git invocation via a python "
                    f"subprocess failed:\n\n{type(exc).__name__}: {exc}"
                )

            else:
                # git command works, can store information
                # git status
                git_status_stdout = git_status.stdout.strip()
                if git_status_stdout:
                    d["git_status"] = [
                        f.split(" ", 1) for f in git_status_stdout.split("\n")
                    ]

                # git diff
                git_diff_p = subprocess.run(["git", "diff", "-p"], **sp_kws)
                d["git_diff"] = git_diff_p.stdout.strip()

                # ... whether the repo has uncommitted changes
                git_diff = subprocess.run(["git", "diff", "--quiet"], **sp_kws)
                d["dirty"] = git_diff.returncode != 0

        return d


# -- ProjectRegistry ----------------------------------------------------------


class ProjectRegistry(YAMLRegistry):
    """The project registry"""

    def __init__(self, registry_dir: str = None):
        """Initializes the project registry, loading available entries from
        the registry directory in the utopya config directory.

        This also creates the ``projects`` directory, if not created yet.

        Args:
            registry_dir (str, optional): A custom projects
        """

        if registry_dir is None:
            registry_dir = UTOPYA_CFG_SUBDIRS["projects"]

        if not os.path.exists(registry_dir):
            os.makedirs(registry_dir)

        super().__init__(Project, registry_dir=registry_dir)

    def register(
        self,
        *,
        base_dir: str,
        info_file: str = None,
        custom_project_name: str = None,
        require_matching_names: bool = None,
        exists_action: str = "raise",
    ) -> dict:
        """Register or update information of a project.

        Args:
            base_dir (str): Project base directory
            info_file (str, optional): Path to info file which contains further
                path information and metadata (may be relative to base
                directory). If not given, will use some defaults to search for
                it.
            custom_project_name (str, optional): Custom project name,
                overwrites the one given in the info file
            require_matching_names (bool, optional): If set, will require that
                the custom project name is equal to the one given in the
                project info file. This allows checking that the file content
                does not diverge from some outside state.
            exists_action (str, optional): Action to take upon existing project

        Returns:
            dict: Project information for the new or validated project
        """
        log.info("Commencing project registration ...")

        # Parse base directory and info file; if not given, search for it
        base_dir = os.path.abspath(os.path.expanduser(base_dir))
        log.remark("Project base directory:\n  %s", base_dir)

        if info_file:
            info_file = os.path.realpath(
                os.path.join(base_dir, os.path.expanduser(info_file))
            )
            log.remark("Have project info file available:\n  %s", info_file)

        else:
            for _relpath in PROJECT_INFO_FILE_SEARCH_PATHS:
                _abspath = os.path.join(base_dir, _relpath)
                if os.path.isfile(_abspath):
                    info_file = _abspath
                    log.remark("Found project info file:\n  %s", info_file)
                    break

            else:
                _locs = "\n".join(
                    f"  - {p}" for p in PROJECT_INFO_FILE_SEARCH_PATHS
                )
                raise ValueError(
                    "Missing project info file!\nEither explicitly supply a "
                    "path or add one at the following search locations "
                    f"relative to the base directory:\n{_locs}"
                )

        # Load and parse the info file
        log.note("Loading project information from file ...")

        project_info = dict(paths=dict(base_dir=base_dir))
        _project_info = load_yml(info_file)
        _project_info = _project_info if _project_info else {}

        # Warn if base_dir was given in info file; the base directory given
        # explicitly should always take precedence
        if _project_info.get("paths", {}).get("base_dir"):
            log.caution(
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
                    "The custom project name '{}' does not match the name "
                    "given in the project info file, '{}'! "
                    "Either ensure that the names match exactly or unset the "
                    "`require_matching_names` flag.".format(
                        custom_project_name, project_info["project_name"]
                    )
                )

            project_info["project_name"] = custom_project_name
            log.remark("Using a custom project name:  %s", custom_project_name)
            log.remark(
                "Note that this creates a mismatch between the project "
                "info file and the registered project!"
            )

        # Now, create a registry entry from it
        log.note(
            "Preparing to add entry (exists_action: %s) ...", exists_action
        )
        project_name = project_info["project_name"]

        project = self.add_entry(
            project_name, exists_action=exists_action, **project_info
        )

        log.success(
            "Successfully stored or updated '%s' project information.",
            project_name,
        )
        log.remark(
            "NOTE: Changes to the project info file are *not* automatically "
            "tracked!\nTo update project information, repeat this procedure."
        )

        return self[project_name]


# -----------------------------------------------------------------------------

PROJECTS = ProjectRegistry()
"""The package-wide project registry"""
