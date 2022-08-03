"""Tests utopya_backend.base_model"""

import os
import time

import pytest

from utopya.testtools import ModelTest
from utopya.tools import load_yml, write_yml
from utopya_backend.base_model import BaseModel

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


# -----------------------------------------------------------------------------


class MinimalTestModel(BaseModel):
    """A test model that tests BaseModel internals"""

    def setup(self, *, sleep_time: float):
        self._num_monitor_emits = 0
        self._num_writes = 0
        self._sleep_time = sleep_time

    def perform_step(self):
        time.sleep(self._sleep_time)

    def write_data(self):
        self._num_writes += 1

    def monitor(self):
        super().monitor()
        self._num_monitor_emits += 1


# -----------------------------------------------------------------------------


def test_BaseModel_basic(minimal_pspace_cfg, tmpdir):
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


def test_BaseModel_missing_methods(minimal_pspace_cfg, tmpdir):
    """Tests incomplete model definition"""

    class IncompleteModel(BaseModel):
        pass

    # Create the configuration file, filling it with model-specific info
    cfg = minimal_pspace_cfg
    cfg["root_model_name"] = "IncompleteModel"
    cfg["IncompleteModel"] = dict()
    cfg_path = tmpdir.join("cfg.yml")
    write_yml(cfg, path=cfg_path)

    # Cannot even instantiate without setup method
    with pytest.raises(NotImplementedError, match="setup"):
        IncompleteModel(cfg_file_path=cfg_path)

    # Cannot setup without write_data, because will want to write initial state
    IncompleteModel.setup = lambda self: print("setup")
    os.remove(cfg["output_path"])

    with pytest.raises(NotImplementedError, match="write_data"):
        IncompleteModel(cfg_file_path=cfg_path)

    # Or without perform_step
    IncompleteModel.write_data = lambda self: print("write_data")
    os.remove(cfg["output_path"])
    model = IncompleteModel(cfg_file_path=cfg_path)
    with pytest.raises(NotImplementedError, match="perform_step"):
        model.run()

    # But with all three methods implemented, it works
    IncompleteModel.perform_step = lambda self: print("perform_step")
    os.remove(cfg["output_path"])
    model = IncompleteModel(cfg_file_path=cfg_path)
    model.run()
