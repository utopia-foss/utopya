"""Implements the `utopya test` subcommand"""

import os
import sys

import click

from ._shared import OPTIONS, add_options
from ._utils import Echo

# -----------------------------------------------------------------------------


@click.command(
    "test",
    help=(
        "Run the Python model tests associated with the specified model.\n"
        "\n"
        "Looks up the test directory, temporarily moves to that directory, "
        "and invokes pytest there. Any additional pytest arguments are passed "
        "through. See pytest docs for more information."
    ),
    context_settings=dict(ignore_unknown_options=True),
)
#
# Select a model
@click.argument("model_name")
@add_options(OPTIONS["label"])
#
# Pass pytest arguments through
@click.argument("pytest_args", nargs=-1)
#
# NOTE This function needs a name that is not simply ``test`` because pytest
#      will also search this file for test discovery and we cannot have a
#      function here that looks like a test function.
def run_test(
    model_name: str,
    label: str,
    pytest_args: tuple,
):
    """Invokes the associated Python tests for a model using pytest."""
    import pytest

    import utopya

    _log = utopya._getLogger("utopya")

    # Get model information and the corresponding test directory
    model = utopya.Model(name=model_name, bundle_label=label)
    model_info = model.info_bundle

    py_tests_dir = model_info.paths.get("py_tests_dir")
    if not py_tests_dir:
        _log.caution("No tests defined for this model.")
        return

    py_tests_dir = os.path.abspath(py_tests_dir)

    # Add the model tests' parent directories to the PATH to allow imports
    prepend_to_sys_path = (
        os.path.dirname(os.path.dirname(py_tests_dir)),
        os.path.dirname(py_tests_dir),
    )
    for p in prepend_to_sys_path:
        sys.path.insert(0, p)

    # Move to the test directory ...
    old_wd = os.getcwd()
    os.chdir(py_tests_dir)

    # ... and invoke the tests
    _log.progress("Invoking associated Python model tests ...")
    _log.remark(
        "Temporarily setting working directory to model test directory:\n  %s",
        py_tests_dir,
    )
    _log.remark("Full test command:\n\n  pytest %s\n\n", " ".join(pytest_args))
    try:
        sys.exit(pytest.main(list(pytest_args)))

    finally:
        # Change back to previous working directory to not have side effects
        os.chdir(old_wd)

        # Remove previously prependend directories from system PATH
        for p in prepend_to_sys_path:
            sys.path.remove(p)
