"""Test the command line methods"""

import argparse  # FIXME now using click

import pytest

from .._fixtures import *

# import utopya.cltools as clt  # FIXME


# -----------------------------------------------------------------------------


@pytest.mark.skip(reason="needs to be adapted")
def test_prompt_for_new_plot_args(capsys, monkeypatch):
    """Tests the prompt for new plot arguments"""
    # Some mock definition of the parser
    p_eval = argparse.ArgumentParser()
    p_eval.add_argument("model_name")
    p_eval.add_argument("run_dir_path", default=None, nargs="?")

    # plot configuration
    p_eval.add_argument("--plots-cfg", default=None, nargs="?")
    p_eval.add_argument("--update-plots-cfg", default=None, nargs="+")
    p_eval.add_argument("--plot-only", default=None, nargs="*")
    p_eval.add_argument("--interactive", action="store_true")
    p_eval.add_argument("--debug", action="store_true")

    p_eval.add_argument("--run-cfg-path", default=None, nargs="?")
    p_eval.add_argument("--set-cfg", default=None, nargs="+", type=str)
    p_eval.add_argument("--suppress-data-tree", action="store_true")
    p_eval.add_argument("--full-data-tree", action="store_true")
    p_eval.add_argument("--cluster-mode", action="store_true")
    # .........................................................................

    # The prompt function
    prompt = lambda **kws: clt.prompt_for_new_plot_args(**kws, parser=p_eval)

    # Specify mock argv and args
    argv = ["dummy", "--interactive", "--plot-only", "foo", "bar"]
    args = p_eval.parse_args(argv)

    # Specify some example parameters
    monkeypatch.setattr("builtins.input", lambda x: "--plot-only foo")
    argv, args = prompt(old_argv=argv, old_args=args)
    assert "--plot-only" in argv
    assert args.plot_only == ["foo"]
    assert not args.debug

    # Again, with some other input
    # NOTE Can't test the readline startup hook using monkeypatch.setattr, thus
    #      the full user input needs be specified ...
    monkeypatch.setattr(
        "builtins.input", lambda x: "--plot-only foo bar --debug"
    )
    argv, args = prompt(old_argv=argv, old_args=args)
    assert "--plot-only" in argv
    assert "--debug" in argv
    assert args.plot_only == ["foo", "bar"]
    assert args.debug

    # Some bad arguments (that are caught by the parser)
    with pytest.raises(SystemExit):
        monkeypatch.setattr("builtins.input", lambda x: "some pos. argument")
        prompt(old_argv=argv, old_args=args)

    # Some disallowed arguments (that are caught by the prompt function)
    with pytest.raises(ValueError, match="Disallowed arguments:"):
        monkeypatch.setattr(
            "builtins.input", lambda x: "some/run/cfg/path --plot-only foo"
        )
        prompt(old_argv=argv, old_args=args)
