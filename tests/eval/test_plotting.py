"""Test the plotting module"""

import builtins
import copy
import logging
import os
import sys

import dantro
import matplotlib as mpl
import matplotlib.pyplot as plt
import networkx as nx
import paramspace as psp
import pytest
from dantro._import_tools import remove_from_sys_modules
from dantro.data_ops import available_operations
from dantro.plot_mngr import PlotCreatorError

from utopya import Multiverse
from utopya._import_tools import added_sys_path
from utopya._import_tools import temporary_sys_modules as tmp_sys_modules
from utopya.eval.plots._graph import GraphPlot
from utopya.testtools import ModelTest
from utopya.yaml import load_yml

from .. import ADVANCED_MODEL, DUMMY_MODEL, get_cfg_fpath

# Get the test resources ......................................................
# Mute the matplotlib logger
logging.getLogger("matplotlib").setLevel(logging.WARNING)

# Basic universe plots
BASIC_UNI_PLOTS = get_cfg_fpath("plots/basic_uni.yml")

# DAG-based plots
DAG_PLOTS = get_cfg_fpath("plots/dag.yml")

# Bifurcation diagram plots, 1D and 2D
BIFURCATION_DIAGRAM_RUN = get_cfg_fpath("plots/bifurcation_diagram/run.yml")
BIFURCATION_DIAGRAM_PLOTS = get_cfg_fpath(
    "plots/bifurcation_diagram/plots.yml"
)
BIFURCATION_DIAGRAM_2D_RUN = get_cfg_fpath(
    "plots/bifurcation_diagram_2d/run.yml"
)
BIFURCATION_DIAGRAM_2D_PLOTS = get_cfg_fpath(
    "plots/bifurcation_diagram_2d/plots.yml"
)

# Graph plots
GRAPH_RUN = get_cfg_fpath("graphgroup_cfg.yml")
GRAPH_PLOTS = get_cfg_fpath("plots/graph_plot_cfg.yml")
GRAPH_PLOT_CLS = get_cfg_fpath("graphplot_class_cfg.yml")


# -----------------------------------------------------------------------------


# Fixtures --------------------------------------------------------------------
from .._fixtures import *


@pytest.fixture(autouse=True)
def register_demo_project(tmp_projects, with_test_models):
    """Use on all tests in this module"""
    pass


@pytest.fixture
def without_cached_model_plots_modules():
    remove_from_sys_modules(lambda m: m.startswith("model_plots"))

    assert "model_plots" not in sys.modules
    assert not any([ms.startswith("model_plots") for ms in sys.modules])


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------


def test_dag_custom_operations(without_cached_model_plots_modules):
    """Tests if custom dantro data operations can be registered via the
    extensions made to PlotManager.
    """
    op_name = "my_custom_data_operation"

    # Make sure the operation is not yet registered
    OPERATIONS = dantro.data_ops._OPERATIONS
    if op_name in OPERATIONS:
        del OPERATIONS["my_custom_data_operation"]

    assert "my_custom_data_operation" not in available_operations()

    # Now, set up the model and its PlotManager
    model = ModelTest(ADVANCED_MODEL)
    mv, dm = model.create_run_load()
    mv.pm.raise_exc = True
    plot_cfgs = load_yml(DAG_PLOTS)

    # Should still not be available
    assert "my_custom_data_operation" not in available_operations()

    # Now, do some unrelated plot operation, i.e. not requiring model-specific
    # plot functions, but only utopya plot functions.
    # This should still lead to the _invoke_creator method being called, which
    # takes care of pre-loading model-specific module definitions, which in
    # turn call register_operation during their import
    with tmp_sys_modules():
        mv.pm.plot("test", out_dir=mv.dirs["eval"], **plot_cfgs["uni_ts"])

        assert "my_custom_data_operation" in available_operations()


