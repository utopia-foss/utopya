"""Methods needed to implement the utopia command line interface"""

import argparse
import glob
import logging
import os
import re
import readline
from typing import Callable, Dict, List, Sequence, Tuple

from pkg_resources import resource_filename

from . import MODELS as _MODELS
from .cfg import load_from_cfg_dir, write_to_cfg_dir
from .model_registry import get_info_bundle as _get_info_bundle
from .multiverse import Multiverse
from .tools import add_item, recursive_update

log = logging.getLogger(__name__)

USER_CFG_HEADER_PATH = resource_filename("utopya", "cfg/user_cfg_header.yml")
"""Where the user config header prefix is stored"""

BASE_CFG_PATH = resource_filename("utopya", "cfg/base_cfg.yml")
"""Where to find the utopya base configuration"""


class ANSIesc:
    """Some selected ANSI escape codes; usable in format strings"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


# -----------------------------------------------------------------------------


def add_from_kv_pairs(
    *pairs,
    add_to: dict,
    attempt_conversion: bool = True,
    allow_eval: bool = False,
    allow_deletion: bool = True,
) -> None:
    """Parses the key=value pairs and adds them to the given dict.

    .. note::

        This happens directly on the ``add_to`` object, i.e. making use of the
        mutability of the given dict. This function has no return value!

    Args:
        *pairs: Sequence of key=value strings
        add_to (dict): The dict to add the pairs to
        attempt_conversion (bool, optional): Whether to attempt converting the
            strings to bool, float, int types
        allow_eval (bool, optional): Whether to try calling eval() on the
            value strings during conversion
        allow_deletion (bool, optional): If set, can pass a ``DELETE`` string
            to a key to remove the corresponding entry.
    """

    class _DEL:
        """Objects of this class symbolize deletion"""

    DEL = _DEL()

    def conversions(val):
        # Boolean
        if val.lower() in ("true", "false"):
            return bool(val.lower() == "true")

        # None
        if val.lower() == "null":
            return None

        # Floating point number (requiring '.' being present)
        if re.match(r"^[-+]?[0-9]*\.[0-9]*([eE][-+]?[0-9]+)?$", val):
            try:
                return float(val)
            except:
                pass

        # Integer
        if re.match(r"^[-+]?[0-9]+$", val):
            try:
                return int(val)
            except:  # very unlike to be reached; regex is quite restrictive
                pass

        # Deletion placeholder
        if val == "DELETE":
            return DEL

        # Last resort, if activated: eval
        if allow_eval:
            try:
                return eval(val)
            except:
                pass

        # Just return the string
        return val

    log.debug("Adding entries from key-value pairs ...")

    # Go over all pairs and add them to the given base dict
    for kv in pairs:
        # Split key and value
        key, val = kv.split("=")

        # Process the key
        key_sequence = key.split(".")
        traverse_keys, last_key = key_sequence[:-1], key_sequence[-1]

        # Set temporary variable to root dict
        d = add_to

        # Traverse through the key sequence, if available
        for _key in traverse_keys:
            # Check if a new entry is needed
            if _key not in d:
                d[_key] = dict()

            # Select the new entry
            d = d[_key]

        # Attempt conversion
        if attempt_conversion:
            val = conversions(val)

        # In all cases but that where the value is the DEL object, write:
        if val is not DEL:
            d[last_key] = val
            continue

        # Otherwise: need to check whether deletion is allowed and the entry
        # is present ...
        if not allow_deletion:
            raise ValueError(
                f"Attempted deletion of value for key '{key}', but "
                "deletion is not allowed."
            )

        if last_key not in d:
            continue
        del d[last_key]

    # No need to return the base dict as it is a mutable!
    log.debug("Added %d entries from key-value pairs.", len(pairs))


def register_models(args, *, registry):
    """Handles registration of multiple models given argparse args"""
    # If there is project info to be updated, do so
    project_info = None
    if args.update_project_info:
        project_info = register_project(args, arg_prefix="project_")

    # The dict to hold all model info bundle arguments
    specs = dict()

    if not args.separator:
        # Will only register a single model.
        # Gather all the path-related arguments
        # TODO
        raise NotImplementedError(
            "Registering a single model is currently "
            "not possible via the CLI!"
        )

    else:
        # Got separator for lists of model names, binary paths, and source dirs
        log.debug(
            "Splitting given model registration arguments by '%s' ...",
            args.separator,
        )

        model_names = args.model_name.split(args.separator)
        executables = args.executable.split(args.separator)
        source_dirs = args.source_dir.split(args.separator)

        if not (len(model_names) == len(executables) == len(source_dirs)):
            raise ValueError(
                "Mismatch of sequence lengths during batch model "
                "registration! The model_name, executable, and source_dir "
                "lists should all be of equal length after having been split "
                f"by separator '{args.separator}', but were: {model_names}, "
                f"{executables}, and {source_dirs}, respectively."
            )
        # TODO Will ignore other path-related arguments! Warn if given.

        # Go over them, create the paths dict, and populate specs dict.
        # If there is project info given, use it to extend path information
        # with the python-related directories. Only do so if they exist.
        for model_name, executable, source_dir in zip(
            model_names, executables, source_dirs
        ):
            paths = dict(
                source_dir=source_dir,
                executable=executable,
                base_source_dir=args.base_source_dir,
                base_executable_dir=args.base_executable_dir,
            )

            if project_info:
                for _k in ("python_model_tests_dir", "python_model_plots_dir"):
                    _path = os.path.join(project_info[_k], model_name)
                    if os.path.isdir(_path):
                        paths[_k] = _path

            specs[model_name] = dict(
                paths=paths, project_name=args.project_name
            )

    log.debug(
        "Received registry parameters for %d model%s.",
        len(specs),
        "s" if len(specs) != 1 else "",
    )

    # Now, actually register. Here, pass along the common arguments.
    for model_name, bundle_kwargs in specs.items():
        registry.register_model_info(
            model_name,
            **bundle_kwargs,
            exists_action=args.exists_action,
            label=args.label,
            overwrite_label=args.overwrite_label,
        )

    log.info("Model registration finished.\n\n%s\n", registry.info_str)


def register_project(args: list, *, arg_prefix: str = "") -> dict:
    """Register or update information of an Utopia project, i.e. a repository
    that implements models.

    Args:
        args (list): The CLI arguments object
        arg_prefix (str, optional): The prefix to use when using attribute
            access to these arguments. Useful if the names as defined in the
            CLI are different depending on the invocation

    Returns:
        dict: Information on the newly added or updated project
    """
    project_name = getattr(args, arg_prefix + "name")
    log.debug(
        "Adding or updating information for Utopia project '%s' ...",
        project_name,
    )

    project_paths = dict()
    for arg_name in (
        "base_dir",
        "models_dir",
        "python_model_tests_dir",
        "python_model_plots_dir",
    ):
        project_paths[arg_name] = getattr(args, arg_prefix + arg_name)

        if project_paths[arg_name]:
            project_paths[arg_name] = str(project_paths[arg_name])

    # Load existing project information, update it, store back to file
    projects = load_from_cfg_dir("projects")  # empty dict if file is missing
    projects[project_name] = project_paths

    write_to_cfg_dir("projects", projects)
    log.info("Updated information for Utopia project '%s'.", project_name)

    # If python_model_plots_dir is given, update plot modules cfg file
    if project_paths["python_model_plots_dir"]:
        log.debug("Additionally updating the python model plots path ...")

        plot_module_paths = load_from_cfg_dir("plot_module_paths")
        model_plots_dir = project_paths["python_model_plots_dir"]

        # Remove duplicate paths and instead store it under the project name
        plot_module_paths = {
            k: v for k, v in plot_module_paths.items() if v != model_plots_dir
        }
        plot_module_paths[project_name] = model_plots_dir

        write_to_cfg_dir("plot_module_paths", plot_module_paths)
        log.info(
            "Updated plot module paths for Utopia project '%s'.", project_name
        )

    return projects[project_name]


def deploy_user_cfg(
    user_cfg_path: str = Multiverse.USER_CFG_SEARCH_PATH,
) -> None:
    """Deploys a copy of the full config to the specified location (usually
    the user config search path of the Multiverse class)

    Instead of just copying the full config, it is written line by line,
    commenting out lines that are not already commented out, and changing the
    header.

    Args:
        user_cfg_path (str, optional): The path the file is expected at. Is an
            argument in order to make testing easier.

    Returns:
        None
    """
    # Check if a user config already exists and ask if it should be overwritten
    if os.path.isfile(user_cfg_path):
        print("A config file already exists at " + str(user_cfg_path))
        if input("Replace? [y, N]  ").lower() in ["yes", "y"]:
            os.remove(user_cfg_path)
            print("")

        else:
            print("Not deploying user config.")
            return

    # At this point, can assume that it is desired to write the file and there
    # is no other file there.
    # Make sure that the folder exists
    os.makedirs(os.path.dirname(user_cfg_path), exist_ok=True)

    # Create a file at the given location
    with open(user_cfg_path, "x") as ucfg:
        # Write header section, from user config header file
        with open(USER_CFG_HEADER_PATH) as ucfg_header:
            ucfg.write(ucfg_header.read())

        # Now go over the full config and write the content, commenting out
        # the lines that are not already commented out
        with open(BASE_CFG_PATH) as bcfg:
            past_prefix = False

            for line in bcfg:
                # Look for "---" to find out when the header section ended
                if line == "---\n":
                    past_prefix = True
                    continue

                # Write only if past the prefix
                if not past_prefix:
                    continue

                # Check if the line in the target (user) config needs to be
                # commented out or not
                if line.strip().startswith("#") or line.strip() == "":
                    # Is a comment or empty line -> just write it
                    ucfg.write(line)

                else:
                    # There is an entry on this line -> comment out before the
                    # first character (looks cleaner)
                    spaces = " " * (len(line.rstrip()) - len(line.strip()))
                    ucfg.write(spaces + "# " + line[len(spaces) :])

    print(
        f"Deployed user config to: {user_cfg_path}\n\n"
        "All entries are commented out; open the file to edit your "
        "configuration. Note that it is wise to only uncomment those entries "
        "that you absolutely *need* to set."
    )


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


def prompt_for_new_plot_args(
    *,
    old_argv: List[str],
    old_args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> Tuple[dict, argparse.Namespace]:
    """Given some old arguments, prompts for new ones and returns a new
    list of argument values and the parsed argparse namespace result.

    Args:
        old_argv (List[str]): The old argument value list
        old_args (argparse.Namespace): The old set of parsed arguments
        parser (argparse.ArgumentParser): The parser to use for evaluating the
            newly specified argument value list

    Returns:
        Tuple[dict, argparse.Namespace]: The new argument values list and the
            parsed argument namespace.

    Raises:
        ValueError: Upon error in parsing the new arguments.
    """
    # Specify those arguments that may not be given in the prompt
    DISALLOWED_ARGS = (
        "run_cfg_path",
        "run_dir_path",
        "set_cfg",
        "cluster_mode",
        "suppress_data_tree",
        "full_data_tree",
    )

    # Create a new argument list for querying the user. For that, remove
    # those entries from the argvs that are meant to be in the query.
    prefix_argv = ("--interactive", old_args.model_name)
    to_query = [arg for arg in old_argv if arg not in prefix_argv]
    to_query_str = " ".join(to_query) + (" " if to_query else "")

    # Now, setup the startup hook with a callable that inserts those
    # arguments that shall be editable by the user. Configure readline to
    # allow tab completion for file paths after certain delimiters.
    readline.set_startup_hook(lambda: readline.insert_text(to_query_str))
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n=")

    # Generate the prompt and store the result, stripping whitespace
    prompt_str = (
        "\n{ansi.CYAN}${ansi.MAGENTA} "
        "utopia eval -i {}"
        "{ansi.RESET} ".format(old_args.model_name, ansi=ANSIesc)
    )
    input_res = input(prompt_str).strip()
    print("")

    # Reset the startup hook to do nothing
    readline.set_startup_hook()

    # Prepare the new list of argument values.
    add_argv = input_res.split(" ") if input_res else []
    new_argv = list(prefix_argv) + add_argv

    # ... and parse it to the eval subparser.
    new_args = parser.parse_args(new_argv)
    # NOTE This may raise SystemExit upon the --help argument or other
    #      arguments that are not properly parsable.

    # Check that bad arguments were not used
    bad_args = [
        arg
        for arg in DISALLOWED_ARGS
        if getattr(new_args, arg) != parser.get_default(arg)
    ]
    if bad_args:
        print(
            "{ansi.RED}During interactive plotting, arguments that are used "
            "to update the Multiverse meta-configuration cannot be used!"
            "{ansi.RESET}".format(ansi=ANSIesc)
        )
        print(
            "{ansi.DIM}Remove the offending argument{} ({}) and try again. "
            "Consult --help to find out the available plotting-related "
            "arguments."
            "{ansi.RESET}".format(
                "s" if len(bad_args) != 1 else "",
                ", ".join(bad_args),
                ansi=ANSIesc,
            )
        )
        raise ValueError(
            "Cannot specify arguments that are used for updating the "
            "(already-in-use) meta-configuration of the current Multiverse "
            f"instance. Disallowed arguments: {', '.join(DISALLOWED_ARGS)}"
        )

    return new_argv, new_args
