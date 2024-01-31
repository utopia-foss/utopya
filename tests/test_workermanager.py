"""Tests the WorkerManager class"""

import os
import queue
import time

import numpy as np
import pytest

from utopya.stop_conditions import SIG_STOPCOND
from utopya.task import SIGMAP
from utopya.workermanager import WorkerManager, WorkerManagerTotalTimeout
from utopya.yaml import load_yml

from . import get_cfg_fpath

STOP_CONDS_PATH = get_cfg_fpath("stop_conds.yml")


# Fixtures --------------------------------------------------------------------
@pytest.fixture
def wm():
    """Create the simplest possible WorkerManager instance"""
    return WorkerManager(num_workers=2, poll_delay=0.042, spawn_rate=1)


@pytest.fixture
def wm_priQ():
    """Create simple WorkerManager instance with a PriorityQueue for the tasks.
    Priority from -inf to +inf (high to low)."""
    return WorkerManager(
        num_workers=2,
        poll_delay=0.01,
        QueueCls=queue.PriorityQueue,
        spawn_rate=1,
    )


@pytest.fixture
def sleep_task() -> dict:
    """A sleep task definition"""
    return dict(
        worker_kwargs=dict(
            args=("python3", "-c", "from time import sleep; sleep(0.5)"),
            read_stdout=True,
        )
    )


@pytest.fixture
def longer_sleep_task() -> dict:
    """A sleep task definition that is a bit longer"""
    return dict(
        worker_kwargs=dict(
            args=("python3", "-c", "from time import sleep; sleep(1.0)"),
            read_stdout=True,
        )
    )


@pytest.fixture
def wm_with_tasks(sleep_task):
    """Create a WorkerManager instance and add some tasks"""
    # A few tasks
    tasks = []
    tasks.append(
        dict(
            worker_kwargs=dict(
                args=(
                    "python3",
                    "-c",
                    'print("hello\\noh so\\n' 'complex world")',
                ),
                read_stdout=True,
            ),
            priority=0,
        )
    )

    tasks.append(sleep_task)
    tasks.append(
        dict(
            worker_kwargs=dict(
                args=("python3", "-c", "pass"), read_stdout=False
            )
        )
    )
    tasks.append(
        dict(
            worker_kwargs=dict(
                args=("python3", "-c", "print(\"{'key': '1.23'}\")"),
                read_stdout=True,
                stdout_parser="yaml_dict",
            )
        )
    )
    tasks.append(sleep_task)

    # Now initialise the worker manager
    wm = WorkerManager(num_workers=2, spawn_rate=1)

    # And pass the tasks
    for task_dict in tasks:
        wm.add_task(**task_dict)

    return wm


@pytest.fixture
def sc_run_kws():
    return load_yml(STOP_CONDS_PATH)["run_kwargs"]


# Tests -----------------------------------------------------------------------


def test_init():
    """Tests whether initialization succeeds"""
    WorkerManager()

    # Test different `poll_delay` arguments: negative and small value
    with pytest.raises(ValueError, match="needs to be positive"):
        WorkerManager(num_workers=1, poll_delay=-1000)

    with pytest.warns(UserWarning):
        WorkerManager(num_workers=1, poll_delay=0.001)

    # Test different `spawn_rate` arguments
    with pytest.raises(ValueError, match="needs to be a positive integer"):
        WorkerManager(num_workers="auto", spawn_rate=-2)

    with pytest.raises(ValueError, match="needs to be a positive integer"):
        WorkerManager(num_workers="auto", spawn_rate=0)

    with pytest.raises(ValueError, match="needs to be a positive integer"):
        WorkerManager(num_workers="auto", spawn_rate=0.1)

    # Test initialization with different `nonzero_exit_handling` values
    WorkerManager(nonzero_exit_handling="ignore")
    WorkerManager(nonzero_exit_handling="warn")
    WorkerManager(nonzero_exit_handling="raise")
    with pytest.raises(ValueError, match="`nonzero_exit_handling` needs to"):
        WorkerManager(nonzero_exit_handling="invalid")

    # Test initialization with an (invalid) Reporter type
    with pytest.raises(TypeError, match="Need a WorkerManagerReporter"):
        WorkerManager(reporter="not_a_reporter")
    # NOTE the tests with the actual WorkerManagerReporter can be found in
    # test_reporter.py, as they require adequate initialization arguments
    # for which it would make no sense to make them available here

    # Test passing report specifications
    wm = WorkerManager(rf_spec=dict(foo="bar"))
    assert wm.rf_spec["foo"] == "bar"


