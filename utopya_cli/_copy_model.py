"""Implements functionality to copy relevant model files"""

import glob
import logging
import os
from typing import Callable, Dict, List, Sequence, Tuple

import click

log = logging.getLogger(__name__)

FILE_EXTENSIONS = {
    "c": (".c", ".h"),
    "c++": (".c", ".h", ".cc", ".hh", ".cpp"),
    "python": (".py", ".pyx"),
    "yaml": (".yml", ".yaml"),
}
"""A map of language-specific file extensions that are used for file search"""

LANGUAGE_ALIASES = {
    "cpp": "c++",
    "py": "python",
    "py2": "python",
    "py3": "python",
}
"""A map of language specifier aliases that can be used to find a normalized
language specifier"""

# -----------------------------------------------------------------------------


def abbrev_path(p: str) -> str:
    """Abbreviates a path by reversing expanduser and making a path absolute"""
    p = os.path.abspath(p)
    homedir = os.path.expanduser("~")
    if p.startswith(homedir):
        p = "~" + p[len(homedir) :]
    return p


def apply_replacements(
    s: str, *replacements: Sequence[Tuple[str, str]]
) -> str:
    """Applies multiple replacements onto the given string"""
    for replacement in replacements:
        s = s.replace(*replacement)
    return s


def create_file_map(
    *,
    source_dir: str,
    target_dir: str,
    abs_file_map: dict,
    replacements: Sequence[Tuple[str, str]],
    skip_exts: Sequence[str] = None,
    glob_args: Sequence[str] = ("**",),
) -> dict:
    """Given a file list with absolute paths, aggregates the file path
    changes into ``abs_file_map`` and gathers the relative file path
    changes into the returned dict.

    The file name is changed according to the specified replacements.

    Args:
        source_dir (str): The source directory to look for files in using
            glob and the ``glob_args``. Note that directories are not
            matched.
        target_dir (str): The target directory of the renamed files
        abs_file_map (dict): The mutable file map that the absolute file
            path changes are aggregated in.
        replacements (Sequence[Tuple[str, str]]): The replacement
            specifications, applied to the relative paths.
        glob_args (Sequence[str], optional): The glob arguments to match
            files within the source directory. By default, this matches
            all files, also down the source directory tree. The glob
            ``recursive`` option is enabled.

    Returns:
        dict: The file map relative to source and target dir.
    """
    files = glob.glob(os.path.join(source_dir, *glob_args), recursive=True)
    rel_file_map = dict()

    for fpath in files:
        if os.path.isdir(fpath) or not os.path.exists(fpath):
            continue

        if skip_exts and os.path.splitext(fpath)[1] in skip_exts:
            continue

        rel_fpath = os.path.relpath(fpath, start=source_dir)
        new_rel_fpath = apply_replacements(rel_fpath, *replacements)

        abs_file_map[fpath] = os.path.join(target_dir, new_rel_fpath)
        rel_file_map[rel_fpath] = new_rel_fpath

    return rel_file_map


def show_file_map(
    *,
    file_map: dict,
    source_dir: str,
    target_dir: str,
    desc: str,
    _log: logging.Logger = log,
):
    """Shows a human-readable version of the given (relative) file map
    which copies from the source directory tree to the target directory
    tree.
    """
    _log.progress(f"\n--- Found {len(file_map):d} {desc:s} files.")
    _log.note(f"Source directory:\n    {abbrev_path(source_dir)}\n")
    _log.note(f"Target directory:\n    {abbrev_path(target_dir)}\n")

    if not file_map:
        _log.remark(
            "No files found; check the file extensions and paths that are "
            "to be included.\n"
        )
        return

    max_key_len = min(max(len(k) for k in file_map), 32)
    files = "\n".join(
        "    {:{l:d}s}  ->  {:s}".format(k, v, l=max_key_len)
        for k, v in file_map.items()
    )

    _log.note(f"File mapping:\n{files}")


# .............................................................................


