"""Tests the Reporter class and derived classes."""

import re
import time
from datetime import datetime as dt
from datetime import timedelta

import pytest

from utopya.reporter import Reporter, WorkerManagerReporter
from utopya.workermanager import WorkerManager

# Local constants
MIN_REP_INTV = 0.1
SLEEP_TIME = 0.1

# Fixtures --------------------------------------------------------------------


@pytest.fixture
def sleep_task() -> dict:
    """The kwargs for a sleep task"""
    sleep_args = (
        "python3",
        "-c",
        f"from time import sleep; sleep({SLEEP_TIME})",
    )
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
    return ["task_counters", "progress", "progress_bar", "times"]


@pytest.fixture
def rf_dict() -> dict:
    """Returns a report format dict."""
    return dict(
        tasks=dict(parser="task_counters", min_report_intv=MIN_REP_INTV),
        progress=dict(
            min_report_intv=MIN_REP_INTV,
            write_to=dict(
                log=dict(lvl=5), stdout=dict(end="\r"), stdout_noreturn=dict()
            ),
        ),
        short_progress_bar=dict(parser="progress_bar", num_cols=19),
        times=dict(),
        while_working=dict(parser="times"),
        after_work=dict(parser="times"),
    )


@pytest.fixture
def rep(wm, rf_list, tmpdir) -> WorkerManagerReporter:
    """Returns a WorkerManagerReporter"""
    return WorkerManagerReporter(
        wm,
        report_dir=tmpdir,
        report_formats=rf_list,
        default_format="task_counters",
    )


# Tests -----------------------------------------------------------------------


def test_init(wm):
    """Test simplest initialisation of the WorkerManagerReporter"""
    rep = WorkerManagerReporter(wm)

    # Associating another one with the same WorkerManager should fail
    with pytest.raises(RuntimeError, match="Already set the reporter"):
        WorkerManagerReporter(wm)

    # Ensure correct association
    assert rep.wm is wm
    assert wm._reporter is rep


def test_init_with_rf_list(wm, rf_list):
    """Test initialisation of the WorkerManagerReporter with report formats"""
    rep = WorkerManagerReporter(wm, report_formats=rf_list)


def test_init_with_rf_dict(wm, rf_dict):
    """Test initialisation of the WorkerManagerReporter"""
    rep = WorkerManagerReporter(
        wm, report_formats=rf_dict, default_format="progress"
    )


def test_resolve_writers(rep):
    """Tests the _resolve_writers method."""
    rw = rep._resolve_writers

    # Test passing a callable directly
    assert rw(print) == {print.__name__: print}

    # A list or tuple of callables
    assert rw([print]) == {print.__name__: print}
    assert rw((print,)) == {print.__name__: print}

    # A mixed list or tuple of strings and callables
    assert rw([print, "stdout"]) == {
        print.__name__: print,
        "stdout": rep._write_to_stdout,
    }
    assert rw((print, "stdout")) == {
        print.__name__: print,
        "stdout": rep._write_to_stdout,
    }

    # With invalid types, this should fail
    with pytest.raises(TypeError, match="Invalid type "):
        rw(123)
    with pytest.raises(TypeError, match="One item of given `write_to` "):
        rw([print, 123])
    with pytest.raises(TypeError, match="One item of given `write_to` "):
        rw(["stdout", 123])

    # With the callable already existing, this should also fail
    with pytest.raises(ValueError, match="Given writer callable with name "):
        rw([print, print])

    # Invalid writer name
    with pytest.raises(ValueError, match="No writer named"):
        rw("invalid")


def test_add_report_format(rep):
    """Test the add_report_format method"""

    add_rf = rep.add_report_format

    # Adding formats with the same name should not work
    with pytest.raises(ValueError, match="A report format with the name"):
        add_rf("task_counters")

    # Invalid write_to argument
    with pytest.raises(
        TypeError, match="Invalid type <class 'int'> for argument"
    ):
        add_rf("foo", parser="progress", write_to=1)
    with pytest.raises(
        TypeError, match="One item of given `write_to` argument"
    ):
        add_rf("foo", parser="progress", write_to=(1, 2, 3))

    # Invalid parser
    with pytest.raises(ValueError, match="No parser named"):
        add_rf("invalid")

    # Invalid writer
    with pytest.raises(ValueError, match="No writer named"):
        add_rf("foo", parser="progress", write_to="invalid")


def test_task_counter(rep):
    """Tests the task_counters property"""

    # Assert initial worker manager state is as desired
    tc = rep.task_counters
    assert tc["total"] == 11
    assert tc["active"] == 0
    assert tc["finished"] == 0

    # Let the WorkerManager work and then test again
    rep.wm.start_working()

    tc = rep.task_counters
    assert tc["total"] == 11
    assert tc["active"] == 0
    assert tc["finished"] == 11