def test_preloading(tmpdir, without_cached_model_plots_modules):
    """Tests the preloading feature of the utopya.PlotManager"""
    model_plot_modstr = f"model_plots.{ADVANCED_MODEL}"
    model_plot_name = "custom_plot"

    # Now create the model test object, which should load it
    model = ModelTest(ADVANCED_MODEL)
    mv, dm = model.create_run_load()
    mv.pm.raise_exc = True
    assert model_plot_modstr not in sys.modules

    mv.pm.plot_from_cfg(plot_only=(model_plot_name,))
    assert model_plot_modstr in sys.modules

    # How about a case with a bad import location; adjust a copy of the info
    # bundle to be corrupt in such a way ... Also, temporarily clear the
    # sys.path, as it _might_ include a path that allows import.
    mv.renew_plot_manager(out_dir=f"session_2/", raise_exc=False)

    del sys.modules[model_plot_modstr]
    del sys.modules["model_plots"]
    assert "model_plots" not in sys.modules
    assert model_plot_modstr not in sys.modules

    # Corrupt the bundle
    mib = mv.pm._model_info_bundle
    mpd = os.path.dirname(os.path.dirname(mib.paths["py_plots_dir"]))

    # Prepare the temporary sys.path corruption, using a valid and existing
    # path but without any content
    bad_sys_path = str(tmpdir)
    mib.paths["py_plots_dir"] = bad_sys_path

    # Need to disassociate the project to not have the PlotManager load the
    # project-defined plot directory
    mib._project_name = None

    # Assign it back
    mv.pm._model_info_bundle = mib

    # Without exception raising, this should just go ahead, even though the
    # import will fail ...
    assert not mv.pm.raise_exc
    with added_sys_path(bad_sys_path), tmp_sys_modules():
        # Remove the model plots directories from the path
        sys.path = [p for p in sys.path if not p.startswith(mpd)]

        mv.pm.plot_from_cfg(plot_only=(model_plot_name,))

        # The module will still be loaded though, because the associated
        # project will load it.
        assert model_plot_modstr in sys.modules

    # With exception raising, there should be an appropriate error message
    mv.renew_plot_manager(out_dir=f"session_3/", raise_exc=True)
    mv.pm._model_info_bundle = mib

    with added_sys_path(bad_sys_path), tmp_sys_modules():
        assert mv.pm._model_info_bundle.paths["py_plots_dir"] == bad_sys_path
        assert "model_plots" not in sys.modules
        assert model_plot_modstr not in sys.modules
        assert mv.pm.raise_exc

        remove_from_sys_modules(lambda m: m.startswith("model_plots"))
        assert not any([ms.startswith("model_plots") for ms in sys.modules])

        # This will pass, because import happens via the project's py_plots_dir
        mv.pm.plot_from_cfg(plot_only=(model_plot_name,))

        # But without the project (and also: without framework) it will fail
        mv.pm._model_info_bundle._d["project_name"] = None
        assert not mv.pm._model_info_bundle.project
        remove_from_sys_modules(lambda m: m.startswith("model_plots"))

        with pytest.raises(ImportError, match="Could not import module"):
            mv.pm.plot_from_cfg(plot_only=(model_plot_name,))


def test_plot_func_resolver_extensions():
    """Test the changes and extensions to the plot function resolver.

    ... indirectly, using some other plot creator.
    """
    model = ModelTest(ADVANCED_MODEL)
    mv, dm = model.create_run_load()
    mv.pm.raise_exc = True
    print(dm.tree)

    # Can do the default plots
    mv.pm.plot_from_cfg()

    # Can specify custom plots within utopya ... but will receive an error
    # because the data dimensionality does not match
    with pytest.raises(PlotCreatorError, match="Apply dimensionality red"):
        mv.pm.plot(
            "test",
            out_dir=mv.dirs["eval"],
            creator="universe",
            universes="all",
            module=".basic_uni",
            plot_func="lineplot",
            model_name=ADVANCED_MODEL,
            path_to_data="state",
        )

    # Cannot do a custom plot with a bad relative module import
    with pytest.raises(ModuleNotFoundError, match="Could not import"):
        mv.pm.plot(
            "test2",
            out_dir=mv.dirs["eval"],
            creator="universe",
            universes="all",
            module=".some_invalid_module",
            plot_func="lineplot",
        )

    # How about absolute imports? Nope.
    with pytest.raises(ModuleNotFoundError, match="No module named 'some'"):
        mv.pm.plot(
            "test3",
            out_dir=mv.dirs["eval"],
            creator="universe",
            universes="all",
            module="some.abs.invalid.module",
            plot_func="lineplot",
        )

    # ... and when an import fails for a custom model plot module?
    with pytest.raises(
        ModuleNotFoundError,
        match="_unrelated_ ModuleNotFoundError occurred somew",
    ):
        mv.pm.plot(
            "test4",
            out_dir=mv.dirs["eval"],
            creator="universe",
            universes="all",
            module="model_plots.some_invalid_model_name",
            plot_func="lineplot",
        )


