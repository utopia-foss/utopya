"""Tests utopya_backend.base_model"""

import copy
import os
import signal
import time

import pytest

from utopya.testtools import ModelTest
from utopya.tools import load_yml, write_yml
from utopya_backend.model import BaseModel, StepwiseModel
from utopya_backend.signal import SIG_STOPCOND, SIGNAL_INFO

from .. import DUMMY_MODEL
from .._fixtures import *

# -- Fixtures -----------------------------------------------------------------


@pytest.fixture
def minimal_pspace_cfg(with_test_models) -> dict:
    """Returns the minimally necessary parameter space that will get passed to
    the model; does so by instantiating a test Multiverse and starting a run,
    then re-loading the file. This way, it is ensured to be in sync with
    whatever the Multiverse does.
    The model-specific information is stripped from it"""
    mtc = ModelTest(DUMMY_MODEL)
    mv = mtc.create_mv()
    mv.run()

    cfg = load_yml(os.path.join(mv.dirs["data"], "uni0", "config.yml"))
    assert os.path.exists(cfg["output_path"])

    # Drop model-specific content, to be re-added
    del cfg[cfg["root_model_name"]]
    del cfg["root_model_name"]

    # Need to remove the existing output file, otherwise the test model cannot
    # create its output file there.
    os.remove(cfg["output_path"])
    assert not os.path.exists(cfg["output_path"])
    assert os.path.isdir(os.path.dirname(cfg["output_path"]))

    # Yield to model
    # NOTE Important to yield instead of returning, because otherwise the
    #      Multiverse's temporary directory object goes out of scope and leads
    #      to removal of the above directiony, which would require that we
    #      emulate that ... which we don't want.
    yield cfg

    # Can do cleanup here, if necessary


# -- Implementations ----------------------------------------------------------


class MyModel(BaseModel):
    """A test model implementation from BaseModel. This doesn't do much..."""

    def setup(self, *, some_param, max_n_iter: int) -> None:
        self.some_param = some_param
        self.max_n_iter = max_n_iter

    def should_iterate(self) -> bool:
        """A method that determines whether :py:meth:`.iterate` should be
        called or not."""
        return self.n_iterations < self.max_n_iter

    def iterate(self) -> None:
        """Called repeatedly until the end of the simulation, which can be
        either due to"""
        pass

    def should_write(self) -> bool:
        """A method that determines whether :py:meth:`.write_data` should be
        called after an iteration or not."""
        return False

    def write_data(self) -> None:
        """Performs data writing if :py:meth:`.should_write` returned true."""
        pass


class MyStepwiseModel(StepwiseModel):
    """A model that tests StepwiseModel internals"""

    def setup(self, *, sleep_time: float, mock_signal: int = None):
        self._num_monitor_emits = 0
        self._num_writes = 0
        self._sleep_time = sleep_time
        self._total_sleep_time = 0.0
        self._mock_signal = mock_signal

        self.h5group.create_dataset("some_dset", (self.num_steps + 1,))

    def perform_step(self):
        dt = self._sleep_time + self.rng.uniform(0.01, 0.02)
        time.sleep(dt)
        self._total_sleep_time += dt

        if self._mock_signal is not None:
            self._signal_info = copy.deepcopy(SIGNAL_INFO)
            self._signal_info["got_signal"] = True
            self._signal_info["signum"] = self._mock_signal

    def write_data(self):
        self.h5group["some_dset"][self._num_writes] = self._num_writes
        self._num_writes += 1

    def trigger_monitor(self):
        super().trigger_monitor()
        self._num_monitor_emits += 1

    def monitor(self, monitor_info: dict) -> dict:
        monitor_info["total_sleep_time"] = self._total_sleep_time
        monitor_info["num_writes"] = self._num_writes
        return monitor_info


# -----------------------------------------------------------------------------