def test_wm_progress(sleep_task):
    """Tests the wm_progress property"""
    wm = WorkerManager(num_workers=2)
    rep = WorkerManagerReporter(wm)

    # Should be zero if there are no tasks
    assert rep._compute_progress()["total"] == 0.0

    # Should still be zero after having added a task
    wm.add_task(**sleep_task)
    assert rep._compute_progress()["total"] == 0.0

    # Should be 1. after working
    wm.start_working()
    assert rep._compute_progress()["total"] == 1.0


def test_wm_times(rep):
    """Test the wm_times property"""
    t1 = rep.wm_times
    assert t1["start"] is None
    assert "now" in t1
    assert t1["elapsed"] is None
    assert t1["est_left"] is None
    assert t1["est_end"] is None

    # Work
    rep.wm.start_working()

    t2 = rep.wm_times
    assert t2["start"] is rep.wm.times["start_working"]
    assert "now" in t2 and t2["now"] > t1["now"]
    assert t2["elapsed"]
    assert t2["est_left"].total_seconds() == 0.0
    assert t2["est_end"] < dt.now()


def test_est_left(rep):
    """Tests (parts of) time left estimation function"""
    cmp_est_left = rep._compute_est_left

    # .. Default mode: from_start
    # Without skipped tasks, it's easy:
    elapsed = timedelta(seconds=2.0)
    assert (
        cmp_est_left(
            progress=dict(skipped=0, total=0.1), elapsed=elapsed
        ).total_seconds()
        == 18.0
    )
    assert (
        cmp_est_left(
            progress=dict(skipped=0, total=0.5), elapsed=elapsed
        ).total_seconds()
        == 2.0
    )
    assert (
        cmp_est_left(
            progress=dict(skipped=0, total=1.0), elapsed=elapsed
        ).total_seconds()
        == 0.0
    )

    # Not meant to be called if no progress was made, but avoids zero-div error
    assert (
        cmp_est_left(progress=dict(skipped=0, total=0.0), elapsed=elapsed)
        is None
    )

    # Computation is different with skipped tasks
    assert (
        cmp_est_left(
            progress=dict(skipped=1, worked_on=10, left_to_do=10),
            elapsed=elapsed,
        ).total_seconds()
        == 2.0
    )
    assert (
        cmp_est_left(
            progress=dict(skipped=10, worked_on=10, left_to_do=10),
            elapsed=elapsed,
        ).total_seconds()
        == 2.0
    )
    assert (
        cmp_est_left(
            progress=dict(skipped=10, worked_on=5, left_to_do=15),
            elapsed=elapsed,
        ).total_seconds()
        == 6.0
    )

    assert (
        cmp_est_left(
            progress=dict(skipped=1, worked_on=0, left_to_do=10),
            elapsed=elapsed,
        )
        is None
    )

    # Progress buffer
    assert (
        cmp_est_left(
            progress=dict(total=0),
            elapsed=elapsed,
            mode="from_buffer",
        )
        is None
    )
    assert "progress_buffer" not in rep._eta_info

    assert (
        cmp_est_left(
            progress=dict(total=0.1),
            elapsed=elapsed,
            mode="from_buffer",
        ).total_seconds()
        == 18.0
    )
    assert len(rep._eta_info["progress_buffer"]) == 2  # have 0-value in there

    # Invalid mode
    with pytest.raises(ValueError, match="Invalid ETA computation mode"):
        cmp_est_left(mode="bad_mode", progress=dict(), elapsed=elapsed)