# -----------------------------------------------------------------------------
# -- Demo model default plots -------------------------------------------------
# -----------------------------------------------------------------------------


def test_dummy_model_plotting():
    """Test plotting of the dummy model works"""
    mv, _ = ModelTest(DUMMY_MODEL).create_run_load()
    mv.pm.plot_from_cfg()


def test_advanced_model_plotting():
    """Test plotting of the dummy model works"""
    mv, _ = ModelTest(ADVANCED_MODEL).create_run_load()
    mv.pm.plot_from_cfg()


# -----------------------------------------------------------------------------
# -- CA Plots -----------------------------------------------------------------
# -----------------------------------------------------------------------------


def test_caplot():
    """Tests the plot_funcs.ca module"""
    mv, _ = ModelTest(ADVANCED_MODEL).create_run_load()

    # Run the CA plots (initial frame + animation)
    mv.pm.plot_from_cfg(plot_only=["ca/animated"])
    mv.pm.plot_from_cfg(plot_only=["ca/snapshot"])


@pytest.mark.skip("No hexagonal grid model available")
def test_caplot_hexagonal():
    """Tests the plot_funcs.ca module with hexagonal lattice"""
    update_meta_cfg = {
        "parameter_space": {
            "CopyMeGrid": {
                "cell_manager": {
                    "grid": {"structure": "hexagonal"},
                    "neighborhood": {"mode": "hexagonal"},
                }
            }
        }
    }
    mv, _ = ModelTest("CopyMeGrid").create_run_load(**update_meta_cfg)

    # Run the CA plots (initial frame + animation)
    mv.pm.plot_from_cfg(plot_only=["initial_state_and_trait"])
    mv.pm.plot_from_cfg(plot_only=["state_and_trait_anim"])

    # Same again with SimpleEG . . . . . . . . . . . . . . . . . . . . . . . .
    mv, _ = ModelTest("SimpleEG").create_run_load(**update_meta_cfg)

    # Plot the default configuration, which already includes some CA plotting
    mv.pm.plot_from_cfg()

    # To explicitly plot with the frames writer, select the disabled config
    mv.pm.plot_from_cfg(plot_only=["strategy_and_payoff_frames"])


# -----------------------------------------------------------------------------
# -- DAG Plots ----------------------------------------------------------------
# -----------------------------------------------------------------------------
# TODO Decide which ones need to be tested here at all


def test_dag_plotting():
    """Makes sure that DAG plotting works as expected"""
    # Now, set up the model
    model = ModelTest(ADVANCED_MODEL)
    mv, dm = model.create_run_load()
    mv.pm.raise_exc = True
    print(dm.tree)

    # Load some configuration arguments
    shared_kwargs = dict(out_dir=mv.dirs["eval"])
    plot_cfgs = load_yml(DAG_PLOTS)

    # Can do a simple DAG-based universe and multiverse plot
    for cfg_name, plot_cfg in plot_cfgs.items():
        if cfg_name.startswith("."):
            continue

        # The actual plotting
        print(f"Plotting '{cfg_name}' ...")
        mv.pm.plot(cfg_name, **shared_kwargs, **plot_cfg)
        print(f"Successfully plotted '{cfg_name}'!\n\n")


