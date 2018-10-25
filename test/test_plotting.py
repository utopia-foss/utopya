"""Test the plotting module"""

import pytest

from utopya import Multiverse

# Local constants


# Fixtures --------------------------------------------------------------------


# Tests -----------------------------------------------------------------------

def test_dummy_plotting(tmpdir):
    """Test plotting of the dummy model"""
    # Create and run simulation
    mv = Multiverse(model_name='dummy',
                    update_meta_cfg=dict(paths=dict(out_dir=str(tmpdir))))
    mv.run_single()

    # Load
    mv.dm.load_from_cfg(print_tree=True)

    # Plot the default configuration
    mv.pm.plot_from_cfg()

    # Perform a custom plot that tests the utopya plotting functions
    mv.pm.plot("all_states",
               creator='universe',
               universes='all',
               out_dir=str(tmpdir),
               module=".basic",
               plot_func="lineplot",
               y="dummy/state"
               )

def test_ca_plotting(tmpdir):
    """Tests the plot_funcs submodule using the SimpleEG model"""
    mv = Multiverse(model_name='SimpleEG',
                    update_meta_cfg=dict(paths=dict(out_dir=str(tmpdir))))
    mv.run_single()

    # Load
    mv.dm.load_from_cfg(print_tree=True)

    # Plot the default configuration
    mv.pm.plot_from_cfg()
