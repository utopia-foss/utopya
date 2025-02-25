"""Test the Multiverse class initialization and workings.

As the Multiverse will always generate a folder structure, it needs to be
taken care that these output folders are temporary and are deleted after the
tests. This can be done with the tmpdir fixture of pytest.
"""

import copy
import os
import time
import uuid

import pytest

from utopya import DistributedMultiverse, FrozenMultiverse, Multiverse
from utopya.exceptions import (
    MultiverseError,
    UniverseOutputDirectoryError,
    UniverseSetupError,
)
from utopya.model import Model
from utopya.multiverse import DataManager, PlotManager, WorkerManager
from utopya.parameter import ValidationError

from . import ADVANCED_MODEL, DUMMY_MODEL, TEST_PROJECT_NAME, get_cfg_fpath
from ._fixtures import *
from .test_demo_project import test_EvalOnlyModel as test_eval_only

# Get the test resources
# TODO Sort these and find better names
RUN_CFG_PATH = get_cfg_fpath("run_cfg.yml")
RUN_CFG_PATH_VALID = get_cfg_fpath("run_cfg_validation_valid.yml")
RUN_CFG_PATH_INVALID = get_cfg_fpath("run_cfg_validation_invalid.yml")
USER_CFG_PATH = get_cfg_fpath("user_cfg.yml")
BASE_PLOTS_PATH = get_cfg_fpath("base_plots.yml")
UPDATE_BASE_PLOTS_PATH = get_cfg_fpath("update_base_plots.yml")
SWEEP_CFG_PATH = get_cfg_fpath("sweep_cfg.yml")
STOP_COND_CFG_PATH = get_cfg_fpath("stop_conds_integration.yml")
CLUSTER_MODE_CFG_PATH = get_cfg_fpath("cluster_mode_cfg.yml")

# Fixtures --------------------------------------------------------------------


@pytest.fixture(autouse=True)
def with_models(with_test_models):
    """Use on all tests in this module"""
    pass


@pytest.fixture
def mv_kwargs(tmpdir) -> dict:
    """Returns a dict that can be passed to Multiverse for initialisation.

    This uses the `tmpdir` fixture provided by pytest, which creates a unique
    temporary directory that is removed after the tests ran through.
    """
    # Create a dict that specifies a unique testing path.
    # The str cast is needed for python version < 3.6
    rand_str = "test_" + uuid.uuid4().hex
    unique_paths = dict(out_dir=str(tmpdir), model_note=rand_str)

    return dict(
        model_name=DUMMY_MODEL,
        run_cfg_path=RUN_CFG_PATH,
        user_cfg_path=USER_CFG_PATH,
        paths=unique_paths,
    )


@pytest.fixture
def default_mv(mv_kwargs) -> Multiverse:
    """Initialises a unique default configuration of the Multiverse to test
    everything beyond initialisation.

    Using the mv_kwargs fixture, it is assured that the output directory is
    unique.
    """
    return Multiverse(**mv_kwargs)


@pytest.fixture(
    params=[
        "node[002-004,011,006]",
        "node[002,003-004,011,006]",
        "z03s0123,m05s[0204,0409-0410],node006",
    ]
)
def cluster_env(tmpdir, request) -> dict:
    return dict(
        TEST_JOB_ID="123",
        TEST_JOB_NUM_NODES="5",
        TEST_JOB_NODELIST=request.param,
        TEST_NODENAME="node006",
        TEST_JOB_NAME="testjob",
        TEST_JOB_ACCOUNT="testaccount",
        TEST_CPUS_ON_NODE="42",
        TEST_CLUSTER_NAME="testcluster",
        TEST_TIMESTAMP=str(int(time.time())),
        TEST_CUSTOM_OUT_DIR=str(tmpdir.join("my_custom_dir")),
    )


@pytest.fixture(params=["node[002-004,011,006]", "node[002,003-004,011,006]"])
def cluster_env_specific(tmpdir, request) -> dict:
    """A cluster environment with a fully SPECIFIC node list. The node lists
    resulting from the given parameters above need to be fully identical and
    include nodes 2, 3, 4, 6 and 11 and nothing else.
    """
    return dict(
        TEST_JOB_ID="123",
        TEST_JOB_NUM_NODES="5",
        TEST_JOB_NODELIST=request.param,
        TEST_NODENAME="node006",
        TEST_JOB_NAME="testjob",
        TEST_JOB_ACCOUNT="testaccount",
        TEST_CPUS_ON_NODE="42",
        TEST_CLUSTER_NAME="testcluster",
        TEST_TIMESTAMP=str(int(time.time())),
        TEST_CUSTOM_OUT_DIR=str(tmpdir.join("my_custom_dir")),
    )


# Initialisation tests --------------------------------------------------------


