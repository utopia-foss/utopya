"""Tests the DataManager and involved functions and classes."""

import logging
import os
import uuid

import numpy as np
import pytest
from paramspace import ParamSpace
from pkg_resources import resource_filename

import utopya.eval.containers as udc
import utopya.eval.groups as udg
from utopya import DataManager, Multiverse
from utopya.eval.datamanager import _condense_thresh_func

from .. import ADVANCED_MODEL, DUMMY_MODEL, get_cfg_fpath

RUN_CFG_PATH = get_cfg_fpath("run_cfg.yml")
LARGE_SWEEP_CFG_PATH = get_cfg_fpath("large_sweep_cfg.yml")

# Suppress overly verbose log messages
logging.getLogger("utopya.task").setLevel(logging.DEBUG)
logging.getLogger("utopya.reporter").setLevel(logging.INFO)


# Fixtures --------------------------------------------------------------------
from .._fixtures import *


@pytest.fixture(autouse=True)
def register_demo_project(tmp_projects):
    """Use on all tests in this module"""
    pass


@pytest.fixture
def mv_kwargs(tmpdir) -> dict:
    """Returns a dict that can be passed to Multiverse for initialisation.

    This uses the `tmpdir` fixture provided by pytest, which creates a unique
    temporary directory that is removed after the tests ran through.
    """
    # Create a random string to use as model note
    rand_str = "test_" + uuid.uuid4().hex

    # Create a dict that specifies a unique testing path.
    return dict(
        model_name=ADVANCED_MODEL,
        run_cfg_path=RUN_CFG_PATH,
        user_cfg_path=False,  # to omit the user config
        paths=dict(out_dir=str(tmpdir), model_note=rand_str),
    )


@pytest.fixture
def dm_dummy_model(mv_kwargs, with_test_models) -> DataManager:
    """Initialises a Multiverse with a DataManager, runs a simulation with
    output going into a temporary directory, then returns the DataManager."""
    mv_kwargs["model_name"] = DUMMY_MODEL
    mv_kwargs["run_cfg_path"] = RUN_CFG_PATH
    mv = Multiverse(**mv_kwargs)
    mv.run_single()
    return mv.dm


@pytest.fixture
def dm_after_single(mv_kwargs, with_test_models) -> DataManager:
    """Initialises a Multiverse with a DataManager, runs a simulation with
    output going into a temporary directory, then returns the DataManager."""
    mv_kwargs["run_cfg_path"] = RUN_CFG_PATH
    mv = Multiverse(**mv_kwargs)
    mv.run_single()
    return mv.dm


@pytest.fixture
def dm_after_large_sweep(mv_kwargs, with_test_models) -> DataManager:
    """Initialises a Multiverse with a DataManager, runs a simulation with
    output going into a temporary directory, then returns the DataManager."""
    mv_kwargs["run_cfg_path"] = LARGE_SWEEP_CFG_PATH
    mv = Multiverse(**mv_kwargs)
    mv.run_sweep()
    return mv.dm


# Tests -----------------------------------------------------------------------


def test_condense_thresh_func():
    """Tests the function that evaluates the condense threshold for the
    data tree.
    """
    for l, n, t in zip([1, 4, 5], [42, 42, 42], [42, 42, 142]):
        _condense_thresh_func(level=l, num_items=n, total_item_count=t)


def test_init(tmpdir):
    """Tests simple initialisation of the data manager"""
    DataManager(str(tmpdir))


def test_simple_load(dm_dummy_model):
    """Tests the loading of simulation data for a single simulation"""
    dm = dm_dummy_model

    # Load and print a tree of the loaded data
    dm.load_from_cfg(print_tree=True)

    # Check that the config is loaded as expected
    assert "cfg" in dm
    assert "cfg/base" in dm
    assert "cfg/meta" in dm
    assert "cfg/model" in dm
    assert "cfg/run" in dm

    # Check that 'multiverse' is a MultiverseGroup
    assert "multiverse" in dm
    assert isinstance(dm["multiverse"], udg.MultiverseGroup)
    assert isinstance(dm["multiverse"].pspace, ParamSpace)

    assert len(dm["multiverse"]) == 1
    assert 0 in dm["multiverse"]
    uni = dm["multiverse"][0]

    # Check that the uni config is loaded
    assert "cfg" in uni

    # Binary data should NOT have been loaded by default because there is no
    # load configuration available for this model
    assert "data" not in uni


def test_load_single(dm_after_single):
    """Tests the loading of simulation data for a single simulation"""
    dm = dm_after_single

    # Load and print a tree of the loaded data
    dm.load_from_cfg(print_tree=True)

    # Check that the config is loaded as expected
    assert "cfg" in dm
    assert "cfg/base" in dm
    assert "cfg/meta" in dm
    assert "cfg/model" in dm
    assert "cfg/run" in dm

    # Check that 'multiverse' is a MultiverseGroup
    assert "multiverse" in dm
    assert isinstance(dm["multiverse"], udg.MultiverseGroup)
    assert isinstance(dm["multiverse"].pspace, ParamSpace)

    assert len(dm["multiverse"]) == 1
    assert 0 in dm["multiverse"]
    uni = dm["multiverse"][0]

    # Check that the uni config is loaded
    assert "cfg" in uni

    # Check that the binary data is loaded as expected
    assert "data" in uni
    assert f"data/{ADVANCED_MODEL}" in uni

    # Get the state dataset and check its content
    dset = uni[f"data/{ADVANCED_MODEL}/state"]
    print(dset.data)

    assert isinstance(dset, (udc.NumpyDC, udc.XarrayDC))
    assert dset.shape[1] == 100
    assert str(dset.dtype).startswith("f")


def test_load_sweep(dm_after_large_sweep):
    """Tests the loading of simulation data for a sweep"""
    dm = dm_after_large_sweep

    # Load and print a tree of the loaded data
    dm.load_from_cfg(print_tree="condensed")

    # Check that the config is loaded as expected
    assert "cfg" in dm
    assert "cfg/base" in dm
    assert "cfg/meta" in dm
    assert "cfg/model" in dm
    assert "cfg/run" in dm

    # Check that 'multiverse' is a MultiverseGroup of right length
    assert "multiverse" in dm
    assert isinstance(dm["multiverse"], udg.MultiverseGroup)
    assert isinstance(dm["multiverse"].pspace, ParamSpace)
    assert 0 not in dm["multiverse"]
    assert len(dm["multiverse"]) == dm["multiverse"].pspace.volume

    # Now go over all available universes
    for uni_no, uni in dm["multiverse"].items():
        # Check that the uni config is loaded
        assert "cfg" in uni

        # Check that the binary data is loaded as expected
        assert "data" in uni
        assert f"data/{ADVANCED_MODEL}" in uni
        assert f"data/{ADVANCED_MODEL}/state" in uni

        # Get the state dataset and check its content
        dset = uni[f"data/{ADVANCED_MODEL}/state"]

        assert isinstance(dset, (udc.NumpyDC, udc.XarrayDC))
        assert dset.shape == (uni["cfg"]["num_steps"] + 1, 100)
        assert str(dset.dtype).startswith("f")
