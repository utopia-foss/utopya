"""Test module for example plot generation"""

import os

from utopya import PlotManager
from utopya.tools import load_yml

from .._fixtures import *

PLOTS_CFG = os.path.join(os.path.dirname(__file__), "test_plots.yml")
"""Path to the plots configuration file"""

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
