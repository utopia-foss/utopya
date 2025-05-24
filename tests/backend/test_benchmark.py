"""Tests the benchmark mixin"""

import time

import pytest

from utopya.tools import write_yml
from utopya_backend import ModelBenchmarkMixin
from utopya_backend.benchmark import (
    DEFAULT_TIMERS_CUMULATIVE,
    DEFAULT_TIMERS_ONE_SHOT,
    Timer,
)

from .._fixtures import *
from .test_model import MyModel, MyStepwiseModel, minimal_pspace_cfg

# -----------------------------------------------------------------------------


class BenchmarkedBaseModel(ModelBenchmarkMixin, MyModel):
    def should_write(self):
        return True


class BenchmarkedModel(ModelBenchmarkMixin, MyStepwiseModel):
    pass


# -----------------------------------------------------------------------------


def test_Timer_init():
    t = Timer("foo")
    assert t.name == "foo"
    assert not t.running
    assert not t.finished
    assert t.elapsed == 0.0
    assert t.one_shot is False

    assert "Timer 'foo'" in str(t)
    assert "0s elapsed" in str(t)
    assert "running" not in str(t)
    assert "finished" not in str(t)

    # One-shot timer
    t = Timer("bar", one_shot=True)
    assert t.name == "bar"
    assert not t.running
    assert not t.finished
    assert t.elapsed == 0.0
    assert t.one_shot is True

    # Custom time function
    t = Timer("bar", time_func=time.time)


def test_timer_operation():
    DT = 0.05
    match_is_finished = "was already marked as finished"
    match_is_one_shot = "is a one-shot timer"
    match_is_paused = "Cannot pause already paused timer"

    def sleep(dt=DT):
        time.sleep(dt)

    # Regular operation
    t = Timer("foo")
    assert t.elapsed == 0.0
    assert not t.running

    t.start()
    assert t.running
    sleep()

    assert "running" in str(t)
    assert "finished" not in str(t)

    # Can get elapsed time without pausing
    t1 = t.elapsed
    assert t1 >= DT

    # After pausing, timer does not continue
    t.pause()
    assert not t.running

    t2 = t.elapsed
    assert t2 >= t1
    sleep()
    assert t.elapsed == t2

    # Can unpause to continue
    t.unpause()
    sleep()
    t3 = t.elapsed
    assert t3 > t2 + DT
    assert t.running

    # pause has a return value
    t4 = t.pause()
    assert not t.running
    sleep()

    # can stop a paused timer (and also have a return value)
    assert t.stop() == t4
    assert t.finished

    # Can directly start a timer
    t = Timer("bar", start=True)
    assert t.elapsed > 0.0
    t.pause()

    # Cannot pause a paused timer
    with pytest.raises(RuntimeError, match=match_is_paused):
        t.pause()

    # Cannot modify a finished timer
    t.stop()
    assert t.elapsed > 0.0
    assert t.finished
    assert not t.running

    assert "running" not in str(t)
    assert "finished" in str(t)

    with pytest.raises(RuntimeError, match=match_is_finished):
        t.start()

    with pytest.raises(RuntimeError, match=match_is_finished):
        t.unpause()

    with pytest.raises(RuntimeError, match=match_is_finished):
        t.pause()

    with pytest.raises(RuntimeError, match=match_is_finished):
        t.stop()

    # Cannot unpause or restart a one-shot timer
    t = Timer("baz", one_shot=True, start=True)
    assert t.running
    assert t.elapsed > 0.0
    assert not t.finished
    t.pause()

    with pytest.raises(RuntimeError, match=match_is_one_shot):
        t.unpause()

    with pytest.raises(RuntimeError, match=match_is_finished):
        t.start()


