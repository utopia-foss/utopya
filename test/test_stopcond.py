"""Test the stopcond module"""

import time
import subprocess

import pytest

from utopya.tools import yaml
import utopya.stopcond as sc
import utopya.stopcond_funcs as sc_funcs
from utopya.task import WorkerTask

# Fixtures --------------------------------------------------------------------
@pytest.fixture
def basic_sc():
    """Returns a basic StopCondition object that checks the mock timeout_wall method."""
    return sc.StopCondition(to_check=[dict(func=sc_funcs.timeout_wall,
                                           seconds=123)],
                            name="wall timeout")

@pytest.fixture
def task() -> WorkerTask:
    """Generates a WorkerTask object, manipulating it somewhat"""
    task = WorkerTask(name="foo", worker_kwargs=dict(args=('echo','$?')))
    task.profiling['create_time'] = time.time() - 124.

    return task

# Tests of the class ----------------------------------------------------------

def test_init():
    """Test StopCondition initialization"""
    sc.StopCondition(to_check=[dict(func=sc_funcs.timeout_wall, seconds=123)])

    # Empty should also work
    sc.StopCondition(to_check=[])
    
    # These should fail
    # no to_check argument
    with pytest.raises(TypeError, match="Need at least one of the required"):
        sc.StopCondition()
    
    # invalid function name
    with pytest.raises(TypeError, match="`func` needs to be a callable"):
        sc.StopCondition(to_check=[dict(func="I am not a function.")])

    # too many arguments
    with pytest.raises(ValueError, match="Please pass either"):
        sc.StopCondition(to_check=[dict(func=sc_funcs.timeout_wall,
                                        seconds=123)],
                         func=sc_funcs.timeout_wall)

def test_constructors():
    """Tests the YAML constructor"""
    ymlstr1 = "sc: !stop-condition {to_check: [], name: foo, description: bar}"
    assert isinstance(yaml.load(ymlstr1)['sc'], sc.StopCondition)

    ymlstr2 = "sc: !stop-condition [1, 2, 3]"
    with pytest.raises(TypeError):
        yaml.load(ymlstr2)

    ymlstr3 = "scf: !sc-func timeout_wall"
    assert yaml.load(ymlstr3)['scf'] is sc_funcs.timeout_wall

    # non-scalar node type
    ymlstr4 = "scf: !sc-func [timeout_wall, foo, bar]"
    with pytest.raises(TypeError):
        yaml.load(ymlstr4)
    
    # non-scalar node type
    ymlstr5 = "scf: !sc-func non_existant_function"
    with pytest.raises(ImportError):
        yaml.load(ymlstr5)
        

def test_magic_methods(basic_sc):
    """Tests magic methods of the StopCond class."""
    str(basic_sc)

def test_fulfilled(basic_sc, task):
    """Tests magic methods of the StopCond class."""
    # Test if it is fulfilled (should always be the case when using the fixtures)
    assert basic_sc.fulfilled(task) is True

    # Disable it: should now be false
    basic_sc.enabled = False
    assert basic_sc.fulfilled(task) is False

# Tests of the stop condition methods -----------------------------------------
