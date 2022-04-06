"""Implements functionality to copy relevant model files"""

import glob
import os
from typing import Callable, Dict, List, Sequence, Tuple

FILE_EXTENSIONS = {
    "c": (
        ".c",
        ".h",
    ),
    "c++": (".c", ".h", ".cc", ".hh", ".cpp"),
    "python": (".py", ".pyx"),
    "yaml": (".yml", ".yaml"),
}
"""A map of language-specific file extensions"""

LANGUAGE_ALIASES = {
    "cpp": "c++",
    "py": "python",
    "py2": "python",
    "py3": "python",
}
"""A map of language specifier aliases that can be used to find a normalized
language specifier"""

# -----------------------------------------------------------------------------


def copy_model_files(
    *,
    model_name: str,
    new_name: str = None,
    target_project: str = None,
    add_to_cmakelists: bool = True,
    skip_exts: Sequence[str] = None,
    use_prompts: bool = True,
    dry_run: bool = False,
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
        use_prompts (bool, optional): Whether to interactively prompt for
            confirmation or missing arguments.
        dry_run (bool, optional): If given, no write or copy operations will be
            carried out.

    Raises:
        ValueError: Upon bad arguments

    Returns:
        None
    """
    # FIXME Only import needed ones!
    from utopya import MODELS as _MODELS
    from utopya.cfg import load_from_cfg_dir, write_to_cfg_dir
    from utopya.model_registry import get_info_bundle as _get_info_bundle
    from utopya.multiverse import Multiverse
    from utopya.tools import add_item, recursive_update

    def apply_replacements(s, *replacements: Sequence[Tuple[str, str]]) -> str:
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

    def print_file_map(
        *, file_map: dict, source_dir: str, target_dir: str, label: str
    ):
        """Prints a human-readable version of the given (relative) file map
        which copies from the source directory tree to the target directory
        tree.
        """
        max_key_len = min(max(len(k) for k in file_map), 32)
        files = [
            "\t{:{l:d}s}  ->  {:s}".format(k, v, l=max_key_len)
            for k, v in file_map.items()
        ]

        print(
            "\nThe following {num:d} {label:s} files from\n\t{from_dir:}\n"
            "will be copied to\n\t{to_dir:}\nusing the following new file "
            "names:\n{files:}"
            "".format(
                num=len(file_map),
                label=label,
                from_dir=source_dir,
                to_dir=target_dir,
                files="\n".join(files),
            )
        )

    def add_model_to_cmakelists(*, fpath: str, new_name: str, write: bool):
        """Adds the relevant add_subdirectory command to the CMakeLists file
        at the specified path.

        Assumes an ascending alphabetical list of add_subdirectory commands
        and adds the new command at a suitable place.

        Args:
            fpath (str): The absolute path of the CMakeLists.txt file
            new_name (str): The new model name to add to it
            write (bool): If false, will not write.

        Raises:
            ValueError: On missing ``add_subdirectory`` command in the given
                file. In this case, the line has to be added manually.
        """
        # Read the file
        with open(fpath) as f:
            lines = f.readlines()

        # Find the line to add the add_subdirectory command at
        insert_idx = None
        for i, line in enumerate(lines):
            if not line.startswith("add_subdirectory"):
                continue

            insert_idx = i
            _model = line[len("add_subdirectory(") : -2]
            if _model.lower() > new_name.lower():
                break
        else:
            # Did not break. Insert behind the last add_subdirectory command
            insert_idx += 1

        if insert_idx is None:
            raise ValueError(
                "Found no add_subdirectory commands and thus do "
                "not know where to insert the command for the "
                "new model directory; please do it manually in "
                f"the following file:  {fpath}"
            )

        lines.insert(
            insert_idx if insert_idx else last_add_subdir_idx + 1,
            f"add_subdirectory({new_name})\n",
        )

        if write:
            with open(fpath, "w") as f:
                f.writelines(lines)

            print(f"Subdirectory for model '{new_name}' added to\n\t{fpath}")

        else:
            print(
                f"Not writing. Preview of how the new\n\t{fpath}\n"
                "file _would_ look like:"
            )
            print("-" * 79 + "\n")
            print("".join(lines))
            print("-" * 79)

    # Gather information on model, project, and replacements . . . . . . . . .
    # Get the model information
    info_bundle = _get_info_bundle(model_name=model_name)
    print(
        f"\nModel selected to copy:     {info_bundle.model_name}  "
        f"(from project: {info_bundle.project_name})"
    )

    # Find out the new name
    if not new_name:
        if not use_prompts:
            raise ValueError("Missing new_name argument!")
        try:
            new_name = input("\nWhat should be the name of the NEW model?  ")
        except KeyboardInterrupt:
            return

    # Check if the name is not already taken, being case-insensitive
    if new_name.lower() in [n.lower() for n in _MODELS.keys()]:
        _avail = ", ".join(_MODELS.keys())
        raise ValueError(
            f"A model with name '{new_name}' is already registered! "
            "Make sure that the name is unique. If you keep "
            "receiving this error despite no other model with "
            "this name being implemented, remove the entry from "
            "the model registry, e.g. via the `utopia models rm` "
            "CLI command.\n"
            f"Already registered models: {_avail}"
        )

    print(f"Name of the new model:      {new_name}")

    # Define the replacements
    replacements = [
        (model_name, new_name),
        (model_name.lower(), new_name.lower()),
        (model_name.upper(), new_name.upper()),
    ]

    # Find out the project that the files are copied _to_
    projects = load_from_cfg_dir("projects")

    if not target_project:
        if not use_prompts:
            raise ValueError("Missing target_project argument!")
        try:
            target_project = input(
                f"\nWhich Utopia project (available: {', '.join(projects)}) "
                "should the model be copied to?  "
            )
        except KeyboardInterrupt:
            return
    print(f"Utopia project to copy to:  {target_project}")

    project_info = projects.get(target_project)
    if not project_info:
        raise ValueError(
            f"No Utopia project with name '{target_project}' is known to the "
            "frontend. Check the spelling and note that the "
            "project name is case-sensitive.\n"
            f"Available projects: {', '.join(projects)}."
        )

    # Generate the file maps . . . . . . . . . . . . . . . . . . . . . . . . .
    # The mapping of all files that are to be copied and in which the content
    # is to be replaced. It maps absolute source file paths to absolute target
    # file paths.
    file_map = dict()

    # Relative file maps, created below
    impl_file_map = None
    py_t_file_map = None
    py_p_file_map = None

    # Find out the target directories
    target_models_dir = project_info.get("models_dir")
    target_py_t_dir = project_info.get("python_model_tests_dir")
    target_py_p_dir = project_info.get("python_model_plots_dir")

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

    if target_py_t_dir and info_bundle.paths.get("python_model_tests_dir"):
        py_t_source_dir = info_bundle.paths["python_model_tests_dir"]
        py_t_target_dir = os.path.join(target_py_t_dir, new_name)
        py_t_file_map = create_file_map(
            source_dir=py_t_source_dir,
            target_dir=py_t_target_dir,
            abs_file_map=file_map,
            replacements=replacements,
            skip_exts=skip_exts,
        )

    if target_py_p_dir and info_bundle.paths.get("python_model_plots_dir"):
        py_p_source_dir = info_bundle.paths["python_model_plots_dir"]
        py_p_target_dir = os.path.join(target_py_p_dir, new_name)
        py_p_file_map = create_file_map(
            source_dir=py_p_source_dir,
            target_dir=py_p_target_dir,
            abs_file_map=file_map,
            replacements=replacements,
            skip_exts=skip_exts,
        )

    # Gathered all information now. . . . . . . . . . . . . . . . . . . . . . .
    # Inform about the file changes and the replacement in them.
    print_file_map(
        file_map=impl_file_map,
        label="model implementation",
        source_dir=impl_source_dir,
        target_dir=impl_target_dir,
    )

    if py_t_file_map:
        print_file_map(
            file_map=py_t_file_map,
            label="python model test",
            source_dir=py_t_source_dir,
            target_dir=py_t_target_dir,
        )

    if py_p_file_map:
        print_file_map(
            file_map=py_p_file_map,
            label="python model plot",
            source_dir=py_p_source_dir,
            target_dir=py_p_target_dir,
        )

    max_repl_len = max(len(rs) for rs, _ in replacements)
    repl_info = [
        "\t'{:{l:d}s}'  ->  '{:s}'".format(*repl, l=max_repl_len)
        for repl in replacements
    ]
    _repl_info = "\n".join(repl_info)
    print(
        f"\nInside all of these {len(file_map):d} files, the following string "
        f"replacements will be carried out:\n{_repl_info}\n"
    )

    # Inform about dry run and ask whether to proceed
    if dry_run:
        print("--- THIS IS A DRY RUN. ---")
        print("Copy and write operations below are not operational.")

    if use_prompts:
        try:
            response = input("\nProceed [y/N]  ")
        except KeyboardInterrupt:
            response = "N"
        if response.lower() not in ("y", "yes"):
            print("\nNot proceeding ...")
            return

    print("\nNow copying and refactoring ...")

    # Now, the actual copying . . . . . . . . . . . . . . . . . . . . . . . . .
    for i, (src_fpath, target_fpath) in enumerate(file_map.items()):
        print(f"\nFile {i + 1:d}/{len(file_map):d} ...")
        print(f"\t   {src_fpath:s}\n\t-> {target_fpath:s}")

        try:
            with open(src_fpath) as src_file:
                src_lines = src_file.read()

        except Exception as exc:
            print(f"\tReading FAILED due to {type(exc).__name__}: {str(exc)}.")
            print(
                "\tIf you want this file copied and refactored, you will "
                "have to do it manually."
            )
            continue

        target_lines = apply_replacements(src_lines, *replacements)

        if dry_run:
            continue

        # Create directories and write the file; failing if it already exists
        os.makedirs(os.path.dirname(target_fpath), exist_ok=True)
        with open(target_fpath, mode="x") as target_file:
            target_file.write(target_lines)

    print("\nFinished copying.\n")

    # Prepare for CMakeLists.txt adjustments
    cmakelists_fpath = os.path.abspath(
        os.path.join(impl_target_dir, "../CMakeLists.txt")
    )

    if not add_to_cmakelists:
        print("Not extending CMakeLists.txt automatically.")
        print(
            "Remember to register the new model in the relevant "
            f"CMakeLists.txt file at\n\t{cmakelists_fpath}\n"
            "and invoke CMake to reconfigure."
        )
        return

    print("Adding model directory to CMakeLists.txt ...")
    add_model_to_cmakelists(
        fpath=cmakelists_fpath, new_name=new_name, write=not dry_run
    )

    print("\nFinished.")