def test_simple_init(mv_kwargs, tmp_projects):
    """Tests whether initialisation works for all basic cases."""
    # With the full set of arguments
    mv = Multiverse(**mv_kwargs)

    # Assert some basic types
    assert isinstance(mv.wm, WorkerManager)
    assert isinstance(mv.dm, DataManager)
    assert isinstance(mv.pm, PlotManager)
    assert isinstance(mv.model, Model)

    # And properties
    assert mv.model_name == DUMMY_MODEL
    assert mv.status_file_paths == []

    # Without the run configuration
    mv_kwargs.pop("run_cfg_path")
    mv_kwargs["paths"]["model_note"] += "_wo_run_cfg"
    Multiverse(**mv_kwargs)

    # Suppressing the user config
    mv_kwargs["user_cfg_path"] = False
    mv_kwargs["paths"]["model_note"] += "_wo_user_cfg"
    Multiverse(**mv_kwargs)
    # NOTE Without specifying a path, the search path will be used, which makes
    # the results untestable and creates spurious folders for the user.
    # Therefore, we cannot test for the case where no user config is given ...

    # No user config path given -> search at default location
    mv_kwargs["user_cfg_path"] = None
    mv_kwargs["paths"]["model_note"] = "_user_cfg_path_none"
    Multiverse(**mv_kwargs)

    # No user config at default search location
    Multiverse.USER_CFG_SEARCH_PATH = "this_is_not_a_path"
    mv_kwargs["paths"]["model_note"] = "_user_cfg_path_none_and_no_class_var"
    Multiverse(**mv_kwargs)


def test_invalid_model_name_and_operation(default_mv, mv_kwargs):
    """Tests for correct behaviour upon invalid model names"""
    # Try to instantiate with invalid model name
    mv_kwargs["model_name"] = "invalid_model_RandomShit_bgsbjkbkfvwuRfopiwehGP"
    with pytest.raises(ValueError, match="No model with name 'invalid_model_"):
        Multiverse(**mv_kwargs)


def test_config_handling(mv_kwargs):
    """Tests the config handling of the Multiverse"""
    # Multiverse that does not load the default user config
    mv_kwargs["user_cfg_path"] = False
    Multiverse(**mv_kwargs)

    # Testing whether errors are raised
    # Multiverse with wrong run config
    mv_kwargs["run_cfg_path"] = "an/invalid/run_cfg_path"
    with pytest.raises(FileNotFoundError):
        Multiverse(**mv_kwargs)


def test_backup(mv_kwargs):
    """Tests whether the backup of all config parts and the executable works"""
    mv = Multiverse(**mv_kwargs)
    cfg_path = mv.dirs["config"]

    assert os.path.isfile(os.path.join(cfg_path, "base_cfg.yml"))
    assert os.path.isfile(os.path.join(cfg_path, "user_cfg.yml"))
    assert os.path.isfile(os.path.join(cfg_path, "model_cfg.yml"))
    assert os.path.isfile(os.path.join(cfg_path, "run_cfg.yml"))
    assert os.path.isfile(os.path.join(cfg_path, "update_cfg.yml"))

    # Git information was not stored, because the dummy model has no project
    # associated with it
    assert not os.path.isfile(os.path.join(cfg_path, "git_info_project.yml"))
    assert not os.path.isfile(os.path.join(cfg_path, "git_info_framework.yml"))

    # And once more, now including the executable
    mv_kwargs["backups"] = dict(backup_executable=True)
    mv_kwargs["paths"]["model_note"] = "with-exec-backup"
    mv = Multiverse(**mv_kwargs)

    assert os.path.isfile(os.path.join(mv.dirs["run"], "backup", DUMMY_MODEL))

    # Now use the ADVANCED_MODEL, which has project information
    mv_kwargs["model_name"] = ADVANCED_MODEL
    mv_kwargs["paths"]["model_note"] = "with-git-info"
    mv_kwargs["backups"] = dict()  # use defaults
    mv = Multiverse(**mv_kwargs)
    cfg_path = mv.dirs["config"]

    assert os.path.isfile(os.path.join(cfg_path, "git_info_project.yml"))
    assert not os.path.isfile(os.path.join(cfg_path, "git_info_framework.yml"))

    # Can also turn that off
    mv_kwargs["paths"]["model_note"] = "without-git-info"
    mv_kwargs["backups"] = dict(include_git_info=False)
    mv = Multiverse(**mv_kwargs)
    cfg_path = mv.dirs["config"]

    assert not os.path.isfile(os.path.join(cfg_path, "git_info_project.yml"))
    assert not os.path.isfile(os.path.join(cfg_path, "git_info_framework.yml"))


def test_create_run_dir(default_mv):
    """Tests the folder creation in the initialsation of the Multiverse."""
    mv = default_mv

    # Reconstruct path from meta-config to have a parameter to compare to
    out_dir = str(mv.meta_cfg["paths"]["out_dir"])  # need str for python < 3.6
    path_base = os.path.join(out_dir, mv.model_name)

    # get all folders in the output dir
    folders = os.listdir(path_base)

    # select the latest one (there should be only one anyway)
    latest = folders[-1]

    # Check if the subdirectories are present
    for folder, perm_mask in dict(config=None, eval="775", data=None).items():
        subdir_path = os.path.join(path_base, latest, folder)
        assert os.path.isdir(subdir_path)

        # ... and it has the right directory permissions
        expected_permissions = int(perm_mask, 8) if perm_mask else 0o755

        dirstat = os.stat(subdir_path)
        print(folder, "folder type and permission mask:", dirstat.st_mode)
        assert oct(dirstat.st_mode)[-3:] == oct(expected_permissions)[-3:]


def test_detect_doubled_folders(mv_kwargs):
    """Tests whether an existing folder will raise an exception."""
    # Init Multiverse
    Multiverse(**mv_kwargs)

    # create output folders again
    # expect error due to existing folders
    with pytest.raises(RuntimeError, match="Simulation directory already"):
        # And another one, that will also create a directory
        Multiverse(**mv_kwargs)
        Multiverse(**mv_kwargs)
        # NOTE this test assumes that the two calls are so close to each other
        #      that the timestamp is the same, that's why there are two calls
        #      so that the latest the second call should raise such an error


