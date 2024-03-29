"""Test the stopcond module"""

import io
import subprocess
import time

import pytest
import ruamel.yaml

import utopya.stop_conditions as sc
from utopya.task import WorkerTask
from utopya.tools import yaml

SC_FUNCS = sc.STOP_CONDITION_FUNCS
timeout_wall = SC_FUNCS["timeout_wall"]
check_monitor_entry = SC_FUNCS["check_monitor_entry"]


# Fixtures --------------------------------------------------------------------
@pytest.fixture
def basic_sc():
    """Returns a basic StopCondition object that checks the mock timeout_wall
    method."""
    return sc.StopCondition(
        to_check=[dict(func=timeout_wall, seconds=123)],
        name="wall timeout",
    )


@pytest.fixture
def false_true_sc():
    return sc.StopCondition(
        to_check=[dict(func=lambda _: False), dict(func=lambda _: True)],
        name="false and true",
    )


@pytest.fixture
def task() -> WorkerTask:
    """Generates a WorkerTask object, manipulating it somewhat to act as a
    mock object.
    """
    task = WorkerTask(name="foo", worker_kwargs=dict(args=("echo", "$?")))

    task.profiling["create_time"] = time.time() - 124.0
    task.streams["out"] = dict(log_parsed=[])

    return task


# Tests of the class ----------------------------------------------------------


def test_init():
    """Test StopCondition initialization"""
    sc0 = sc.StopCondition(to_check=[dict(func=timeout_wall, seconds=123)])

    # Empty should also work
    sc.StopCondition(to_check=[])

    # These should fail
    # no to_check argument
    with pytest.raises(TypeError, match="Need at least one of the required"):
        sc.StopCondition()

    # invalid function name
    with pytest.raises(ValueError, match="No stop condition function"):
        sc.StopCondition(to_check=[dict(func="I am not a function.")])

    # non-callable
    with pytest.raises(TypeError, match="Expected callable or name of a reg"):
        sc.StopCondition(to_check=[dict(func=123.456)])

    # too many arguments
    with pytest.raises(ValueError, match="Please pass either"):
        sc.StopCondition(
            to_check=[dict(func=timeout_wall, seconds=123)],
            func=timeout_wall,
        )

    # Basic interface checks:
    assert not sc0.fulfilled_for
    assert "timeout_wall" in str(sc0)
    assert sc0.enabled is True
    assert not sc0.description
    assert len(sc0.to_check) == 1
    assert sc0.to_check[0] == (timeout_wall, "timeout_wall", dict(seconds=123))


def test_constructor():
    """Tests the YAML constructor"""
    ymlstr1 = "sc: !stop-condition {to_check: [], name: foo, description: bar}"
    assert isinstance(yaml.load(ymlstr1)["sc"], sc.StopCondition)

    ymlstr2 = "sc: !stop-condition [1, 2, 3]"
    with pytest.raises(ruamel.yaml.constructor.ConstructorError):
        yaml.load(ymlstr2)


def test_representer():
    """Tests the YAML constructor"""
    sc1 = sc.StopCondition(func="timeout_wall", seconds=123)

    with io.StringIO() as f:
        yaml.dump(sc1, stream=f)
        print(f.getvalue())
        assert f.getvalue() == (
            "!stop-condition {func: timeout_wall, " "seconds: 123}\n"
        )


def test_magic_methods(basic_sc, false_true_sc):
    """Tests magic methods of the StopCond class."""
    assert basic_sc.description is None
    s1 = str(basic_sc)
    assert basic_sc.name in s1

    # with description
    basic_sc.description = "foo bar"
    s2 = str(basic_sc)
    assert s1 != s2
    assert basic_sc.name in s2
    assert basic_sc.description in s2

    # with multiple to_check
    s3 = str(false_true_sc)
    assert false_true_sc.name in s3

    # without name: auto-generating one
    sc4 = sc.StopCondition(
        to_check=[dict(func=lambda _: False), dict(func=lambda _: True)]
    )
    assert "&&" in str(sc4)


def test_fulfilled(basic_sc, false_true_sc, task):
    """Tests magic methods of the StopCond class."""
    assert not basic_sc.fulfilled_for

    # Test if it is fulfilled (should always be the case for the fixture)
    assert basic_sc.fulfilled(task) is True
    assert task in basic_sc.fulfilled_for

    # Disable it: should now be false
    basic_sc.enabled = False
    assert basic_sc.fulfilled(task) is False

    # Task is still in the set, because it was checked previously
    assert task in basic_sc.fulfilled_for

    # Test with a stop condition that has multiple to_check entries
    sc = false_true_sc
    assert not sc.fulfilled_for
    assert not false_true_sc.fulfilled(task)
    assert not sc.fulfilled_for


def test_stop_condition_function_decorator():
    """Tests the ``stop_condition_function`` decorator that adds an entry to
    the registry.
    """
    num_sc_funcs = len(SC_FUNCS)

    @sc.stop_condition_function
    def foo(t) -> bool:
        return False

    assert len(SC_FUNCS) == num_sc_funcs + 1

    # Remove the entry again
    del SC_FUNCS["foo"]
    assert len(SC_FUNCS) == num_sc_funcs

    # Check the error message upon an existing entry
    assert "timeout_wall" in SC_FUNCS
    with pytest.raises(AttributeError, match="already registered"):

        @sc.stop_condition_function
        def timeout_wall(t) -> bool:
            pass

    assert "timeout_wall" in SC_FUNCS


# Tests of the stop condition methods -----------------------------------------


def test_check_monitor_entry(task):
    """Test the check_monitor_entry stop condition function"""
    # Without a parsed object, this is always false, and no other checks are
    # actually performed
    assert not check_monitor_entry(
        task, entry_name="foo", operator="bar", value="baz"
    )

    # Add a mock object
    task.outstream_objs.append(dict(foo="bar"))
    assert check_monitor_entry(
        task, entry_name="foo", operator="==", value="bar"
    )
