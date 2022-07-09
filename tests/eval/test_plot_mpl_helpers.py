"""Test the utopya.eval.plots_mpl module"""
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pytest
from pkg_resources import resource_filename

from utopya.eval.plots._mpl import ColorManager
from utopya.tools import load_yml

from .._fixtures import tmpdir_or_local_dir

COLOR_MANAGER_CFG = resource_filename("tests", "cfg/color_manager_cfg.yml")

# Fixtures --------------------------------------------------------------------


# Tests -----------------------------------------------------------------------


def test_ColorManager(tmpdir_or_local_dir):
    """Tests the ColorManager class."""
    out_dir = tmpdir_or_local_dir

    # The configurations to test
    test_configurations = load_yml(COLOR_MANAGER_CFG)

    # Test initializing the default ColorManager
    colormanager = ColorManager()
    assert colormanager.cmap.name == "viridis"
    assert isinstance(colormanager.norm, mpl.colors.Normalize)
    assert colormanager.labels is None

    for name, cfg in test_configurations.items():
        cbar_kwargs = cfg.pop("cbar_kwargs", {})

        # Test the failing cases explicitly
        if name == "invalid_norm":
            with pytest.raises(
                ValueError, match="Received invalid norm specifier:"
            ):
                ColorManager(**cfg)
            continue

        elif name == "invalid_cmap":
            with pytest.raises(
                ValueError, match="Received invalid colormap name:"
            ):
                ColorManager(**cfg)
            continue

        elif name == "disconnected_intervals":
            with pytest.raises(
                ValueError, match="Received disconnected intervals:"
            ):
                ColorManager(**cfg)
            continue

        elif name == "decreasing_boundaries":
            with pytest.raises(
                ValueError, match="Received decreasing boundaries:"
            ):
                ColorManager(**cfg)
            continue

        elif name == "single_bin_center":
            with pytest.raises(
                ValueError, match="At least 2 bin centers must be given"
            ):
                ColorManager(**cfg)
            continue

        # Initialize the ColorManager and retrieve the created colormap, norm,
        # and colorbar labels.
        colormanager = ColorManager(**cfg)

        cmap = colormanager.cmap
        norm = colormanager.norm
        labels = colormanager.labels

        assert isinstance(cmap, mpl.colors.Colormap)
        assert isinstance(norm, mpl.colors.Normalize)
        assert labels is None or isinstance(labels, dict)

        # Test the `ColorManager.create_cbar` method
        fig, ax = plt.subplots()
        scatter = ax.scatter(
            np.arange(10), np.arange(10), c=np.arange(10), cmap=cmap, norm=norm
        )

        cb = colormanager.create_cbar(scatter, **cbar_kwargs)

        assert isinstance(cb, mpl.colorbar.Colorbar)
        assert cb.norm == norm
        assert cb.cmap == cmap
        if "labels" in cfg and isinstance(cfg["labels"], dict):
            assert (cb.get_ticks() == list(cfg["labels"].keys())).all()

        # Save and close the plot
        plt.savefig(os.path.join(out_dir, f"{name}.pdf"))
        plt.close()

        # Test the `ColorManager.map_to_color` method
        colors = colormanager.map_to_color(42.0)
        assert mpl.colors.is_color_like(colors)
        colors = colormanager.map_to_color(np.linspace(2.1, 5.3, 10))
        assert all([mpl.colors.is_color_like(c) for c in colors])

        # NOTE Some explicit color checks. If it fails check the respective
        #      configurations.
        if name == "from_intervals":
            assert cmap(1) == mpl.colors.to_rgba("w")

        if name == "shortcut_categorical":
            assert cmap(0) == mpl.colors.to_rgba("g")

    # Test ColorManager when passing norm and cmap (as mpl object) directly
    colormanager = ColorManager(
        cmap=mpl.colors.ListedColormap(["r", "b"]),
        norm=mpl.colors.BoundaryNorm([-2, 1, 2], ncolors=2),
    )
    assert colormanager.cmap(0) == mpl.colors.to_rgba("r")