def test_parameter_validation(mv_kwargs):
    """Tests integration of the parameter validation feature"""
    mv_kwargs["model_name"] = ADVANCED_MODEL

    # Works
    mv_kwargs["run_cfg_path"] = RUN_CFG_PATH_VALID
    mv_kwargs["paths"]["model_note"] = "valid"
    mv = Multiverse(**mv_kwargs)
    mv.run()

    # Fails already during initialization
    mv_kwargs["run_cfg_path"] = RUN_CFG_PATH_INVALID
    mv_kwargs["paths"]["model_note"] = "invalid"
    with pytest.raises(ValidationError, match="Validation failed for 1 para"):
        Multiverse(**mv_kwargs)

    # But not if validation is deactivated, then it will fail during run
    mv_kwargs["paths"]["model_note"] = "failing_during_run"
    mv = Multiverse(**mv_kwargs, perform_validation=False)
    with pytest.raises(SystemExit):
        mv.run()


def test_prepare_executable(mv_kwargs):
    """Tests handling of the executable, i.e. copying to a temporary location
    and emitting helpful error messages
    """
    mv_kwargs["executable_control"] = dict(run_from_tmpdir=False)
    mv = Multiverse(**mv_kwargs)

    # The dummy model should be available at this point, so _prepare_executable
    # should have correctly set a binary path, but not in a temporary directory
    assert mv._model_executable is not None
    assert mv._tmpdir is None
    original_executable = mv._model_executable

    # Now, let the executable be copied to a temporary location
    mv._prepare_executable(run_from_tmpdir=True)
    assert mv._model_executable != original_executable
    assert mv._tmpdir is not None

    # Adjust the info bundle for this Multiverse to use the temporary location
    tmp_executable = mv._model_executable
    mv._info_bundle = copy.deepcopy(mv.info_bundle)
    mv._info_bundle.paths["binary"] = tmp_executable

    # With the executable in a temporary location, we can change its access
    # rights to test the PermissionError
    os.chmod(tmp_executable, 0o600)
    with pytest.raises(
        PermissionError, match="does not point to an executable file"
    ):
        mv._prepare_executable()

    # Finally, remove that (temporary) file, to test the FileNotFound error
    os.remove(tmp_executable)
    with pytest.raises(FileNotFoundError, match="did you build it?"):
        mv._prepare_executable()


def test_base_cfg_pools(mv_kwargs):
    """Tests the generation of valid base config pools"""
    mv_kwargs["model_name"] = ADVANCED_MODEL
    mv = Multiverse(**mv_kwargs)
    parse = mv._parse_base_cfg_pools

    # Check special keywords get replaced
    assert parse(["utopya_base"]) == [("utopya", mv.UTOPYA_BASE_PLOTS_PATH)]
    assert parse(["model_base"]) == [
        (ADVANCED_MODEL + "_base", mv.info_bundle.paths.get("base_plots", {}))
    ]

    # Check additional paths get resolved
    assert parse(
        [("{model_name}_foo", "{paths[source_dir]}/{model_name}_plots.yml")]
    ) == [(f"{ADVANCED_MODEL}_foo", mv.info_bundle.paths["default_plots"])]
    assert parse([("foo", "some_invalid_path")]) == [("foo", {})]  # empty pool

    # Error messages
    with pytest.raises(TypeError, match="need to be specified as a list"):
        parse("not a list")

    with pytest.raises(ValueError, match="Invalid base config pool shortcut"):
        parse(["some bad shortcut"])


# Simulation tests ------------------------------------------------------------


def test_run_single(default_mv):
    """Tests a run with a single simulation"""
    # Run a single simulation using the default multiverse
    default_mv.run()
    # NOTE run will check the meta configuration for perform_sweep parameter
    #      and accordingly call run_single

    # Test that the universe directory was created as a proxy for the run
    # being finished
    assert os.path.isdir(os.path.join(default_mv.dirs["data"], "uni0"))

    # ... and nothing else in the data directory
    assert len(os.listdir(default_mv.dirs["data"])) == 1


def test_run_sweep(mv_kwargs):
    """Tests a run with a single simulation"""
    # Adjust the defaults to use the sweep configuration for run configuration
    mv_kwargs["run_cfg_path"] = SWEEP_CFG_PATH
    mv = Multiverse(**mv_kwargs)

    # Run the sweep
    mv.run()

    # There should now be four directories in the data directory
    assert len(os.listdir(mv.dirs["data"])) == 4

    # There should also be a status file path
    assert len(mv.status_file_paths) == 1

    # With a parameter space without volume, i.e. without any sweeps added,
    # the sweep should not be possible
    mv_kwargs["run_cfg_path"] = RUN_CFG_PATH
    mv_kwargs["paths"]["model_note"] = "_invalid_cfg"
    mv = Multiverse(**mv_kwargs)

    with pytest.raises(ValueError, match="The parameter space has no sweeps"):
        mv.run_sweep()


def test_multiple_runs_not_allowed(mv_kwargs):
    """Assert that multiple runs are prohibited"""
    # Create Multiverse and run
    mv = Multiverse(**mv_kwargs)
    mv.run_single()

    # Another run should not be possible
    with pytest.raises(MultiverseError, match="Could not add simulation task"):
        mv.run_single()