def test_num_workers():
    """Tests the num_workers property"""
    # Defaults to CPU count
    wm = WorkerManager()
    assert wm.num_workers == os.cpu_count()
    assert wm.num_workers == WorkerManager(num_workers="auto").num_workers

    wm = WorkerManager(num_workers=1)
    assert wm.num_workers == 1

    # Can pass negative values, which are added to the CPU count
    wm = WorkerManager(num_workers=-1)
    assert wm.num_workers == max(1, os.cpu_count() - 1)

    # High number of workers will emit a warning
    with pytest.warns(UserWarning, match="Set WorkerManager to use more"):
        WorkerManager(num_workers=1000)

    # Too negative values are clipped to 1
    wm = WorkerManager(num_workers=-1000)
    assert wm.num_workers == 1

    # Other exceptions
    with pytest.raises(TypeError, match="Expected integer or string"):
        WorkerManager(num_workers=1.23)


def test_add_tasks(wm, sleep_task):
    """Tests adding of tasks"""
    # This one should work
    wm.add_task(**sleep_task)

    # Test that warnings and errors propagate through
    with pytest.warns(UserWarning, match="`worker_kwargs` given but also"):
        wm.add_task(
            setup_kwargs=dict(foo="bar"), worker_kwargs=dict(foo="bar")
        )

    with pytest.raises(ValueError, match="Need either argument `setup_func`"):
        wm.add_task()


def test_start_working(wm_with_tasks):
    """Tests whether the start_working methods does what it should"""
    wm = wm_with_tasks
    wm.start_working()
    # This will be blocking

    # Check that all tasks finished with exit status 0
    for task in wm.tasks:
        assert task.worker_status == 0
        assert task.profiling["end_time"] > task.profiling["create_time"]

        # Trying to spawn or assigning another worker should fail
        with pytest.raises(RuntimeError):
            task.spawn_worker()

        with pytest.raises(RuntimeError):
            task.worker = "something"


def test_nonzero_exit_handling(wm):
    """Test that the non-zero exception handling works"""

    # Work sequentially
    wm.num_workers = 1

    # Generate a failing task config
    failing_task = dict(worker_kwargs=dict(args=("false",)))

    # Test that with 'ignore', everything runs as expected
    wm.nonzero_exit_handling = "ignore"
    wm.add_task(**failing_task)
    wm.add_task(**failing_task)
    wm.start_working()
    assert wm.num_finished_tasks == 2

    # Now run through 'warning' mode
    wm.nonzero_exit_handling = "warn"
    wm.add_task(**failing_task)
    wm.add_task(**failing_task)
    wm.start_working()
    assert wm.num_finished_tasks == 4

    # Now run through 'raise' mode
    wm.nonzero_exit_handling = "raise"
    wm.add_task(**failing_task)
    wm.add_task(**failing_task)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        wm.start_working()

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    assert wm.num_finished_tasks == 5


def test_interrupt_handling(wm, sleep_task, tmpdir):
    """Tests the keyboard interrupt handling of the WorkerManager.start_working
    method.
    """

    # Define a post poll function that is to simulate the KeyboardInterrupt
    def ppf():
        time.sleep(0.2)  # To give the task enough time to start up ...
        raise KeyboardInterrupt

    # Work with specific worker parameters
    wm.num_workers = 4
    wm.interrupt_params["send_signal"] = "SIGTERM"
    wm.interrupt_params["grace_period"] = 10.0
    wm.interrupt_params["exit"] = True

    # -- Case 1 --
    # Check that working on these tasks leads to system exit
    wm.add_task(**sleep_task)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        wm.start_working(post_poll_func=ppf)

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 128 + 15
    assert wm.tasks[-1].worker_status == -15  # SIGTERM

    # -- Case 2 --
    # Don't exit after interrupt
    wm.interrupt_params["exit"] = False
    wm.add_task(**sleep_task)
    wm.start_working(post_poll_func=ppf)
    assert wm.tasks[-1].worker_status == -15  # SIGTERM

    # -- Case 3 --
    # Check the case where the task is not quitting fast enough. For that, use
    # a bash script that sleeps, but catches the keyboard interrupt and then
    # does not quit immediately
    sh_script = tmpdir.join("deep_sleep.sh")
    with sh_script.open("w") as f:
        f.write("#!/bin/sh\ntrap 'sleep 5' SIGINT\nsleep 5\n")
    sh_script.chmod(888)  # full permission needed
    # NOTE The actual sleep time is not important; it just needs to be long
    #      enough such that the script does not exit before the signal can be
    #      sent to it. Due to the reduced grace period (see below), the kill
    #      signal will be sent directly afterwards...

    deep_sleep = dict(worker_kwargs=dict(args=(str(sh_script),)))
    wm.add_task(**deep_sleep)

    wm.interrupt_params["grace_period"] = 0.5  # needs to be shorter than sleep
    wm.interrupt_params["send_signal"] = "SIGINT"  # Such that caught in task
    wm.interrupt_params["exit"] = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        wm.start_working(post_poll_func=ppf)

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 128 + 2
    assert wm.tasks[-1].worker_status == -9  # SIGKILL, b/c SIGINT was handled