def test_ModelBenchmarkMixin(minimal_pspace_cfg, tmpdir):
    cfg = minimal_pspace_cfg
    cfg["root_model_name"] = "MyStepwiseModel"
    cfg["MyStepwiseModel"] = dict(
        sleep_time=0.01,
        benchmark=dict(
            enabled=True,
            add_to_monitor=True,
            info_fstr="⏲️ {time_str:>13s}   {percent_of_max:5.1f}%   {name:s}",
            info_kwargs=dict(sort=True),
        ),
    )
    cfg["monitor_emit_interval"] = 0.1
    cfg["num_steps"] = 42

    cfg_path = tmpdir.join("cfg.yml")
    write_yml(cfg, path=cfg_path)

    # Initialize it, running init and setup
    m = BenchmarkedModel(cfg_file_path=cfg_path)

    print("one shot:", m.elapsed_one_shot)
    print("cumulative:", m.elapsed_cumulative)
    print("\n".join(f"{n}: {t}" for n, t in m.timers.items()))

    INIT_TIMERS = ("init", "setup", "monitor")
    assert all(not t.running for n, t in m.timers.items() if n != "simulation")
    assert all(
        not t.finished for n, t in m.timers.items() if n not in INIT_TIMERS
    )
    assert all(
        t.elapsed == 0
        for n, t in m.timers.items()
        if n not in INIT_TIMERS + ("simulation",)
    )

    assert m.timers["simulation"].running
    assert m.timers["simulation"].elapsed > 0

    # Key errors
    with pytest.raises(ValueError, match="No benchmark timer named"):
        m.start_timer("i do not exist")

    # Let it run and check timers again
    m.run()

    print("one shot:", m.elapsed_one_shot)
    print("cumulative:", m.elapsed_cumulative)
    print("\n".join(f"{n}: {t}" for n, t in m.timers.items()))

    # ... all should have run and be finished now (except teardown)
    timers = [t for n, t in m.timers.items() if n != "teardown"]
    assert all(not t.running for t in timers)
    assert all(t.finished for t in timers)
    assert all(t.elapsed > 0 for t in timers)

    # Test formatting
    assert "⏲️" in m.elapsed_info
    assert "⏲️" in m.format_elapsed_info()
    assert "⏲️" not in m.format_elapsed_info("{w:}", width=10, sort=False)
    assert "⌛" in m.format_elapsed_info("{x:}", x="⌛")

    # Delete the model
    timers = m.timers
    del m
    assert timers["teardown"].elapsed > 0.0
    assert timers["teardown"].finished


def test_ModelBenchmarkMixin_in_basemodel(minimal_pspace_cfg, tmpdir):
    cfg = minimal_pspace_cfg
    cfg["root_model_name"] = "MyModel"
    cfg["MyModel"] = dict(
        some_param="foo", max_n_iter=13, benchmark=dict(enabled=True)
    )

    cfg_path = tmpdir.join("cfg.yml")
    write_yml(cfg, path=cfg_path)

    # Initialize it, running init and setup
    m = BenchmarkedBaseModel(cfg_file_path=cfg_path)

    print("one shot:", m.elapsed_one_shot)
    print("cumulative:", m.elapsed_cumulative)
    print("\n".join(f"{n}: {t}" for n, t in m.timers.items()))

    INIT_TIMERS = ("init", "setup", "monitor")
    assert all(not t.running for n, t in m.timers.items() if n != "simulation")
    assert all(
        not t.finished for n, t in m.timers.items() if n not in INIT_TIMERS
    )
    assert all(
        t.elapsed == 0
        for n, t in m.timers.items()
        if n not in INIT_TIMERS + ("simulation",)
    )

    assert m.timers["simulation"].running
    assert m.timers["simulation"].elapsed > 0

    # Key errors
    with pytest.raises(ValueError, match="No benchmark timer named"):
        m.start_timer("i do not exist")

    # Let it run and check timers again
    m.run()

    print("one shot:", m.elapsed_one_shot)
    print("cumulative:", m.elapsed_cumulative)
    print("\n".join(f"{n}: {t}" for n, t in m.timers.items()))

    # ... all should have run and be finished now (except teardown)
    timers = [t for n, t in m.timers.items() if n not in ("teardown",)]
    assert all(not t.running for t in timers)
    assert all(t.finished for t in timers)
    assert all(t.elapsed > 0 for t in timers)

    # Delete the model
    timers = m.timers
    del m
    assert timers["teardown"].elapsed > 0.0
    assert timers["teardown"].finished


def test_ModelBenchmarkMixin_disabled(minimal_pspace_cfg, tmpdir):
    cfg = minimal_pspace_cfg
    cfg["root_model_name"] = "MyStepwiseModel"
    cfg["MyStepwiseModel"] = dict(
        sleep_time=0.01, benchmark=dict(enabled=False)
    )
    cfg["monitor_emit_interval"] = 0.1
    cfg["num_steps"] = 42

    cfg_path = tmpdir.join("cfg.yml")
    write_yml(cfg, path=cfg_path)

    # Initialize it
    m = BenchmarkedModel(cfg_file_path=cfg_path)
    print(m.elapsed)
    print("\n".join(f"{n}: {t}" for n, t in m.timers.items()))

    # All timers should be reset.
    assert all(not t.running for t in m.timers.values())
    assert all(not t.finished for t in m.timers.values())
    assert all(t.elapsed == 0 for t in m.timers.values())

    # Let it run and check timers again
    m.run()
    print(m.elapsed)
    print("\n".join(f"{n}: {t}" for n, t in m.timers.items()))

    # None should have run
    assert all(not t.running for t in m.timers.values())
    assert all(not t.finished for t in m.timers.values())
    assert all(t.elapsed == 0 for t in m.timers.values())

    # Delete the model
    timers = m.timers
    del m
    assert timers["teardown"].elapsed == 0.0
    assert not timers["teardown"].finished
