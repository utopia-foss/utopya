"""Tools for model registration"""

import logging

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


def register_models_from_list(
    *,
    registry: "utopya.model_registry.registry.ModelRegistry",
    separator: str,
    model_names: str,
    executables: str,
    label: str,
    more_paths: dict = dict(),
    source_dirs: str = None,
    exists_action: str = "raise",
    set_as_default: bool = None,
    project_name: str = None,
    _log=log,
    **shared_bundle_kwargs,
):
    """Handles registration of multiple models where the model names,
    executables, and source directories are splittable lists of equal lengths.

    Args:
        registry (utopya.model_registry.registry.ModelRegistry): The model
            registry to store the models in
        separator (str): Separation string to split ``model_names``,
            ``executables``, and ``source_dirs``.
        model_names (str): Splittable string of model names
        executables (str): Splittable string of executables
        label (str): Label under which to add the entries
        more_paths (dict, optional): Additional paths that are to be parsed
        source_dirs (str, optional): Splittable string of model source
            directories
        exists_action (str, optional): Action to take upon existing label
        project_name (str, optional): The associated project name
        _log (logging.Logger, optional): A logger-like object
        **shared_bundle_kwargs: passed on to bundle creation
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

        specs[model_name] = dict(
            paths=paths, project_name=project_name, **shared_bundle_kwargs
        )

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
            set_as_default=set_as_default,
            exists_action=exists_action,
        )

    _log.success("\nModel registration succeeded.")
    _log.remark(registry.info_str)
