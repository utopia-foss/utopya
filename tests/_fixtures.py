"""Test utilities, fixtures, ..."""

import copy
import os
import pathlib
import shutil
import time

import pytest

import utopya
import utopya.cfg as ucfg
import utopya.model_registry as umr

from . import (
    ABBREVIATE_TEST_OUTPUT_DIR,
    ADVANCED_MODEL,
    DEMO_DIR,
    DUMMY_MODEL,
    EVALONLY_MODEL,
    TEST_LABEL,
    TEST_OUTPUT_DIR,
    TEST_PROJECT_NAME,
    TEST_VERBOSITY,
    USE_TEST_OUTPUT_DIR,
)

# -----------------------------------------------------------------------------

DUMMY_EXECUTABLE = os.path.join(
    DEMO_DIR, "models", DUMMY_MODEL, f"{DUMMY_MODEL}.py"
)

ADVANCED_EXECUTABLE = os.path.join(
    DEMO_DIR, "models", ADVANCED_MODEL, f"{ADVANCED_MODEL}.py"
)

TEST_MODELS = {
    DUMMY_MODEL: (
        os.path.dirname(DUMMY_EXECUTABLE),
        (),
    ),
    ADVANCED_MODEL: (
        os.path.dirname(ADVANCED_EXECUTABLE),
        ("--project-name", TEST_PROJECT_NAME),
    ),
    EVALONLY_MODEL: (
        os.path.join(DEMO_DIR, "models", EVALONLY_MODEL),
        ("--project-name", TEST_PROJECT_NAME),
    ),
}
"""Name and (source dirs, registration args) of the models that are used for
testing the CLI
"""


# -----------------------------------------------------------------------------
# Output Directory


@pytest.fixture
def tmpdir_or_local_dir(tmpdir, request) -> pathlib.Path:
    """If ``USE_TEST_OUTPUT_DIR`` is False, returns a temporary directory;
    otherwise a test-specific local directory within ``TEST_OUTPUT_DIR`` is
    returned.
    """
    if not USE_TEST_OUTPUT_DIR:
        return tmpdir

    if not ABBREVIATE_TEST_OUTPUT_DIR:
        # include the module and don't do any string replacements
        test_dir = os.path.join(
            TEST_OUTPUT_DIR,
            request.node.module.__name__,
            request.node.originalname,
        )
    else:
        # generate a shorter version without the module and with the test
        # prefixes dropped
        test_dir = os.path.join(
            TEST_OUTPUT_DIR,
            request.node.originalname.replace("test_", ""),
        )

    print(f"Using local test output directory:\n  {test_dir}")
    if os.path.isdir(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir, exist_ok=True)
    return pathlib.Path(test_dir)


out_dir = tmpdir_or_local_dir
"""Alias for ``tmpdir_or_local_dir`` fixture"""

# -----------------------------------------------------------------------------


@pytest.fixture
def delay():
    """Delays test execution by a second, eg. to avoid identical time stamps"""
    time.sleep(1)


@pytest.fixture
def tmp_cfg_dir(tmpdir):
    """Adjust the config directory and paths to be something temporary and
    clean it up again afterwards...

    .. note::

        This does NOT change the already loaded models and project registry!
    """
    # Store the old ones
    old_cfg_dir = ucfg.UTOPYA_CFG_DIR
    old_cfg_file_paths = ucfg.UTOPYA_CFG_FILE_PATHS

    # Place a temporary one
    # TODO Check if this works (not changing a *mutable* object here)
    ucfg.UTOPYA_CFG_DIR = str(tmpdir)
    ucfg.UTOPYA_CFG_FILE_PATHS = {
        k: os.path.join(ucfg.UTOPYA_CFG_DIR, fname)
        for k, fname in ucfg.UTOPYA_CFG_FILE_NAMES.items()
    }
    yield str(tmpdir)

    # Teardown code: reinstate the old paths
    ucfg.UTOPYA_CFG_DIR = old_cfg_dir
    ucfg.UTOPYA_CFG_FILE_PATHS = old_cfg_file_paths


@pytest.fixture
def tmp_model_registry(tmp_cfg_dir) -> umr._ModelRegistry:
    """A temporary model registry"""
    return umr._ModelRegistry(tmp_cfg_dir)