@pytest.mark.skip("No model with DAG based plots available")  # TODO
def test_generic_dag_plots(tmpdir):
    """Tests the plot_funcs.dag.generic module"""
    mv, _ = ModelTest("SEIRD").create_run_load()
    mv.pm.plot_from_cfg(
        plot_only=[
            "age_distribution/final",
            "age_distribution/time_series",
            "age_distribution/deceased",
        ]
    )


@pytest.mark.skip("Plot function no longer included")  # TODO
def test_time_series_plots():
    """Tests the plot_funcs.time_series module"""
    mv, _ = ModelTest("SandPile").create_run_load()

    # Plot specific plots from the default plot configuration, which are using
    # the time_series plots
    mv.pm.plot_from_cfg(plot_only=["area_fraction"])

    # Again, with PredatorPrey
    mv, _ = ModelTest("PredatorPrey").create_run_load()

    # Plot specific plots from the default plot configuration, which are using
    # the time_series plots
    mv.pm.plot_from_cfg(plot_only=["species_densities", "phase_space"])


@pytest.mark.skip("Plot function no longer included")  # TODO
def test_distribution_plots():
    """Tests the plot_funcs.distribution module"""
    mv, _ = ModelTest("SandPile").create_run_load()

    # Plot specific plots from the default plot configuration, which are using
    # the distribution plots
    mv.pm.plot_from_cfg(
        plot_only=["compl_cum_prob_dist", "cluster_size_distribution"]
    )


# -----------------------------------------------------------------------------
# -- Graph plots --------------------------------------------------------------
# -----------------------------------------------------------------------------


def test_GraphPlot_class():
    """Tests the plot_funcs._graph module.

    Mainly tests basic functionality, class attribute management and
    configuration parsing. Plotting of more complex graph data (using features
    like property-mapping) is tested in test_plotting.test_graph_plots.
    """
    graph = nx.complete_graph(3, create_using=nx.Graph)
    digraph = nx.complete_graph(3, create_using=nx.DiGraph)

    # Initialize GraphPlot with defaults
    gp = GraphPlot(graph)

    # Check that all nodes and edges are selected for drawing
    assert gp._nodes_to_draw == [0, 1, 2]
    assert len(gp._edges_to_draw) == 3
    assert gp._nodes_to_shrink == []

    # Check properties
    assert isinstance(gp.g, nx.Graph)
    assert gp.g is not gp._g

    # Draw nodes, edges, and default labels
    gp.draw(node_labels=dict(enabled=True), edge_labels=dict(enabled=True))
    # Draw again, re-creating the colormanagers
    gp.draw(nodes=dict(vmin=0.0), edges=dict(edge_vmin=0.0))

    assert isinstance(gp._mpl_nodes, mpl.collections.PathCollection)
    assert isinstance(gp._mpl_edges, mpl.collections.LineCollection)
    assert isinstance(gp._mpl_node_labels, dict)
    assert isinstance(gp._mpl_edge_labels, dict)
    assert gp._mpl_node_cbar is None
    assert gp._mpl_edge_cbar is None

    # Check that the label drawing kwargs are not set permanently
    assert gp._node_label_kwargs == {}
    assert gp._edge_label_kwargs == {}

    # Add colorbars
    gp.add_colorbars()
    # Doing this twice should be ok and should remove the first colorbars
    gp.add_colorbars()

    assert isinstance(gp._mpl_node_cbar, mpl.colorbar.Colorbar)
    assert isinstance(gp._mpl_edge_cbar, mpl.colorbar.Colorbar)

    # Clear plot
    gp.clear_plot()
    # Doing this twice should be ok
    gp.clear_plot()

    # Done with testing the drawing on this figure.
    plt.close(gp.fig)

    # Test the subgraph selection
    # Select two nodes to draw, remove 1 node and 2 edges from the graph
    gp = GraphPlot(graph, select=dict(nodelist=[0, 1]))
    assert gp._g.number_of_nodes() == 2
    assert gp._g.number_of_edges() == 1
    assert gp._nodes_to_draw == [0, 1]
    assert len(gp._edges_to_draw) == 1
    assert gp._nodes_to_shrink == []

    # Select two nodes to draw, but don't remove anything from the graph
    gp = GraphPlot(graph, select=dict(nodelist=[0, 1], drop=False))
    assert gp._g.number_of_nodes() == 3
    assert gp._g.number_of_edges() == 3
    assert gp._nodes_to_draw == [0, 1]
    assert len(gp._edges_to_draw) == 1
    assert gp._nodes_to_shrink == []

    # With open_edges, the non-selected node is still drawn but shrinked
    gp = GraphPlot(graph, select=dict(nodelist=[0, 1], open_edges=True))
    assert gp._g.number_of_nodes() == 3
    assert gp._g.number_of_edges() == 3
    assert gp._nodes_to_draw == [0, 1, 2]
    assert len(gp._edges_to_draw) == 3
    assert gp._nodes_to_shrink == [2]

    # Now go through configurations and test initialization and drawing
    configs = load_yml(GRAPH_PLOT_CLS)

    for name, cfg in configs.items():
        fig = plt.figure()

        # Try using a graphviz node layout, which requires pydot
        if name == "graphviz":
            try:
                import pydot
            except ImportError:
                with pytest.raises(
                    ImportError, match="No module named 'pydot'"
                ):
                    gp = GraphPlot(digraph, fig=fig, **cfg)

                continue

        # Configurations for which an Error is raised
        if "_raises" in cfg:
            exc_type = getattr(builtins, cfg.pop("_raises"))
            match = cfg.pop("_match")

            with pytest.raises(exc_type, match=match):
                gp = GraphPlot(digraph, fig=fig, **cfg)
                gp.draw()
                gp.clear_plot()

        # Configurations that lead to a warning
        elif "_warns" in cfg:
            warn_type = getattr(builtins, cfg.pop("_warns"))
            match = cfg.pop("_match")

            with pytest.warns(warn_type, match=match):
                gp = GraphPlot(digraph, fig=fig, **cfg)
                gp.draw()
                gp.clear_plot()

        # These should work fine
        else:
            gp = GraphPlot(digraph, fig=fig, **cfg)
            gp.draw()
            gp.clear_plot()

        plt.close(fig)