def test_signal_workers(wm, longer_sleep_task):
    """Tests the signalling of workers"""
    # Use the longer sleep task to avoid race conditions
    sleep_task = longer_sleep_task

    # Start running with post-poll function that directly kills off the workers
    for _ in range(3):
        wm.add_task(**sleep_task)
    ppf = lambda: wm._signal_workers("active", signal="SIGKILL")
    wm.start_working(post_poll_func=ppf)

    # Check if they were all killed
    for task in wm.tasks:
        assert task.worker_status == -SIGMAP["SIGKILL"]

    # Same again for other specific signals
    for _ in range(3):
        wm.add_task(**sleep_task)
    ppf = lambda: wm._signal_workers("active", signal="SIGTERM")
    wm.start_working(post_poll_func=ppf)

    for task in wm.tasks[-3:]:
        assert task.worker_status in [-SIGMAP["SIGTERM"], -SIGMAP["SIGKILL"]]
        # NOTE sleep task _might_ not allow SIGTERM, will then be killed

    for _ in range(3):
        wm.add_task(**sleep_task)
    ppf = lambda: wm._signal_workers("active", signal="SIGINT")
    wm.start_working(post_poll_func=ppf)

    for task in wm.tasks[-3:]:
        assert task.worker_status == -SIGMAP["SIGINT"]

    # And invalid signalling value; needs to be a valid signal _name_
    wm.add_task(**sleep_task)
    ppf = lambda: wm._signal_workers("active", signal="NOT_A_SIGNAL")
    with pytest.raises(ValueError, match="No signal named 'NOT_A_SIGNAL'"):
        wm.start_working(post_poll_func=ppf)

    # Invalid list to signal
    with pytest.raises(ValueError, match="Tasks cannot be specified by "):
        wm._signal_workers("foo", signal=9)

    # Signal all tasks (they all ended anyway)
    wm._signal_workers("all", signal="SIGTERM")


def test_detach(wm):
    with pytest.raises(NotImplementedError):
        wm.start_working(detach=True)


def test_empty_task_queue(wm):
    with pytest.raises(queue.Empty):
        wm._grab_task()


def test_spawn_rate(wm_with_tasks):
    """Tests whether the start_working methods does what it should"""
    wm = wm_with_tasks
    assert wm.num_workers > 1
    assert wm.spawn_rate == 1

    # Set more robustly testable values
    POLL_DELAY = 0.1
    wm.spawn_rate = 2
    wm.poll_delay = POLL_DELAY

    wm.start_working()

    # Check that all tasks finished with exit status 0
    for task in wm.tasks:
        assert task.worker_status == 0
        assert task.profiling["end_time"] > task.profiling["create_time"]

    # First two tasks should be spawned very close to each other, because of
    # spawn rate -1
    task0 = wm.tasks[0]
    task1 = wm.tasks[1]
    p0 = task0.profiling
    p1 = task1.profiling

    dt = p1["create_time"] - p0["create_time"]
    assert dt > 0
    assert dt < POLL_DELAY / 5  # heuristical factor, depends on machine

    # Third task should be spawned in the next loop
    task2 = wm.tasks[2]
    p2 = task2.profiling
    assert (p2["create_time"] - p0["create_time"]) > 0.9 * POLL_DELAY