def test_run_from_meta_cfg_backup(mv_kwargs):
    """Tests that the resulting meta config backup file can be used to start
    a new run"""
    # Run a sweep
    mv_kwargs["run_cfg_path"] = SWEEP_CFG_PATH
    mv = Multiverse(**mv_kwargs)
    mv.run()

    assert len(os.listdir(mv.dirs["data"])) == 4

    # Set up a new Multiverse from the previous Multiverse's meta config backup
    mv_kwargs["run_cfg_path"] = os.path.join(mv.dirs["config"], "meta_cfg.yml")
    mv_kwargs["paths"]["model_note"] = "run_from_meta_cfg_backup"

    mv2 = Multiverse(**mv_kwargs)
    mv2.run()

    assert len(os.listdir(mv2.dirs["data"])) == 4


def test_stop_conditions(mv_kwargs):
    """An integration test for stop conditions"""
    # Can stop models that do have a signal handler attached
    mv_kwargs["model_name"] = ADVANCED_MODEL
    mv_kwargs["run_cfg_path"] = STOP_COND_CFG_PATH
    mv = Multiverse(**mv_kwargs)
    mv.run_sweep()
    time.sleep(2)
    assert len(mv.wm.tasks) == 13
    assert len(mv.wm.stopped_tasks) == 13  # all stopped

    # Can also stop models that do not
    mv_kwargs["model_name"] = DUMMY_MODEL
    mv_kwargs["run_kwargs"] = dict(
        stop_conditions=[dict(func="timeout_wall", seconds=1)]
    )

    mv = Multiverse(**mv_kwargs)
    mv.run_sweep()
    time.sleep(2)
    assert len(mv.wm.tasks) == 13
    assert len(mv.wm.stopped_tasks) == 13  # all stopped


def test_renew_plot_manager(mv_kwargs):
    """Tests the renewal of PlotManager instances in the Multiverse"""
    mv = Multiverse(**mv_kwargs)
    initial_pm = mv.pm

    # Try to renew it (with a bad config). The old one should remain
    with pytest.raises(ValueError, match="Failed setting up"):
        mv.renew_plot_manager(foo="bar")

    assert mv.pm is initial_pm

    # Again, this time it should work
    mv.renew_plot_manager()
    assert mv.pm is not initial_pm


def test_cluster_mode(mv_kwargs, cluster_env):
    """Tests cluster mode basics like: resolution of parameters, creation of
    the run directory, ...
    """
    # Define a custom test environment
    mv_kwargs["run_cfg_path"] = CLUSTER_MODE_CFG_PATH
    mv_kwargs["cluster_params"] = dict(env=cluster_env)

    # Create the Multiverse
    mv = Multiverse(**mv_kwargs)

    rcps = mv.resolved_cluster_params
    assert len(rcps) == 10 + 1

    # Check the custom output directory
    assert "my_custom_dir" in mv.dirs["run"]

    # Check the job ID is part of the run directory path
    assert "job123" in mv.dirs["run"]

    # Make sure the required keys are available
    assert all(
        [
            k in rcps
            for k in (
                "job_id",
                "num_nodes",
                "node_list",
                "node_name",
                "timestamp",
            )
        ]
    )

    # Check some types
    assert isinstance(rcps["job_id"], int)
    assert isinstance(rcps["num_nodes"], int)
    assert isinstance(rcps["num_procs"], int)
    assert isinstance(rcps["node_list"], list)
    assert isinstance(rcps["timestamp"], int)

    # Check some values
    assert rcps["node_index"] == 3  # for node006
    assert rcps["timestamp"] > 0
    assert "node006" in rcps["node_list"]
    assert len(rcps["node_list"]) == 5
    # NOTE Actual parsing of node list is checked in test__cluster.py

    # Can add additional info to the run directory
    mv_kwargs["cluster_params"]["additional_run_dir_fstrs"] = [
        "xyz{job_id:}",
        "N{num_nodes:}",
    ]
    mv = Multiverse(**mv_kwargs)
    assert "xyz123_N5" in mv.dirs["run"]

    # Single-node case
    cluster_env["TEST_JOB_NUM_NODES"] = "1"
    cluster_env["TEST_JOB_NODELIST"] = "node006"
    mv = Multiverse(**mv_kwargs)
    assert mv.resolved_cluster_params["node_list"] == ["node006"]

    # Test error messages; also see test__cluster.py for more dedicated tests
    # Node name not in node list
    cluster_env["TEST_NODENAME"] = "node042"
    with pytest.raises(ValueError, match="Failed parsing node list"):
        Multiverse(**mv_kwargs)

    # Wrong number of nodes
    cluster_env["TEST_NODENAME"] = "node003"
    cluster_env["TEST_JOB_NUM_NODES"] = "3"
    with pytest.raises(ValueError, match="Failed parsing node list"):
        Multiverse(**mv_kwargs)

    # Missing environment variables
    cluster_env.pop("TEST_NODENAME")
    with pytest.raises(
        ValueError, match="Missing required environment variable"
    ):
        Multiverse(**mv_kwargs)


