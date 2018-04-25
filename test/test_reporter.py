"""Tests the Reporter class and derived classes."""

import time

import pytest

from utopya.workermanager import WorkerManager
from utopya.task import enqueue_lines, parse_json
from utopya.reporter import Reporter, WorkerManagerReporter

# Local constants
MIN_REP_INTV = 0.1

# Fixtures --------------------------------------------------------------------

@pytest.fixture
def sleep_task() -> dict:
    """The kwargs for a sleep task"""
    sleep_args = ('python3', '-c', 'from time import sleep; sleep(0.1)')
    return dict(worker_kwargs=dict(args=sleep_args, read_stdout=True))

@pytest.fixture
def wm(sleep_task) -> WorkerManager:
    """Create a WorkerManager instance with multiple sleep tasks"""
    # Initialise a worker manager
    wm = WorkerManager(num_workers=4)

    # And pass some tasks
    for _ in range(11):
        wm.add_task(**sleep_task)

    return wm

@pytest.fixture
def rf_list() -> list:
    """Returns a list of report formats; this will invoke them with their
    default settings."""
    return ['runtime', 'task_counters', 'progress', 'progress_bar']

@pytest.fixture
def rf_dict() -> dict:
    """Returns a report format dict."""
    raise NotImplementedError

@pytest.fixture
def rep(wm, rf_list) -> WorkerManagerReporter:
    """Returns a WorkerManagerReporter"""
    return WorkerManagerReporter(wm, report_formats=rf_list,
                                 default_format='runtime')

# Tests -----------------------------------------------------------------------

def test_init(wm, rf_list):
    """Test initialisation of the WorkerManagerReporter"""
    rep = WorkerManagerReporter(wm, report_formats=rf_list)

    # Associating another one with the same WorkerManager should fail
    with pytest.raises(RuntimeError, match="Already set the reporter"):
        WorkerManagerReporter(wm)

    # Ensure correct association
    assert rep.wm is wm
    assert wm._reporter is rep

def test_report(rep):
    """Tests the report method."""
    # Test the default report format
    assert rep.report()

    # Other report formats
    assert rep.report('task_counters')
    assert rep.report('progress')
    assert rep.report('progress_bar')

def test_task_counter(rep):
    """Tests the task_counters property"""

    # Assert initial worker manager state is as desired
    tc = rep.task_counters
    assert tc['total'] == 11
    assert tc['queued'] == 11
    assert tc['active'] == 0
    assert tc['finished'] == 0

    # Let the WorkerManager work and then test again
    rep.wm.start_working()

    tc = rep.task_counters
    assert tc['total'] == 11
    assert tc['queued'] == 0
    assert tc['active'] == 0
    assert tc['finished'] == 11

def test_parsers(rep, sleep_task):
    """Tests the custom parser methods of the WorkerManagerReporter that is
    written for simple terminal reports
    """

    # Disable minimum report interval and create shortcuts to the parse methods
    rep.min_report_intv = None
    ptc = rep._parse_task_counters
    pp = rep._parse_progress
    ppb = lambda *a, **kws: rep._parse_progress_bar(*a, num_cols=19, **kws)

    # Test the initial return strings
    assert ptc() == "total: 11,  queued: 11,  active: 0,  finished: 0"
    assert pp() == "Finished   0 / 11  (0.0%)"
    assert ppb() == "╠          ╣   0.0%"
    
    # Start working and check again afterwards
    rep.wm.start_working()
    assert ptc() == "total: 11,  queued: 0,  active: 0,  finished: 11"
    assert pp() == "Finished  11 / 11  (100.0%)"
    assert ppb() == "╠▓▓▓▓▓▓▓▓▓▓╣ 100.0%"

    # Add another task to the WorkerManager, which should change the counts
    rep.wm.add_task(**sleep_task)
    assert ptc() == "total: 12,  queued: 1,  active: 0,  finished: 11"
    assert pp() == "Finished  11 / 12  (91.7%)"
    assert ppb() == "╠▓▓▓▓▓▓▓▓▓ ╣  91.7%"