def test_parallel_spawn(wm_with_tasks):
    """Tests whether the start_working methods does what it should"""
    wm = wm_with_tasks
    assert wm.num_workers > 1
    assert wm.spawn_rate == 1

    # Set more robustly testable values
    POLL_DELAY = 0.1
    wm.spawn_rate = -1
    wm.poll_delay = POLL_DELAY

    wm.start_working()

    # Check that all tasks finished with exit status 0
    for task in wm.tasks:
        assert task.worker_status == 0
        assert task.profiling["end_time"] > task.profiling["create_time"]


def test_timeout(wm, sleep_task, longer_sleep_task):
    """Tests whether the timeout succeeds"""
    # Add some sleep tasks
    for _ in range(3):
        wm.add_task(**sleep_task)
    # NOTE With two workers, this should take approx 1 second to execute

    # Check if the run does not start for an invalid timeout value
    with pytest.raises(ValueError):
        wm.start_working(timeout=-123.45)

    # Check if no WorkerManagerTotalTimeout is raised for a high timeout value
    wm.start_working(timeout=23.4)
    assert wm.num_finished_tasks == 3

    # Add more asks
    for _ in range(17):
        wm.add_task(**longer_sleep_task)  # 1s each
    assert wm.task_count == 20

    # For a brief timeout duration, not all of the queued tasks should be run.
    # With 2 workers, there will be two finished tasks and two interrupted ones
    wm.start_working(timeout=1.4)
    assert wm.num_finished_tasks == 3 + 2 + 2


def test_stopconds(wm, wm_with_tasks, longer_sleep_task, sc_run_kws):
    """Tests the stop conditions"""
    assert not wm.stop_conditions

    # Populate the basic wm with two sleep tasks
    wm.add_task(**longer_sleep_task)
    wm.add_task(**longer_sleep_task)

    # Start working. Stop conditions:
    #   - timeout_wall == 0.4 seconds
    #   - monitor check (to a non-existing monitor entry)
    assert not wm.stop_conditions
    wm.start_working(**sc_run_kws)
    assert len(wm.stop_conditions) == 3

    # Assert that there are no workers remaining and that both have as exit
    # status -SIGUSR1, 128 + 30 on UNIX systems, wrapped around
    assert wm.active_tasks == []
    for task in wm.tasks:
        assert task.worker_status == -SIGMAP[SIG_STOPCOND]

        # Also, the tasks should have the stop conditions associated
        assert len(task.fulfilled_stop_conditions) == 2  # only 2 of 3

        # And the stop conditions should know about these tasks
        for sc in task.fulfilled_stop_conditions:
            assert task in sc.fulfilled_for


@pytest.mark.skip("Properly implement this!")
def test_read_stdout(wm):
    """Checks if the stdout was read"""

    wm.start_working()

    # TODO read the stream output here


def test_priority_queue(wm_priQ, sleep_task):
    """Checks that tasks are dispatched from the task queue in order of their
    priority, if a priority queue is used."""
    wm = wm_priQ

    # Create a list of priorities that should be checked
    prios = [-np.inf, 2.0, 1.0, None, 0, -np.inf, 0, +np.inf, 1.0]
    correct_order = [0, 6, 4, 7, 2, 1, 3, 8, 5]
    # If priorites are equal, the task added first have higher priority
    # NOTE cannot just order the list of tasks, because then there would be
    # no ground truth (the same ordering mechanism between tasks would be used)

    # Add tasks to the WorkerManager, keeping track of addition order
    tasks = []
    for prio in prios:
        tasks.append(wm.add_task(priority=prio, **sleep_task))

    # Now, start working
    wm.start_working()
    # Done working now.

    # Assert that the internal task list has the same order
    assert tasks == wm.tasks

    # Extract the creation times of the tasks for manual checks
    creation_times = [t.profiling["create_time"] for t in tasks]
    print("Creation times:")
    print("\n".join([str(e) for e in creation_times]))
    print("Correct order:", correct_order)

    # Sort task list by correct order and by creation times
    tasks_by_correct_order = [t for _, t in sorted(zip(correct_order, tasks))]
    tasks_by_creation_time = [t for _, t in sorted(zip(creation_times, tasks))]

    # Check that the two lists compare equal
    assert tasks_by_correct_order == tasks_by_creation_time