@pytest.mark.skip("No graph model available")  # TODO
def test_graph_plots(tmpdir):
    """Tests the plot_funcs.dag.graph module"""
    # Create and run simulation
    raise_exc = {"plot_manager": {"raise_exc": True}}
    mv = Multiverse(
        model_name="CopyMeGraph",
        run_cfg_path=GRAPH_RUN,
        paths=dict(out_dir=str(tmpdir)),
        **raise_exc,
    )

    mv.run_single()

    # Load
    mv.dm.load_from_cfg(print_tree=False)

    # Single graph plots
    mv.pm.plot_from_cfg(
        plots_cfg=GRAPH_PLOTS,
        plot_only=(
            "Graph",
            "DiGraph",
            "MultiGraph",
            "MultiDiGraph",
            "ExternalProperties",
            "Example_graph_plot",
            "custom_node_positioning_model",
            "explicit_node_positions",
            "custom_graph_creation",
            "custom_graph_arr_creation",
        ),
    )

    # Animation plots
    mv.pm.plot_from_cfg(
        plots_cfg=GRAPH_PLOTS,
        plot_only=[
            "graph_anim1",
            "graph_anim2",
            "graph_anim3",
            "graph_anim_external",
            "graph_anim4",
            "graph_anim_custom_graph_creation",
        ],
    )

    # Test failing cases – if possible these test are done in the (faster)
    # GraphPlot-class test.
    # Providing invalid dag tag for external property
    with pytest.raises(
        PlotCreatorError,
        match=(
            "No tag 'some_state_transformed' found in the data selected by "
            "the DAG!"
        ),
    ):
        mv.pm.plot_from_cfg(
            plots_cfg=GRAPH_PLOTS, plot_only=["invalid_ext_prop"]
        )

    # Ambiguous time specifications for animation
    with pytest.raises(
        PlotCreatorError, match="ambiguous animation time specifications"
    ):
        mv.pm.plot_from_cfg(
            plots_cfg=GRAPH_PLOTS, plot_only=["anim_amgiguous_time_spec"]
        )

    # Trying to animate from single nx.Graph
    with pytest.raises(
        PlotCreatorError, match="due to invalid type of the 'graph'"
    ):
        mv.pm.plot_from_cfg(
            plots_cfg=GRAPH_PLOTS, plot_only=["anim_not_dataarray"]
        )