def add_model_to_cmakelists(
    *, fpath: str, new_name: str, dry_run: bool, _log: logging.Logger = log
):
    """Adds the relevant add_subdirectory command to the CMakeLists file
    at the specified path.

    Assumes an ascending alphabetical list of ``add_subdirectory`` commands
    and adds the new command at a suitable place.
    If no ``add_subdirectory`` command is found, inserts at the end.

    Args:
        fpath (str): The absolute path of the CMakeLists.txt file
        new_name (str): The new model name to add to it
        dry_run (bool): If true, will not write but show a preview instead
    """
    if not os.path.exists(fpath):
        _log.warning(
            f"No CMakeLists.txt file found in expected location:\n  {fpath}"
        )
        _log.remark("If you want CMake postprocessing, add a file there.")
        return

    # Read the file
    with open(fpath) as f:
        lines = f.readlines()

    # Find the line to add the add_subdirectory command at
    insert_idx = None
    i = 0
    for i, line in enumerate(lines):
        if not line.startswith("add_subdirectory"):
            continue

        insert_idx = i
        _model = line[len("add_subdirectory(") : -2]
        if _model.lower() > new_name.lower():
            break
    else:
        # Did not break
        if insert_idx is None:
            # No add_subdirectory found, insert at end of file
            _log.warning(
                "Found no add_subdirectory commands and thus do not know "
                "where to insert the add_subdirectory command for the copied "
                "model's subdirectory; inserting at the end of the file ..."
            )
            insert_idx = i
        else:
            # Insert behind the last add_subdirectory command
            insert_idx += 1

    lines.insert(insert_idx, f"add_subdirectory({new_name})\n")

    if not dry_run:
        _log.remark("Now writing ...")
        with open(fpath, "w") as f:
            f.writelines(lines)

        _log.progress(
            f"add_subdirectory('{new_name}') added to\n"
            f"   {abbrev_path(fpath)}"
        )

    else:
        _log.note(
            "This is a dry run.\nThe following is a preview of how the new\n"
            f"   {abbrev_path(fpath)}\n"
            "file _would_ look like:\n"
        )
        _log.info("-" * 79 + "\n")
        _log.info("".join(lines))
        _log.info("-" * 79)


def postprocess_copied_model(
    *,
    new_name: str,
    info_bundle,
    target_project,
    dry_run: bool,
    file_map: str,
    impl_target_dir: str,
    _log: logging.Logger = log,
    # TODO Should pass information in a more general form here
    #
    # User-controlled parameters
    enabled: bool = True,
    cmake: dict = None,
):
    """Performs postprocessing routines, e.g. file adaptations that embed the
    copied model into the build system."""
    _log.hilight("\nPostprocessing copied model ...\n")
    if not enabled:
        _log.remark("Post-processing routines were disabled.")
        return

    # .. CMake-related stuff ..................................................
    cmake = cmake if cmake else {}
    cmake_enabled = cmake.get("enabled", "auto")
    if cmake_enabled == "auto":
        if any(p.endswith("CMakeLists.txt") for p in file_map.values()):
            cmake_enabled = True
            _log.note(
                "Found CMakeLists.txt file in file map, thus auto-enabling "
                "CMake postprocessing routine."
            )
            _log.remark(
                "Set postprocessing.cmake.enabled to False to suppress this."
            )
        else:
            cmake_enabled = False

    if cmake_enabled:
        cmakelists_fpath = os.path.abspath(
            os.path.join(impl_target_dir, "../CMakeLists.txt")
        )

        _log.progress(
            "Inserting add_subdirectory command for model directory ..."
        )
        add_model_to_cmakelists(
            fpath=cmakelists_fpath,
            new_name=new_name,
            dry_run=dry_run,
            _log=_log,
        )

    _log.success("\nFinished post-processing the copied model.")


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------