@pytest.fixture
def tmp_projects(tmp_cfg_dir):
    """A "temporary" projects registry that adds the demo project to it and
    removes it again at fixture teardown"""
    from utopya import PROJECTS

    original_project_names = list(PROJECTS)

    PROJECTS.register(
        base_dir=DEMO_DIR,
        exists_action="raise",
        custom_project_name=TEST_PROJECT_NAME,
        require_matching_names=False,
    )
    assert TEST_PROJECT_NAME in PROJECTS
    yield

    # Make sure no projects added by the tests remain in the registry
    new_project_names = [
        name for name in PROJECTS if name not in original_project_names
    ]
    for project_name in new_project_names:
        PROJECTS.remove_entry(project_name)


@pytest.fixture
def with_test_models(tmp_projects):
    """A fixture that prepares the model registry by adding some test models.
    It ensures that the registry is in its old state after the tests ran
    through.

    This uses the actual model registry in order to carry out the tests in a
    realistic scenario and without the caveats of a mock registry.
    Furthermore, it uses the CLI to carry out some of the operations, because
    that's the easiest way to carry over some of the information of the test
    models.

    TODO Consider using a file-based backup instead?!
    """
    from .cli import invoke_cli

    mr = utopya.MODELS
    existing_bundles = dict()
    default_labels = dict()

    # Register the test models under a custom label and set them as defaults
    for model, (src_dir, extra_args) in TEST_MODELS.items():
        # Get existing labels and potentially existing default label
        if model in mr:
            existing_bundles[model] = {
                k: copy.deepcopy(v) for k, v in mr[model].items()
            }
            default_labels[model] = mr[model].default_label
        else:
            existing_bundles[model] = dict()
            default_labels[model] = None

        assert TEST_LABEL not in existing_bundles[model]

        # Register using CLI (easiest to carry over all information)
        reg_args = (
            "models",
            "register",
            "from-manifest",
            os.path.join(src_dir, f"{model}_info.yml"),
            "--model-name",
            model,
            "--label",
            TEST_LABEL,
            "--exists-action",
            "raise",  # safeguard against corrupting existing entry
        ) + extra_args

        res = invoke_cli(reg_args)
        print(res.output)
        assert res.exit_code == 0

        assert model in mr
        assert TEST_LABEL in mr[model]

        res = invoke_cli(("models", "set-default", model, TEST_LABEL))
        assert res.exit_code == 0

    yield mr

    # Remove the test bundles again and set the previous default
    for model in TEST_MODELS:
        # Remove the whole entry, then add it back as before
        if model in mr:
            mr.remove_entry(model)

        for label, bundle in existing_bundles[model].items():
            mr.register_model_info(
                model,
                label=label,
                **bundle._d,
                registration_time=bundle._reg_time,
            )

        # Set the default label value
        if default_labels[model]:
            mr[model].default_label = default_labels[model]


registry = with_test_models
"""Alias for the `with_test_models` fixture"""


@pytest.fixture(scope="module")
def tmp_output_dir():
    """Replaces the user configuration such that the same temporary output
    directory is used throughout the whole module this fixture is used in.
    """
    import tempfile

    user_cfg_path = os.path.expanduser("~/.config/utopya/user_cfg.yml")
    have_user_cfg = os.path.exists(user_cfg_path)

    if have_user_cfg:
        # Need to move that file away temporarily
        tmp_user_cfg_path = user_cfg_path + ".tmp"
        shutil.move(user_cfg_path, tmp_user_cfg_path)

    # Create a temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        utopya.tools.write_yml(
            dict(paths=dict(out_dir=str(tmpdir))), path=user_cfg_path
        )
        yield

    # Restore previous state
    if have_user_cfg:
        shutil.move(tmp_user_cfg_path, user_cfg_path)

    else:
        os.remove(user_cfg_path)


# -- Generated test data ------------------------------------------------------


@pytest.fixture
def dm(tmpdir) -> utopya.DataManager:
    """Constructs a utopya DataManager and fills it with data"""
    dm = utopya.DataManager(tmpdir)

    # TODO Add test data here

    return dm
