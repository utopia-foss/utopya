"""Tests utopya_backend.base_model"""

import os
import time

import pytest

from utopya.testtools import ModelTest
from utopya.tools import load_yml, write_yml
from utopya_backend.model import BaseModel, StepwiseModel

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
    print(cfg)
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


class MinimalTestModel(StepwiseModel):
    """A model that tests StepwiseModel internals"""

    def setup(self, *, sleep_time: float):
        self._num_monitor_emits = 0
        self._num_writes = 0
        self._sleep_time = sleep_time

    def perform_step(self):
        time.sleep(self._sleep_time)

    def write_data(self):
        self._num_writes += 1

    def trigger_monitor(self):
        super().trigger_monitor()
        self._num_monitor_emits += 1


# -----------------------------------------------------------------------------


@pytest.mark.skip(reason="Needs to be implemented")  # TODO
def test_BaseModel():
    pass


# -----------------------------------------------------------------------------


def test_StepwiseModel_basic(minimal_pspace_cfg, tmpdir):
    """Tests instantiation of a base model"""
    # Create the configuration file, filling it with model-specific info
    cfg = minimal_pspace_cfg
    cfg["root_model_name"] = "MinimalTestModel"
    cfg["MinimalTestModel"] = dict(sleep_time=0.01)
    cfg["monitor_emit_interval"] = 0.1
    cfg["num_steps"] = 42

    cfg_path = tmpdir.join("cfg.yml")
    write_yml(cfg, path=cfg_path)

    # Instantiate a model instance from that config file
    model = MinimalTestModel(cfg_file_path=cfg_path)

    assert model.name == "MinimalTestModel"
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
