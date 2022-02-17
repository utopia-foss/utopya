"""Tools for model and project registration"""

import logging

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


def evaluate_fstr_for_list(*, fstr: str, model_names: str, sep: str) -> str:
    """Evaluates a format string using the information from a list of model
    names.

    Args:
        fstr (str): The format string to evaluate for each model name
        model_names (str): A splittable string of model names
        sep (str): The separator used to split the ``model_names`` string
    """
    return sep.join(fstr.format(model_name=m) for m in model_names.split(sep))


def register_models_from_list(
    *,
    registry: "ModelRegistry",
    separator: str,
    model_names: str,
    executables: str,
    source_dirs: str,
    exists_action: str,
    label: str,
    project_name: str = None,
    _log=log,
    **more_paths,
):
    """Handles registration of multiple models where the model names,
    executables, and source directories are splittable lists of equal lengths.
    """

    _log.debug(
        "Splitting given model registration arguments by '%s' ...",
        separator,
    )

    model_names = model_names.split(separator)
    executables = executables.split(separator)

    if not source_dirs:
        source_dirs = [None for _ in model_names]
    else:
        source_dirs = source_dirs.split(separator)

    if not (len(model_names) == len(executables) == len(source_dirs)):
        raise ValueError(
            "Mismatch of sequence lengths during list-based model "
            "registration! The model_names, executables, and source_dirs "
            "lists should all be of equal length after having been split "
            f"by separator '{separator}', but were:\n"
            f"  model_names ({len(model_names)}):  {model_names}\n"
            f"  executables ({len(executables)}):  {executables}\n"
            f"  source_dirs ({len(source_dirs)}):  {source_dirs}"
        )

    # Go over them, create the paths dict, and populate a specs dict.
    specs = dict()
    for model_name, executable, source_dir in zip(
        model_names, executables, source_dirs
    ):
        paths = dict(
            executable=executable,
            source_dir=source_dir,
            **more_paths,
        )

        specs[model_name] = dict(paths=paths, project_name=project_name)

    _log.progress(
        "Received information for %d model%s. Now registering ...\n",
        len(specs),
        "s" if len(specs) != 1 else "",
    )

    # Now register, passing along shared arguments
    for model_name, bundle_kwargs in specs.items():
        registry.register_model_info(
            model_name,
            **bundle_kwargs,
            label=label,
            exists_action=exists_action,
        )

    _log.success("Model registration succeeded.")
    _log.remark(registry.info_str)


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