def test_cluster_mode_run(mv_kwargs, cluster_env_specific):
    cluster_env = cluster_env_specific

    # Define a custom test environment
    mv_kwargs["run_cfg_path"] = CLUSTER_MODE_CFG_PATH
    mv_kwargs["cluster_params"] = dict(env=cluster_env)

    # Parameter space has 12 points
    # Five nodes are being used: node002, node003, node004, node006, node011
    # Test for first node, should perform 3 simulations
    cluster_env["TEST_NODENAME"] = "node002"
    mv_kwargs["paths"]["model_note"] = "node002"

    mv = Multiverse(**mv_kwargs)
    mv.run_sweep()
    assert mv.wm.num_finished_tasks == 3
    assert [t.name for t in mv.wm.tasks] == ["uni01", "uni06", "uni11"]
    # NOTE: simulated universes are uni01 ... uni12

    # Test for second node, should also perform 3 simulations
    cluster_env["TEST_NODENAME"] = "node003"
    mv_kwargs["paths"]["model_note"] = "node003"

    mv = Multiverse(**mv_kwargs)
    mv.run_sweep()
    assert mv.wm.num_finished_tasks == 3
    assert [t.name for t in mv.wm.tasks] == ["uni02", "uni07", "uni12"]

    # The third node should only perform 2 simulations
    cluster_env["TEST_NODENAME"] = "node004"
    mv_kwargs["paths"]["model_note"] = "node004"

    mv = Multiverse(**mv_kwargs)
    mv.run_sweep()
    assert mv.wm.num_finished_tasks == 2
    assert [t.name for t in mv.wm.tasks] == ["uni03", "uni08"]

    # The fourth and fifth node should also perform only 2 simulations
    cluster_env["TEST_NODENAME"] = "node006"
    mv_kwargs["paths"]["model_note"] = "node006"

    mv = Multiverse(**mv_kwargs)
    mv.run_sweep()
    assert mv.wm.num_finished_tasks == 2
    assert [t.name for t in mv.wm.tasks] == ["uni04", "uni09"]

    cluster_env["TEST_NODENAME"] = "node011"
    mv_kwargs["paths"]["model_note"] = "node011"

    mv = Multiverse(**mv_kwargs)
    mv.run_sweep()
    assert mv.wm.num_finished_tasks == 2
    assert [t.name for t in mv.wm.tasks] == ["uni05", "uni10"]


@pytest.mark.skip(
    "utopya cannot yet communicate to the model whether it should run parallel"
)
def test_parallel_init(mv_kwargs):
    """Test enabling parallel execution through the config"""
    # NOTE Ensure that information on parallel execution is logged
    mv_kwargs["parameter_space"] = dict(log_levels=dict(core="debug"))

    # Run with default settings and check log message
    mv_kwargs["paths"]["model_note"] = "pexec_disabled"
    mv = Multiverse(**mv_kwargs)
    mv.run()
    log = mv.wm.tasks[0].streams["out"]["log"]
    assert any("Parallel execution disabled" in line for line in log)

    # Now override default setting
    mv_kwargs["parameter_space"]["parallel_execution"] = dict(enabled=True)
    mv_kwargs["paths"]["model_note"] = "pexec_enabled"
    mv = Multiverse(**mv_kwargs)
    mv.run()
    log = mv.wm.tasks[0].streams["out"]["log"]
    assert any("Parallel execution enabled" in line for line in log)


def test_shared_worker_manager(mv_kwargs):
    """Tests using a shared WorkerManager between multiple Multiverses, an
    experimental feature that allows to use the WorkerManager for running
    multiple Multiverses.
    """
    mvs = list()
    shared_wm = None

    # Create a number of Multiverse, some with sweeps configured
    for i in range(5):
        _kws = copy.deepcopy(mv_kwargs)
        _kws["paths"]["model_note"] += f"_no{i}"
        if i % 2 == 0:
            _kws["run_cfg_path"] = SWEEP_CFG_PATH

        # Create Multiverse and manually add tasks
        mv = Multiverse(**_kws, _shared_worker_manager=shared_wm)
        mv._add_sim_tasks()

        # Keep track of it
        mvs.append(mv)

        # Define the shared WorkerManager instance (for the next iteration)
        shared_wm = mvs[0].wm

    # There should now be a total of 14 tasks, 4 each from Multiverses 0, 2,
    # and 4, and one each from Multiverses 1 and 3
    assert len(mvs) == 5
    assert len(shared_wm.tasks) == (4 + 1 + 4 + 1 + 4)

    # Let the shared WorkerManager start working
    shared_wm.start_working()

    # Check the output directories of each Multiverse were created (proxy for
    # the run having succeeded)
    for i, mv in enumerate(mvs):
        if i % 2 == 0:
            uni_names = ("uni1", "uni2", "uni3", "uni4")
        else:
            uni_names = ("uni0",)

        for uni_name in uni_names:
            assert os.path.isdir(os.path.join(mv.dirs["data"], uni_name))

        # Report files will only be created for the first Multiverse, because
        # there is (and can be) only one Reporter instance.
        _report_file = os.path.join(mv.dirs["run"], "_report.txt")
        _sweep_info_file = os.path.join(mv.dirs["run"], "_sweep_info.txt")
        if i == 0:
            assert os.path.isfile(_report_file)
            assert os.path.isfile(_sweep_info_file)
        else:
            assert not os.path.isfile(_report_file)
            assert not os.path.isfile(_sweep_info_file)


# FrozenMultiverse tests ------------------------------------------------------


