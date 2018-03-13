"""Test the Task class implementation"""

import numpy as np
import pytest

from utopya.task import Task, WorkerTask, TaskList


# Fixtures ----------------------------------------------------------------

@pytest.fixture
def tasks() -> TaskList:
    """Returns a TaskList filled with tasks"""
    tasks = TaskList()
    for uid, priority in enumerate(np.random.random(size=50)):
        tasks.append(Task(uid=uid, priority=priority))

    return tasks

@pytest.fixture
def workertasks() -> TaskList:
    """Returns a TaskList filled with WorkerTasks"""
    tasks = TaskList()
    for uid, priority in enumerate(np.random.random(size=50)):
        tasks.append(WorkerTask(uid=uid, priority=priority,
                                worker_kwargs=dict(args=('echo', '$?'))))

    return tasks

# Task tests ------------------------------------------------------------------

def test_task_init():
    """Test task initialization"""
    Task(uid=0)
    Task(uid=1, priority=1000)

    # Invalid initialization arguments
    with pytest.raises(TypeError):
        Task(uid=1.23)
    with pytest.raises(ValueError):
        Task(uid=-1)

    # Test that the task ID cannot be changed
    with pytest.raises(RuntimeError):
        t = Task(uid=2)
        t.uid = 3

def test_task_sorting(tasks):
    """Tests whether different task objects are sortable"""
    # Put into a normal list, as the TaskList does not support sorting
    tasks = list(tasks)

    # Sort it, then do some checks
    tasks.sort()

    t1 = tasks[0]
    t2 = tasks[1]

    assert (t1 <= t2) is True
    assert (t1 == t2) is False
    assert (t1 == t1) is True

def test_task_magic_methods(tasks):
    """Test magic methods"""
    _ = [str(t) for t in tasks]


# WorkerTask tests ------------------------------------------------------------

def test_workertask_init():
    """Tests the WorkerTask class"""
    WorkerTask(uid=0, worker_kwargs=dict(foo="bar"))

    with pytest.warns(UserWarning):
        WorkerTask(uid=0, setup_func=print, worker_kwargs=dict(foo="bar"))
    
    with pytest.warns(UserWarning):
        WorkerTask(uid=0, setup_kwargs=dict(foo="bar"),
                   worker_kwargs=dict(foo="bar"))

    with pytest.raises(ValueError):
        WorkerTask(uid=0, )

def test_workertask_magic_methods(workertasks):
    """Test magic methods"""
    _ = [str(t) for t in workertasks]

def test_workertask_invalid_args():
    """It should not be possible to spawn a worker with non-tuple arguments"""
    t = WorkerTask(uid=0, worker_kwargs=dict(args="python -c 'hello hello'"))
    
    with pytest.raises(TypeError):
        t.spawn_worker()

# TaskList tests --------------------------------------------------------------

def test_tasklist(tasks):
    """Tests the TaskList features"""
    # This should work
    for _ in range(3):
        tasks.append(Task(uid=len(tasks)))

    # Or changing a task at a specific position
    tasks[3] = Task(uid=3)

    # This should not: the tasks already exist
    with pytest.raises(ValueError):
        tasks.append(Task(uid=0))

    # Or it was not even a task
    with pytest.raises(TypeError):
        tasks.append(("foo", "bar"))

def test_tasklist_prohibited(tasks):
    """Tests the prohibited methods of this class."""
    prohibited = [
        ('__add__', (None,)),
        ('__iadd__', (None,)),
        ('__delitem__', (0,)),
        ('clear', ()),
        ('insert', (0, "foo")),
        ('pop', (0,)),
        ('reverse', ()),
        ('sort', ()),
        ('remove', (0,)),
        ('extend', ([1,2,3])),
    ]

    for attr_name, args in prohibited:
        with pytest.raises(NotImplementedError):
            getattr(tasks, attr_name)(*args)
