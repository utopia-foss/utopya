"""Test module for example plot generation"""

import contextlib
import os

import pytest

from utopya.eval import PlotHelper, PlotManager
from utopya.testtools import ModelTest
from utopya.tools import load_yml

from .. import *
from .._fixtures import *
from ..eval.test_plotting import (
    ABM_PLOTS_CFG,
    HEXGRID_PLOTS_CFG,
    ObjectContainer,
    XarrayDC,
    abm_data,
    hexgrid_data,
)

PLOTS_CFG = os.path.join(os.path.dirname(__file__), "test_plots.yml")
"""Path to the plots configuration file"""

# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def register_demo_project(tmp_projects, with_test_models):
    """Use on all tests in this module"""
    pass


# -----------------------------------------------------------------------------


def test_plots(dm, out_dir):
    """Creates output from the (DAG-based) plotting tests and examples"""

    model = ModelTest(ADVANCED_MODEL)
    mv, dm = model.create_run_load(parameter_space=dict(num_steps=42))
    mv.pm.raise_exc = True
    print(dm.tree)

    # Load some configuration arguments
    shared_kwargs = dict(out_dir=str(out_dir))
    plot_cfgs = load_yml(PLOTS_CFG)

    # Can do a simple DAG-based universe and multiverse plot
    for cfg_name, plot_cfg in plot_cfgs.items():
        if cfg_name.startswith("."):
            continue

        _raises = plot_cfg.pop("_raises", None)
        _match = plot_cfg.pop("_match", None)

        if _raises is not None:
            ctx = pytest.raises(globals()[_raises], match=_match)
        else:
            ctx = contextlib.nullcontext()

        # The actual plotting
        print(f"\n\n--- Test case '{cfg_name}' ---")
        with ctx:
            mv.pm.plot(cfg_name, **shared_kwargs, **plot_cfg)


def test_imshow_hex(hexgrid_data, out_dir):
    """Creates output that illustrates imshow_hexagonal"""

    from utopya.eval.plots.ca import imshow_hexagonal as imshow_hex

    def new_helper(name: str, *, ext: str = "pdf", **kws):
        out_path = os.path.join(out_dir, f"{name}.{ext}")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        ph = PlotHelper(out_path=out_path, **kws)
        ph.setup_figure()
        return ph

    def draw_imshow_hex(name: str, data, **kwargs):
        hlpr = new_helper(name)
        imshow_hex(data, ax=hlpr.ax, **kwargs)
        hlpr.save_figure()

    # .........................................................................
    data_small = hexgrid_data["small"].sel(time=0, drop=True)
    space_kwargs = dict(space_size=(8, 8), space_offset=(-4, -4))

    draw_imshow_hex(
        "small",
        data_small,
    )

    draw_imshow_hex(
        "small_centers_marked",
        data_small,
        draw_centers=True,
    )

    draw_imshow_hex(
        "small_with_space_outer",
        data_small,
        update_grid_properties=dict(**space_kwargs),
    )

    draw_imshow_hex(
        "small_with_space_inner",
        data_small,
        update_grid_properties=dict(
            **space_kwargs,
            space_boundary="inner",
        ),
    )

    draw_imshow_hex(
        "small_flat_top_odd",
        data_small,
        update_grid_properties=dict(pointy_top=False, offset_mode="odd"),
    )

    draw_imshow_hex(
        "small_flat_top_odd_with_space",
        data_small,
        update_grid_properties=dict(
            pointy_top=False, offset_mode="odd", **space_kwargs
        ),
    )


def test_caplot(hexgrid_data, out_dir):
    """Creates output that illustrates imshow_hexagonal"""
    # Add the hexgrid data to the data tree
    mv, _ = ModelTest(ADVANCED_MODEL).create_run_load()

    for _, uni in mv.dm["multiverse"].items():
        hexdata = uni[("data", ADVANCED_MODEL)].new_group("hexgrid")
        for name, data in hexgrid_data.items():
            hexdata.new_container(name, data=data, Cls=XarrayDC)

    # Configure PlotManager
    mv.pm.raise_exc = True
    mv.pm._out_dir = out_dir

    # Plot only the documentation-related plots
    for name, plot_cfg in load_yml(HEXGRID_PLOTS_CFG).items():
        if not name.startswith("doc_"):
            continue

        try:
            mv.pm.plot(name[4:], **plot_cfg)

        except Exception as exc:
            # Allow to fail if it's due to ffmpeg missing
            if "ffmpeg" in str(exc) and HAVE_FFMPEG:
                raise
            continue


def test_abmplot(abm_data, out_dir):
    """Creates output that illustrates abmplot"""
    # Add the data to the data tree
    mv, _ = ModelTest(ADVANCED_MODEL).create_run_load()

    for _, uni in mv.dm["multiverse"].items():
        grp = uni[("data", ADVANCED_MODEL)].new_group("abm")
        for name, data in abm_data.items():
            grp.new_container(name, data=data, Cls=ObjectContainer)

    mv.pm.raise_exc = True
    mv.pm._out_dir = out_dir

    # Plot only the documentation-related plots
    for name, plot_cfg in load_yml(ABM_PLOTS_CFG).items():
        if not name.startswith("doc_"):
            continue

        try:
            mv.pm.plot(name[4:], **plot_cfg)

        except Exception as exc:
            # Allow to fail if it's due to ffmpeg missing
            if "ffmpeg" in str(exc) and HAVE_FFMPEG:
                raise
            continue