def copy_model_files(
    *,
    model_name: str,
    label: str = None,
    new_name: str = None,
    target_project: str = None,
    skip_exts: Sequence[str] = None,
    dry_run: bool = False,
    prompts_confirmed: bool = False,
    raise_exc: bool = False,
    postprocess: dict = None,
    _log: logging.Logger = log,
) -> None:
    """A helper function to conveniently copy model-related files, rename them,
    and adjust their content to the new name as well.

    Args:
        model_name (str): The name of the model to copy
        new_name (str, optional): The new name of the model. This may not
            conflict with any already existing model name in the model
            registry.
        target_project (str, optional): The name of the project to copy the
            model to. It needs to be a registered Utopia project.
        add_to_cmakelists (bool, optional): Whether to add the new model to the
            corresponding CMakeLists.txt file.
        dry_run (bool, optional): If given, no write or copy operations will be
            carried out.

    Raises:
        ValueError: Upon bad arguments
    """
    from utopya import MODELS, PROJECTS
    from utopya.model_registry import get_info_bundle

    _indent = " " * 3

    def handle_exc(exc: Exception, desc: str):
        """A little exception handler function for read/write errors"""
        _log.error(f"{_indent}{desc} failed with {type(exc).__name__}: {exc}.")
        if raise_exc:
            _log.remark("Unset --debug flag to ignore error and continue.")
            raise

        _log.remark(
            f"{_indent}If you want this file copied and refactored, "
            "you will have to do it manually."
        )
        _log.remark("Set --debug flag to raise instead of continuing.")

    # Gather information on model, project, and replacements . . . . . . . . .
    # Get the model information
    info_bundle = get_info_bundle(model_name=model_name, bundle_label=label)
    _log.info(
        f"\nModel selected to copy:      {info_bundle.model_name}  "
        f"(from project: {info_bundle.project_name})"
    )

    # Check if the name is not already taken, being case-insensitive
    _log.info(f"Name of the new model:       {new_name}")

    if new_name.lower() in [n.lower() for n in MODELS.keys()]:
        _avail = ", ".join(MODELS.keys())
        raise ValueError(
            f"A model with name '{new_name}' is already registered! "
            "Make sure that the name is unique. If you keep receiving this "
            "error despite no other model with this name being implemented, "
            "remove the entry from the model registry, e.g. via the "
            "`utopya models rm` CLI command.\n"
            f"Already registered models: {_avail}"
        )

    # Find out about the project that the files are copied _to_
    _log.info(f"Project to copy to:          {target_project}")
    target_project = PROJECTS[target_project]

    # Determine replacements
    replacements = [
        (model_name, new_name),
        (model_name.lower(), new_name.lower()),
        (model_name.upper(), new_name.upper()),
    ]

    # Generate the file maps . . . . . . . . . . . . . . . . . . . . . . . . .
    _log.hilight("\nSearching for files to copy ...")

    # Prepare file extension skipping
    skip_exts = [e if e.startswith(".") else f".{e}" for e in skip_exts]
    _log.remark(
        f"File extensions that are skipped:\n    {' '.join(skip_exts)}\n"
    )

    # The mapping of all files that are to be copied and in which the content
    # is to be replaced. It maps absolute source file paths to absolute target
    # file paths.
    file_map = dict()

    # Relative file maps, created below
    impl_file_map = dict()
    py_t_file_map = dict()
    py_p_file_map = dict()

    # Find out the target directories
    target_models_dir = target_project.paths.get("models_dir")
    target_py_t_dir = target_project.paths.get("py_tests_dir")
    target_py_p_dir = target_project.paths.get("py_plots_dir")

    # Define the source and target directory paths of the implementation and
    # the python-related files, if the path information is available.
    impl_source_dir = info_bundle.paths["source_dir"]
    impl_target_dir = os.path.join(target_models_dir, new_name)
    impl_file_map = create_file_map(
        source_dir=impl_source_dir,
        target_dir=impl_target_dir,
        abs_file_map=file_map,
        replacements=replacements,
        skip_exts=skip_exts,
    )

    if target_py_t_dir and info_bundle.paths.get("py_tests_dir"):
        py_t_source_dir = info_bundle.paths["py_tests_dir"]
        py_t_target_dir = os.path.join(target_py_t_dir, new_name)
        py_t_file_map = create_file_map(
            source_dir=py_t_source_dir,
            target_dir=py_t_target_dir,
            abs_file_map=file_map,
            replacements=replacements,
            skip_exts=skip_exts,
        )
    else:
        _log.note(
            f"Model '{model_name}' and/or target project "
            f"'{target_project.name}' do not define a 'py_tests_dir' "
            "directory."
        )

    if target_py_p_dir and info_bundle.paths.get("py_plots_dir"):
        py_p_source_dir = info_bundle.paths["py_plots_dir"]
        py_p_target_dir = os.path.join(target_py_p_dir, new_name)
        py_p_file_map = create_file_map(
            source_dir=py_p_source_dir,
            target_dir=py_p_target_dir,
            abs_file_map=file_map,
            replacements=replacements,
            skip_exts=skip_exts,
        )
    else:
        _log.note(
            f"Model '{model_name}' and/or target project "
            f"'{target_project.name}' do not define a 'py_plots_dir' "
            "directory."
        )

    # Gathered all information now. . . . . . . . . . . . . . . . . . . . . . .
    # Inform about the file changes and the replacement in them.
    show_file_map(
        file_map=impl_file_map,
        desc="model implementation",
        source_dir=impl_source_dir,
        target_dir=impl_target_dir,
        _log=_log,
    )

    if py_t_file_map:
        show_file_map(
            file_map=py_t_file_map,
            desc="python model test",
            source_dir=py_t_source_dir,
            target_dir=py_t_target_dir,
            _log=_log,
        )

    if py_p_file_map:
        show_file_map(
            file_map=py_p_file_map,
            desc="python model plot",
            source_dir=py_p_source_dir,
            target_dir=py_p_target_dir,
            _log=_log,
        )

    if not file_map:
        _log.caution("No files found to copy! Not continuing ...")
        return

    max_repl_len = max(len(rs) for rs, _ in replacements)
    repl_info = [
        "    '{:{l:d}s}'  ->  '{:s}'".format(*repl, l=max_repl_len)
        for repl in replacements
    ]
    _repl_info = "\n".join(repl_info)
    _log.info(
        f"\nInside all of these {len(file_map):d} files, the following string "
        "replacements will be carried out:"
    )
    _log.note(f"{_repl_info}\n")

    # Inform about further procedure and prompt confirmation
    _log.progress("Ready for copying now.\n")
    if dry_run:
        _log.hilight("--- THIS IS A DRY RUN. ---")
        _log.remark("Copy and write operations below are NOT operational.\n")
    else:
        _log.caution("This is not a drill.")
        _log.remark(
            "If you want to see the effect of copying first, "
            "consider making a dry-run by setting the --dry-run CLI flag.\n"
        )

    if not prompts_confirmed and not click.confirm("Proceed?"):
        _log.caution("Not proceeding.")
        return

    _log.hilight("\nCopying and refactoring ...")

    # Now, the actual copying . . . . . . . . . . . . . . . . . . . . . . . . .
    for i, (src_fpath, target_fpath) in enumerate(file_map.items()):
        _log.progress(f"\nFile {i + 1:d}/{len(file_map):d} ...")
        _log.remark(
            f"{_indent}   {abbrev_path(src_fpath):s}\n"
            f"{_indent}-> {abbrev_path(target_fpath):s}"
        )

        try:
            with open(src_fpath) as src_file:
                src_lines = src_file.read()

        except Exception as exc:
            handle_exc(exc, "Reading")
            continue

        target_lines = apply_replacements(src_lines, *replacements)

        if dry_run:
            continue

        # Create directories and write the file; failing if it already exists
        os.makedirs(os.path.dirname(target_fpath), exist_ok=True)
        try:
            with open(target_fpath, mode="x") as target_file:
                target_file.write(target_lines)

        except Exception as exc:
            handle_exc(exc, "Copying")
            continue

    _log.success("\nFinished copying and refactoring.")
    if dry_run:
        _log.remark("Reminder: This is a dry run. No copying happened.")

    # Invoke postprocessing, which may also be disabled
    postprocess_copied_model(
        new_name=new_name,
        info_bundle=info_bundle,
        target_project=target_project,
        file_map=file_map,
        impl_target_dir=impl_target_dir,
        dry_run=dry_run,
        _log=_log,
        **(postprocess if postprocess else {}),
    )

    if dry_run:
        _log.hilight(f"\nDry-run for copying '{model_name}' model finished.")
        _log.remark("To actually copy files, unset the --dry-run flag.")
    else:
        _log.hilight(f"\nSuccessfully copied the '{model_name}' model.")
        _log.remark("Hint: Use `utopya models register` to register it.")