def test_parsers(rf_dict, sleep_task):
    """Tests the custom parser methods of the WorkerManagerReporter that is
    written for simple terminal reports
    """
    wm = WorkerManager(num_workers=4)
    rep = WorkerManagerReporter(wm, report_formats=rf_dict)

    # Disable minimum report interval and create shortcuts to the parse methods
    rep.min_report_intv = None
    ptc = rep._parse_task_counters
    pdw = rep._parse_distributed_work_status
    pp = rep._parse_progress
    pps = rep._parse_pspace_info
    pr = rep._parse_report
    ppb = lambda *a, n=23, **kws: rep._parse_progress_bar(
        *a, num_cols=n, **kws
    )
    ppbt = lambda *a, n=30, **kws: rep._parse_progress_bar(
        *a,
        num_cols=n,
        **kws,
        info_fstr="{prg[total]:>5.1f}%  of {cnt[total]} ",
    )
    ppbtt = lambda *a, n=60, **kws: rep._parse_progress_bar(
        *a, num_cols=n, show_times=True, **kws
    )

    # Test without tasks assigned
    assert ptc() == (
        "total: 0,  active: 0,  finished: 0,  invoked: 0,  spawned: 0,  "
        "success: 0,  skipped: 0,  stopped: 0,  failed: 0,  worked_on: 0"
    )
    assert pp() == "(No tasks assigned to WorkerManager yet.)"
    assert ppb() == "(No tasks assigned to WorkerManager yet.)"
    assert ppbt() == "(No tasks assigned to WorkerManager yet.)"
    assert ppbtt() == "(No tasks assigned to WorkerManager yet.)"
    assert "No Multiverse associated" in pdw()

    assert "Work has not begun yet." in pr()
    assert "No tasks defined." in pr()

    with pytest.raises(ValueError, match="No Multiverse associated"):
        pps()

    # Assign tasks to wm
    for _ in range(11):
        wm.add_task(**sleep_task)

    # Test the initial return strings
    assert ptc() == (
        "total: 11,  active: 0,  finished: 0,  invoked: 0,  spawned: 0,  "
        "success: 0,  skipped: 0,  stopped: 0,  failed: 0,  worked_on: 0"
    )
    assert pp() == "Finished   0 / 11  (0.0%, 0 skipped)"
    assert ppb() == "  ╠           ╣   0.0% "
    assert ppbt() == "  ╠           ╣   0.0%  of 11 "
    assert re.match("  ╠(.*)╣   0.0% | * elapsed | ~* left  ", ppbtt())

    # For the progress bars, ensure the length matches the given num_cols
    assert len(ppb()) == 23
    assert len(ppbt()) == 30
    assert len(ppbtt()) == 60

    # Start working and check again afterwards
    rep.wm.start_working()
    assert ptc() == (
        "total: 11,  active: 0,  finished: 11,  invoked: 11,  spawned: 11,  "
        "success: 11,  skipped: 0,  stopped: 0,  failed: 0,  worked_on: 11"
    )
    assert pp() == "Finished  11 / 11  (100.0%, 0 skipped)"
    assert ppb() == "  ╠▓▓▓▓▓▓▓▓▓▓▓╣ 100.0% "
    assert ppbt() == "  ╠▓▓▓▓▓▓▓▓▓▓▓╣ 100.0%  of 11 "
    assert re.match("  ╠(▓*)╣ 100.0% | finished in *  ", ppbtt())

    # Add another task to the WorkerManager, which should change the counts
    rep.wm.add_task(**sleep_task)
    assert ptc() == (
        "total: 12,  active: 0,  finished: 11,  invoked: 11,  spawned: 11,  "
        "success: 11,  skipped: 0,  stopped: 0,  failed: 0,  worked_on: 11"
    )
    assert pp() == "Finished  11 / 12  (91.7%, 0 skipped)"
    assert ppb() == "  ╠▓▓▓▓▓▓▓▓▓▓ ╣  91.7% "
    assert ppbt() == "  ╠▓▓▓▓▓▓▓▓▓▓ ╣  91.7%  of 12 "
    assert re.match("  ╠(▓*)(.*)╣  91.7% | * elapsed | ~* left  ", ppbtt())

    # Very short progress bar should return only the percentage indicator
    assert rep._parse_progress_bar(num_cols=10) == "  91.7% "

    # Can also use adaptive or fixed number of columns
    print("fixed:    ", ppb(n="fixed"))
    print("adaptive: ", ppb(n="adaptive"))
    assert re.match(r"  ╠(▓*)(.*)╣  91\.7% ", ppb(n="fixed"))
    assert re.match(r"  ╠(▓*)(.*)╣  91\.7% ", ppb(n="adaptive"))

    # Parsing time is fast, even for adaptive column width
    N = 10000

    t0 = dt.now()
    for _ in range(N):
        ppbtt(n="adaptive")
    seconds_needed = (dt.now() - t0).total_seconds()
    print(f"Needed {seconds_needed:.3g}s for parsing progress bar {N} times.")
    assert float(seconds_needed / N) < 500.0e-6  # very generous -> more robust

    # ... or with advanced ETA estimation
    t0 = dt.now()
    for _ in range(N):
        ppbtt(n="adaptive", times_kwargs=dict(mode="from_buffer"))
    seconds_needed = (dt.now() - t0).total_seconds()
    print(
        f"Needed {seconds_needed:.3g}s for parsing progress bar (with "
        f"advanced ETA estimation) {N} times."
    )
    assert float(seconds_needed / N) < 500.0e-6  # very generous -> more robust


def test_report(rep):
    """Tests the report method."""
    # Test the default report format
    assert rep.report()

    # Other, explicitly specified, report formats
    assert rep.report("task_counters")
    assert rep.report("progress")
    assert rep.report("progress_bar")
    assert rep.report("times")

    # Invalid report formats
    with pytest.raises(KeyError):
        rep.report("foo")

    # Without default format
    rep.default_format = None
    with pytest.raises(ValueError, match="Either a default format needs"):
        rep.report()


