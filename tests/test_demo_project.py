"""Tests for the demo project and models"""

from utopya import Model

from ._fixtures import *

# -----------------------------------------------------------------------------


def test_MinimalModel(with_test_models):
    """Tests the MinimalModel"""
    NAME = DUMMY_MODEL
    model = Model(name=NAME)
    mv, _ = model.create_run_load()
    mv.pm.plot_from_cfg()


def test_ExtendedModel(with_test_models):
    """Tests the MinimalModel"""
    NAME = ADVANCED_MODEL
    model = Model(name=NAME)
    mv, _ = model.create_run_load()
    mv.pm.plot_from_cfg()

    # TODO
    # # Test other configured capabilities
    # # write_every -> only every write_every step should have been written
    # # write_start -> TODO
    # write_every = int(uni[f"data/{ADVANCED_MODEL}"].attrs["write_every"])
    # assert write_every == uni["cfg"]["write_every"]
    # assert dset.shape[0] == (uni["cfg"]["num_steps"] // write_every) + 1


def test_EvalOnlyModel(with_test_models, tmpdir):
    """Tests the EvalOnlyModel

    NOTE This test also checks some of
    """
    NAME = EVALONLY_MODEL
    model = Model(name=NAME)

    out_dir = tmpdir.join("utopya_output")
    mv_updates = dict(paths=dict(out_dir=str(out_dir)))

    with pytest.raises(FileNotFoundError, match="Could not find a run direc"):
        model.create_frozen_mv(**mv_updates)

    with pytest.raises(ValueError, match="does not have an executable"):
        model.create_run_load(**mv_updates)

    mv = model.create_frozen_mv(**mv_updates)

    mv.dm.load_from_cfg()
    assert "multiverse" in mv.dm
    assert len(mv.dm["multiverse"]) == 0

    mv.pm.plot_from_cfg()