def test_FrozenMultiverse(mv_kwargs, cluster_env):
    """Test the FrozenMultiverse class"""
    # Need a regular Multiverse and corresponding output for that
    mv = Multiverse(**mv_kwargs)
    mv.run_single()

    # NOTE Need to adjust the data directory in order to not create collisions
    # in the eval directory due to same timestamps ...

    # Now create a frozen Multiverse from that one
    # Without run directory, the latest one should be loaded
    print("\nInitializing FrozenMultiverse without further kwargs")
    fmv = FrozenMultiverse(
        **mv_kwargs, data_manager=dict(out_dir="eval/{timestamp:}_1")
    )

    # With a relative path that is also matching the folder pattern,
    # the corresponding directory should be found
    print("\nInitializing FrozenMultiverse with timestamp as run_dir")
    FrozenMultiverse(
        **mv_kwargs,
        run_dir=os.path.basename(mv.dirs["run"]),
        data_manager=dict(out_dir="eval/{timestamp:}_2"),
    )

    # This can also be only the timestamp, i.e. without the suffixed note:
    run_dir_timestamp = os.path.basename(mv.dirs["run"]).split("_")[0]
    print(
        "\nInitializing FrozenMultiverse only from run directory "
        f"timestamp: {run_dir_timestamp}"
    )
    FrozenMultiverse(
        **mv_kwargs,
        run_dir=run_dir_timestamp,
        data_manager=dict(out_dir="eval/{timestamp:}_2b"),
    )

    # But needs to be unique (and actually match)
    with pytest.raises(ValueError, match="uniquely match one and only one"):
        FrozenMultiverse(
            **mv_kwargs,
            run_dir=f"{run_dir_timestamp}_bad_note",
            data_manager=dict(out_dir="eval/{timestamp:}_2c"),
        )

    # With an absolute path, that path should be used directly
    print("\nInitializing FrozenMultiverse with absolute path to run_dir")
    FrozenMultiverse(
        **mv_kwargs,
        run_dir=mv.dirs["run"],
        data_manager=dict(out_dir="eval/{timestamp:}_3"),
    )

    # With a relative path, the path relative to the CWD should be used
    print("\nInitializing FrozenMultiverse with relative path to run_dir")
    FrozenMultiverse(
        **mv_kwargs,
        run_dir=os.path.relpath(mv.dirs["run"], start=os.getcwd()),
        data_manager=dict(out_dir="eval/{timestamp:}_4"),
    )

    # Bad type of run directory should fail
    with pytest.raises(TypeError, match="Argument run_dir needs"):
        FrozenMultiverse(
            **mv_kwargs,
            run_dir=123,
            data_manager=dict(out_dir="eval/{timestamp:}_5"),
        )

    # Non-existing directory should fail
    with pytest.raises(IOError, match="No run directory found at"):
        FrozenMultiverse(
            **mv_kwargs,
            run_dir="my_non-existing_directory",
            data_manager=dict(out_dir="eval/{timestamp:}_6"),
        )

    # Cluster mode
    print("\nInitializing FrozenMultiverse in cluster mode")
    mv_kwargs["run_cfg_path"] = CLUSTER_MODE_CFG_PATH
    mv_kwargs["cluster_params"] = dict(env=cluster_env)
    FrozenMultiverse(
        **mv_kwargs,
        run_dir=os.path.relpath(mv.dirs["run"], start=os.getcwd()),
        data_manager=dict(out_dir="eval/{timestamp:}_7"),
    )

    with pytest.raises(NotImplementedError, match="use_meta_cfg_from_run_dir"):
        FrozenMultiverse(
            **mv_kwargs,
            run_dir="/some/path/to/a/run_dir",
            use_meta_cfg_from_run_dir=True,
            data_manager=dict(out_dir="eval/{timestamp:}_7"),
        )

    # Misc
    with pytest.raises(AttributeError, match="should not be called"):
        fmv._create_run_dir(foo="bar")


def test_DistributedMultiverse(mv_kwargs, delay):
    """Tests various aspects of the DistributedMultiverse"""
    mv_kwargs["run_cfg_path"] = SWEEP_CFG_PATH
    update_cfg = dict(
        skipping=dict(enabled=True),
        run_kwargs=dict(timeout=1.0),
        worker_manager=dict(num_workers=1),
        parameter_space={"num_steps": 10, DUMMY_MODEL: dict(sleep_time=0.2)},
    )
    mv = Multiverse(**mv_kwargs, **update_cfg)

    # Start the sweep, after which there should be only one universe directory
    # because we ran into the timeout
    mv.run()

    assert len(os.listdir(mv.dirs["data"])) == 1

    # Set up the distributed multiverse, based on an existing Multiverse that
    # only ran partially.
    dmv = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )

    # Test some method errors that are hard to reproduce otherwise
    with pytest.raises(
        ValueError, match="Missing argument for skipping context"
    ):
        dmv._maybe_skip("some_invalid_context", desc="foo")

    with pytest.raises(
        ValueError, match="Invalid argument 'bad action' for skipping context"
    ):
        dmv.skipping["on_foo"] = "bad action"
        dmv._maybe_skip("foo", desc="test")

    # Meta config may not be missing
    os.remove(os.path.join(mv.dirs["config"], "meta_cfg.yml"))
    with pytest.raises(ValueError, match="No meta configuration file found"):
        DistributedMultiverse(model_name=mv.model_name, run_dir=mv.dirs["run"])

    with pytest.raises(NotImplementedError):
        dmv.run_single()

    with pytest.raises(NotImplementedError):
        dmv.run_sweep()