# -----------------------------------------------------------------------------
# -- Bifurcation diagram plots ------------------------------------------------
# -----------------------------------------------------------------------------
# TODO Need alternative way of testing this


@pytest.mark.skip("Need alternative way of testing this")
def test_bifurcation_diagram(tmpdir):
    """Test plotting of the bifurcation diagram"""
    # Create and run simulation
    raise_exc = {"plot_manager": {"raise_exc": True}}
    mv = Multiverse(
        model_name="SavannaHomogeneous",
        run_cfg_path=BIFURCATION_DIAGRAM_RUN,
        paths=dict(out_dir=str(tmpdir)),
        **raise_exc,
    )
    mv.run_sweep()

    # Load
    mv.dm.load_from_cfg(print_tree=False)

    # Plot the bifurcation using the last datapoint
    mv.pm.plot_from_cfg(
        plots_cfg=BIFURCATION_DIAGRAM_PLOTS, plot_only=["bifurcation_endpoint"]
    )
    # Plot the bifurcation using the fixpoint
    mv.pm.plot_from_cfg(
        plots_cfg=BIFURCATION_DIAGRAM_PLOTS, plot_only=["bifurcation_fixpoint"]
    )
    mv.pm.plot_from_cfg(
        plots_cfg=BIFURCATION_DIAGRAM_PLOTS,
        plot_only=["bifurcation_fixpoint_to_plot"],
    )
    # Plot the bifurcation using scatter
    mv.pm.plot_from_cfg(
        plots_cfg=BIFURCATION_DIAGRAM_PLOTS, plot_only=["bifurcation_scatter"]
    )
    # Plot the bifurcation using oscillation
    mv.pm.plot_from_cfg(
        plots_cfg=BIFURCATION_DIAGRAM_PLOTS,
        plot_only=["bifurcation_oscillation"],
    )

    # Redo simulation, but using several initial conditions
    mv = Multiverse(
        model_name="SavannaHomogeneous",
        run_cfg_path=BIFURCATION_DIAGRAM_RUN,
        paths=dict(out_dir=str(tmpdir)),
        **raise_exc,
        parameter_space=dict(seed=psp.ParamDim(default=0, range=[4])),
    )
    mv.run_sweep()
    mv.dm.load_from_cfg(print_tree=False)

    # Plot the bifurcation using multistability
    mv.pm.plot_from_cfg(
        plots_cfg=BIFURCATION_DIAGRAM_PLOTS, plot_only=["bifurcation_fixpoint"]
    )


@pytest.mark.skip("Need alternative way of testing this")
def test_bifurcation_diagram_2d(tmpdir):
    """Test plotting of the bifurcation diagram"""
    # Create and run simulation
    raise_exc = {"plot_manager": {"raise_exc": True}}
    mv = Multiverse(
        model_name="SavannaHomogeneous",
        run_cfg_path=BIFURCATION_DIAGRAM_2D_RUN,
        paths=dict(out_dir=str(tmpdir)),
        **raise_exc,
    )
    mv.run_sweep()

    # Load
    mv.dm.load_from_cfg(print_tree=False)

    # Plot the bifurcation using the last datapoint
    mv.pm.plot_from_cfg(
        plots_cfg=BIFURCATION_DIAGRAM_2D_PLOTS,
        plot_only=["bifurcation_diagram_2d"],
    )
    # Plot the bifurcation using the fixpoint
    mv.pm.plot_from_cfg(
        plots_cfg=BIFURCATION_DIAGRAM_2D_PLOTS,
        plot_only=["bifurcation_diagram_2d_fixpoint_to_plot"],
    )