def test_min_report_intv(wm, rf_dict):
    """Test correct behaviour of the minimum report interval"""
    rep = WorkerManagerReporter(
        wm, report_formats=rf_dict, default_format="progress"
    )

    # This should work
    assert rep.report()

    # Now this should hit the minimum report interval
    assert not rep.report()
    assert not rep.report()

    # After sleeping, this should work again
    time.sleep(MIN_REP_INTV)
    assert rep.report()

    # And blocked again ...
    assert not rep.report()


def test_parse_and_write(rep):
    """Tests the parse_and_write function"""
    rep.parse_and_write(parser="progress", write_to="stdout")
    rep.parse_and_write(parser="progress", write_to="log")


def test_runtime_statistics(rep):
    """Tests the runtime statistics gathering and parsing.

    NOTE that this does not test the results of the _calculations_ of the
    run times; there, it is trusted that the used numpy methods do what they
    are supposed to do.
    """
    # In the beginning, there should be no run times registered
    assert not rep.runtimes

    # The runtime statistics should be empty now
    assert len(rep.calc_runtime_statistics()) == 0

    # After working, there should be some more entries
    rep.wm.start_working()
    assert len(rep.runtimes) == 11

    # Calculate the runtime statistics
    rtstats = rep.calc_runtime_statistics()
    print("Runtime Statistics: ", rtstats)

    # All entries but the std should be larger than the sleep time of the task
    for key, val in rtstats.items():
        print("Testing key: ", key, "=", val)
        if key == "std":
            assert val > 0.0
        elif key.startswith("num_"):
            assert isinstance(val, int)
        else:
            assert val > SLEEP_TIME

    # Test if it also works with some Nones thrown in there
    rep.runtimes.append(None)
    assert rep.calc_runtime_statistics()

    # Test the parsing method:
    assert rep._parse_runtime_stats()


def test_parse_times(rep):
    """Test the _parse_elapsed function"""
    pt = rep._parse_times

    # Not having worked:
    assert pt() == (
        "Elapsed:  (not started)  |  "
        "Est. left:  ∞         |  "
        "Est. end:  (unknown) "
    )

    # Start working and then check again
    rep.wm.start_working()
    assert pt()

    # Create dummy times dict to use for testing the other cases
    # Use one now() definition for that
    now = dt.now()

    # Not started yet
    times = dict(
        start=None,
        now=now,
        elapsed=None,
        est_left=None,
        est_end=None,
        end=None,
    )
    assert pt(times=times)

    # Just started, finish tomorrow
    times = dict(
        start=now,
        now=now,
        elapsed=timedelta(0),
        est_left=timedelta(1),  # 1 day
        est_end=now + timedelta(1),  # tomorrow
        end=None,
    )

    assert pt(times=times)

    # Move the est end into the future one more day
    times["est_end"] += timedelta(1)
    assert pt(times=times)

    # Simulation started yesterday and ends today (~now)
    times = dict(
        start=now - timedelta(1),
        now=now,
        elapsed=timedelta(1),
        est_left=timedelta(0),
        est_end=now,
        end=None,
    )
    assert pt(times=times)


def test_suppress_cr(wm, tmpdir, capsys):
    """Test whether the writers are able to suppress CR characters"""
    rep = WorkerManagerReporter(wm, report_dir=tmpdir)
    rep.suppress_cr = True

    # This should have written a line break
    captured = capsys.readouterr()
    assert captured.out == "\n"

    # Write more
    rep._write_to_stdout(
        "foo",
    )
    rep._write_to_stdout("bar", end="\n")
    rep._write_to_stdout("baz", end="\r")
    rep._write_to_stdout_noreturn("spam", prepend="")

    # Assert that no \r were written
    captured = capsys.readouterr()
    assert captured.out == "foo\nbar\nbaz\nspam\n"


def test_write_to_file(wm, rf_dict, tmpdir):
    """Test writing to a file."""
    rep = WorkerManagerReporter(wm, report_dir=tmpdir)

    rep.parse_and_write(parser="task_counters", write_to="file")
    report_file = tmpdir.join("_report.txt")
    assert report_file.isfile()

    # Read file content
    with open(str(report_file)) as f:
        assert f.read() == (
            "total: 11,  active: 0,  finished: 0,  invoked: 0,  spawned: 0,  "
            "success: 0,  skipped: 0,  stopped: 0,  failed: 0,  worked_on: 0"
        )

    # Unset the report directory and try with relative path
    rep.report_dir = None

    with pytest.raises(ValueError):
        rep.parse_and_write(parser="task_counters", write_to="file")