def test_run_dmv_join_run(mv_kwargs, delay):
    """Tests a run with a distributed simulation, running all files"""
    # Adjust the defaults to use the sweep configuration for run configuration.
    # However, only run a single universe (stop via timeout), such that we can
    # later on join in on the run.
    mv_kwargs["run_cfg_path"] = SWEEP_CFG_PATH
    update_cfg = dict(
        skipping=dict(enabled=True),
        run_kwargs=dict(timeout=1.0),
        worker_manager=dict(num_workers=1),
        parameter_space={"num_steps": 10, DUMMY_MODEL: dict(sleep_time=0.2)},
    )
    mv = Multiverse(**mv_kwargs, **update_cfg)
    assert mv.status_file_paths == []

    # Start the sweep, after which there should be one universe directory only,
    # because the run should have timed out
    mv.run()

    assert len(mv.status_file_paths) == 1
    assert len(os.listdir(mv.dirs["data"])) == 1
    for uni in os.listdir(mv.dirs["data"]):
        files = os.listdir(os.path.join(mv.dirs["data"], uni))
        assert "config.yml" in files
        assert "data.h5" in files
        assert "out.log" in files

    # Now set up the distributed multiverse
    dmv = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    assert len(mv.status_file_paths) == 1
    assert len(dmv.status_file_paths) == 1

    # ... and complete the remaining tasks
    dmv.join_run(num_workers=3, timeout=-1)

    assert len(mv.status_file_paths) == 2
    assert len(dmv.status_file_paths) == 2

    assert len(os.listdir(mv.dirs["data"])) == 4
    for uni in os.listdir(mv.dirs["data"]):
        files = os.listdir(os.path.join(mv.dirs["data"], uni))
        assert "config.yml" in files
        assert "data.h5" in files
        assert "out.log" in files

    # Cannot join a run if the initial Multiverse had skipping disabled
    time.sleep(1)
    update_cfg["skipping"]["enabled"] = False
    mv = Multiverse(**mv_kwargs, **update_cfg)
    mv.run()
    assert len(os.listdir(mv.dirs["data"])) == 1

    dmv = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )

    with pytest.raises(
        MultiverseError, match="`skipping.enabled` set to False!"
    ):
        dmv.join_run(timeout=-1)


def test_run_dmv_run(mv_kwargs):
    """Tests a run with a distributed simulation, running all files"""
    # Adjust the defaults to use the sweep configuration for run configuration
    mv_kwargs["run_cfg_path"] = SWEEP_CFG_PATH
    update_cfg = dict(skipping=dict(enabled=True, skip_after_setup=True))
    mv = Multiverse(**mv_kwargs, **update_cfg)

    # Run the sweep, after which there should be four universe directories,
    # but no data or output files
    mv.run()

    assert len(os.listdir(mv.dirs["data"])) == 4
    for uni in os.listdir(mv.dirs["data"]):
        files = os.listdir(os.path.join(mv.dirs["data"], uni))
        assert "config.yml" in files
        assert "data.h5" not in files
        assert "out.log" not in files

    # Now, after DistributedMultiverse ran, all directories should have files.
    distributed_mv = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    distributed_mv.run()

    assert len(os.listdir(mv.dirs["data"])) == 4
    for uni in os.listdir(mv.dirs["data"]):
        files = os.listdir(os.path.join(mv.dirs["data"], uni))
        assert "config.yml" in files
        assert "data.h5" in files
        assert "out.log" in files

    # .. Check errors
    # Can not run again (because task list is locked)
    with pytest.raises(MultiverseError, match=r"TaskList locked"):
        distributed_mv.run(universes=[os.listdir(mv.dirs["data"])[1]])

    with pytest.raises(MultiverseError, match=r"TaskList locked"):
        distributed_mv.run()

    # But also with a new instance, will fail because output already exists
    distributed_mv__repeat = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    with pytest.raises(UniverseSetupError, match=r"existing_uni_output"):
        distributed_mv__repeat.run()

    # Test that the MV can create uni-folder and uni-config
    distributed_mv__create_cfg = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )

    dirs = os.listdir(mv.dirs["data"])
    for _dir in dirs:
        dirpath = os.path.join(mv.dirs["data"], _dir)
        for file in os.listdir(dirpath):
            os.remove(os.path.join(dirpath, file))
    dirpath = os.path.join(mv.dirs["data"], dirs[0])
    os.rmdir(dirpath)

    distributed_mv__create_cfg.run()
    for _dir in dirs:
        files = os.listdir(os.path.join(mv.dirs["data"], _dir))
        assert "config.yml" in files
        assert "data.h5" in files
        assert "out.log" in files

    # Cannot run existing in cluster mode (at least not yet)
    distributed_mv__repeat.meta_cfg["cluster_mode"] = True
    with pytest.raises(MultiverseError, match="cluster mode"):
        distributed_mv__repeat.run()


