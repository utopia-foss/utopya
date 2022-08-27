"""Test module for example plot generation"""

import os

from utopya.eval import PlotHelper, PlotManager
from utopya.testtools import ModelTest
from utopya.tools import load_yml

from .. import *
from .._fixtures import *
from ..eval.test_plotting import HEXGRID_PLOTS_CFG, XarrayDC, hexgrid_data

PLOTS_CFG = os.path.join(os.path.dirname(__file__), "test_plots.yml")
"""Path to the plots configuration file"""

# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def register_demo_project(tmp_projects, with_test_models):
    """Use on all tests in this module"""
    pass


# -----------------------------------------------------------------------------


def test_plots(dm, tmpdir_or_local_dir):
    """Creates output from the (DAG-based) plotting tests and examples"""

    pm = PlotManager(
        dm=dm,
        out_dir=tmpdir_or_local_dir,
        raise_exc=True,
        shared_creator_init_kwargs=dict(exist_ok=True),
        cfg_exists_action="overwrite",
    )
    plots_cfg = load_yml(PLOTS_CFG)

    # Here we go ...
    for name, cfg in plots_cfg.items():
        print(f"\n\n... Plot: '{name}' ...")
        raises = cfg.pop("_raises", False)

        try:
            pm.plot(name=name, **cfg)

        except Exception as exc:
            if not raises:
                raise
            print(f"Raised an exception, as expected.")


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