def test_BaseModel_init(minimal_pspace_cfg, tmpdir):
    cfg = minimal_pspace_cfg
    cfg["root_model_name"] = "MyModel"
    cfg["MyModel"] = dict(some_param="foo", max_n_iter=13)

    cfg_path = tmpdir.join("cfg.yml")
    write_yml(cfg, path=cfg_path)

    # Cannot instantiate if it's abstract
    with pytest.raises(TypeError, match="abstract class BaseModel"):
        BaseModel(cfg_file_path=cfg_path)

    # But this one works
    model = MyModel(cfg_file_path=cfg_path)

    # ... and has parameters carried over
    assert model.some_param == "foo"

    # Can also iterate
    assert model.n_iterations == 0
    model.run()
    assert model.n_iterations == 13

    # Teardown does not fail even if there is some unexpected error.
    # Here, provoke it by removing the attribute altogether
    model._h5file = None
    del model


# -----------------------------------------------------------------------------


def test_StepwiseModel_basic(minimal_pspace_cfg, tmpdir):
    """Tests instantiation of a base model"""
    # Create the configuration file, filling it with model-specific info
    cfg = minimal_pspace_cfg
    cfg["root_model_name"] = "MyStepwiseModel"
    cfg["MyStepwiseModel"] = dict(sleep_time=0.01)
    cfg["monitor_emit_interval"] = 0.1
    cfg["num_steps"] = 42

    cfg_path = tmpdir.join("cfg.yml")
    write_yml(cfg, path=cfg_path)

    # Instantiate a model instance from that config file
    model = MyStepwiseModel(cfg_file_path=cfg_path)

    assert model.name == "MyStepwiseModel"
    assert model.time == 0
    assert model.write_start == 0
    assert model.write_every == 1
    assert model._num_writes == 1  # from initialization
    assert model._num_monitor_emits == 1  # from initialization

    # Run the model and test its state afterwards
    model.run()

    assert model.time == 42
    assert model._num_writes == 43
    assert model._num_monitor_emits >= 5

    # Hack around the time limit to run again and test interrupt handling
    model.should_write = lambda *a, **k: False
    model._time = 40
    model._mock_signal = signal.SIGINT
    with pytest.raises(SystemExit, match=str(128 + abs(signal.SIGINT))):
        model.run()

    model._time = 30
    model._mock_signal = signal.SIGTERM
    with pytest.raises(SystemExit, match=str(128 + abs(signal.SIGTERM))):
        model.run()

    model._time = 20
    model._mock_signal = SIG_STOPCOND
    with pytest.raises(SystemExit, match=str(128 + abs(SIG_STOPCOND))):
        model.run()

    model._time = 10
    model._mock_signal = 13
    with pytest.raises(SystemExit, match=str(128 + abs(13))):
        model.run()

    # Invoke some methods that are not accessible easily
    model._invoke_epilog(finished_run=False)
    model._invoke_epilog(finished_run=True)

    model.epilog = lambda *a, **k: 1 / 0
    with pytest.raises(ZeroDivisionError):
        model._invoke_epilog(finished_run=True)

    # h5py.File object should be closed after teardown
    h5file = model._h5file
    assert h5file
    del model
    assert not h5file


def test_StepwiseModel_missing_methods(minimal_pspace_cfg, tmpdir):
    """Tests incomplete model definition"""
    # Create the configuration file, filling it with model-specific info
    cfg = minimal_pspace_cfg
    cfg["root_model_name"] = "my_model"
    cfg["my_model"] = dict()
    cfg_path = tmpdir.join("cfg.yml")
    write_yml(cfg, path=cfg_path)

    # Remains abstract and cannot be instantiated directly
    class IncompleteModel(StepwiseModel):
        pass

    with pytest.raises(TypeError, match="perform_step, setup, write_data"):
        IncompleteModel(cfg_file_path=cfg_path)

    # Can instantiate with those three methods implemented
    class NotIncompleteModel(StepwiseModel):
        def setup(self):
            pass

        def perform_step(self):
            pass

        def write_data(self):
            pass

    model = NotIncompleteModel(cfg_file_path=cfg_path)
    model.run()