def test_run_dmv_run_selection(mv_kwargs):
    """Tests a run with a selection of tasks in a distributed simulation"""
    # Adjust the defaults to use the sweep configuration for run configuration
    mv_kwargs["run_cfg_path"] = SWEEP_CFG_PATH
    update_cfg = dict(skipping=dict(enabled=True, skip_after_setup=True))
    mv = Multiverse(**mv_kwargs, **update_cfg)

    # Run the sweep
    mv.run()

    # There should now be four directories in the data directory
    assert len(os.listdir(mv.dirs["data"])) == 4
    for uni in os.listdir(mv.dirs["data"]):
        files = os.listdir(os.path.join(mv.dirs["data"], uni))
        assert "config.yml" in files
        assert "data.h5" not in files
        assert "out.log" not in files

    distributed_mv_0 = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    distributed_mv_1 = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    distributed_mv_23 = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    distributed_mv_0.run(universes=[os.listdir(mv.dirs["data"])[0]])
    distributed_mv_23.run(universes=os.listdir(mv.dirs["data"])[2:])

    # check that no file can be in directory
    uni1 = os.listdir(mv.dirs["data"])[1]
    bad_file_path = os.path.join(
        mv.dirs["data"], uni1, "this_file_should_not_exist.txt"
    )
    bad_file = open(bad_file_path, "a")
    bad_file.write("New line of text")
    bad_file.close()

    distributed_mv__fail = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    with pytest.raises(UniverseSetupError, match="existing_uni_output"):
        distributed_mv__fail.run(universes=[uni1])

    # run uni1 without that bad file
    os.remove(bad_file_path)
    distributed_mv_1.run(universes=[uni1])

    # There should now be four directories in the data directory
    assert len(os.listdir(mv.dirs["data"])) == 4
    for uni in os.listdir(mv.dirs["data"]):
        files = os.listdir(os.path.join(mv.dirs["data"], uni))
        assert "config.yml" in files
        assert "data.h5" in files
        assert "out.log" in files

    # check that the universes cannot be worked on again
    with pytest.raises(UniverseSetupError, match="existing_uni_output"):
        distributed_mv_0.run(universes=[os.listdir(mv.dirs["data"])[1]])

    with pytest.raises(UniverseSetupError, match="existing_uni_output"):
        distributed_mv_0.run()

    distributed_mv__fail = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    with pytest.raises(UniverseSetupError, match="existing_uni_output"):
        distributed_mv__fail.run()

    # repeat run with clear existing option, this will work
    distributed_mv__clear = DistributedMultiverse(
        model_name=mv.model_name, run_dir=mv.dirs["run"]
    )
    distributed_mv__clear.run(
        universes=os.listdir(mv.dirs["data"]), on_existing_uni_output="clear"
    )

    # various ways to specify universe selection
    dmvc = distributed_mv__clear
    universes_to_test = (
        "all",
        "uni1",
        ["uni1"],
        ("uni2",),
        "uni1,uni2",
        ["uni1", "uni2", "uni3"],
        ("uni1", "uni2"),
        ["uni1", "uni2", "uni1,uni4", "uni3"],
        "uni00001,uni02,0003",
        [1, 2, 3, 4],
        [1, 2, "03", "uni0004"],
    )

    for universes in universes_to_test:
        print("universes =", universes)
        dmvc.run(
            universes=universes, on_existing_uni_output="clear", num_workers=2
        )

    # invalid universe IDs
    with pytest.raises(MultiverseError, match="A universe with ID '234'"):
        dmvc.run(universes="234")

    with pytest.raises(ValueError, match="invalid literal"):
        dmvc.run(universes="badID")

    with pytest.raises(TypeError, match="should be 'all' or a string or list"):
        dmvc.run(universes=dict(not_the="right type"))


def test_run_dmv_run_backup(mv_kwargs):
    """Tests a run with a distributed simulation using an executable that was
    previously backed-up."""
    # Adjust the defaults to use the sweep configuration for run configuration
    mv_kwargs["run_cfg_path"] = SWEEP_CFG_PATH
    update_cfg = dict(
        skipping=dict(enabled=True, skip_after_setup=True),
        executable_control=dict(run_from_tmpdir=False),
    )

    # Include the executable
    mv_kwargs["backups"] = dict(backup_executable=True)
    mv_kwargs["paths"]["model_note"] = "with-exec-backup"

    nowork_mv = Multiverse(**mv_kwargs, **update_cfg)

    # Run the no-work sweep
    nowork_mv.run()

    distributed_mv = DistributedMultiverse(
        model_name=nowork_mv.model_name, run_dir=nowork_mv.dirs["run"]
    )

    assert os.path.isfile(distributed_mv.model_executable)

    assert distributed_mv.model_executable == os.path.join(
        distributed_mv.dirs["run"], "backup", distributed_mv.model_name
    )

    distributed_mv.run()

    mv_kwargs["paths"]["model_note"] = "with-exec-backup__broken_backup"

    # Set up a new one and remove the backup executable
    new_nowork_mv = Multiverse(**mv_kwargs, **update_cfg)
    new_nowork_mv.run()

    os.remove(
        os.path.join(
            new_nowork_mv.dirs["run"], "backup", new_nowork_mv.model_name
        )
    )
    assert not os.path.isfile(
        os.path.join(
            new_nowork_mv.dirs["run"], "backup", new_nowork_mv.model_name
        )
    )

    with pytest.raises(FileNotFoundError, match=r"No executable found .*"):
        distributed_mv = DistributedMultiverse(
            model_name=nowork_mv.model_name,
            run_dir=new_nowork_mv.dirs["run"],
        )
