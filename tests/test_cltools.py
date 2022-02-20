"""Test the command line methods"""

import argparse

import pytest

import utopya.cltools as clt
import utopya.model_registry as mr
from utopya.cfg import load_from_cfg_dir
from utopya.yaml import write_yml

from .test_cfg import tmp_cfg_dir
from .test_model_registry import tmp_model_registry

# Fixtures --------------------------------------------------------------------


class MockArgs(dict):
    """An attribute dict to mock the CL arguments"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


# -----------------------------------------------------------------------------


@pytest.mark.skip("Needs migration")
def test_register_project(tmp_cfg_dir, tmpdir):
    """Test the register_project command line helper function"""
    args = MockArgs()
    args.name = "ProjectName"
    args.base_dir = tmpdir.join("base")
    args.models_dir = tmpdir.join("base/src/models")
    args.python_model_tests_dir = tmpdir.join("base/python/model_tests")
    args.python_model_plots_dir = tmpdir.join("base/python/model_plots")

    # Before invocation, the (temporary) cfg dir has no projects defined and
    # the plot module paths are not adjusted
    assert not load_from_cfg_dir("projects")
    assert not load_from_cfg_dir("plot_module_paths")

    # Invoke it and test that it is written
    project = clt.register_project(args)
    print(project)
    assert project == load_from_cfg_dir("projects")["ProjectName"]

    # The python model plots should also have changed
    plot_module_paths = load_from_cfg_dir("plot_module_paths")
    assert "ProjectName" in plot_module_paths
    assert plot_module_paths["ProjectName"] == args.python_model_plots_dir

    # If invoking it without model plots, there should not be another one
    args.name = "AnotherProject"
    args.python_model_plots_dir = None

    project = clt.register_project(args)
    print(project)
    assert load_from_cfg_dir("projects")["AnotherProject"]

    assert plot_module_paths == load_from_cfg_dir("plot_module_paths")


@pytest.mark.skip("Needs to be abstracted to not rely on CMake infrastructure")
def test_copy_model_files(capsys, monkeypatch):
    """This tests the copy_model_files CLI helper function. It only tests
    the dry_run because mocking the write functions would be too difficult
    here. The actual copying is tested
    """
    # First, without prompts
    copy_model_files = lambda **kws: clt.copy_model_files(
        **kws, use_prompts=False, skip_exts=[".pyc"], dry_run=True
    )

    # This should work
    copy_model_files(
        model_name="CopyMeBare", new_name="FooBar", target_project="Utopia"
    )

    # Make sure that some content is found in the output; this is a proxy for
    # the actual behaviour...
    out, _ = capsys.readouterr()
    print(out, "\n" + "#" * 79)

    # Path changes
    assert 0 < out.find("CopyMeBare.cc") < out.find("FooBar.cc")
    assert (
        0 < out.find("CopyMeBare/CopyMeBare.cc") < out.find("FooBar/FooBar.cc")
    )

    # Added the add_subdirectory command at the correct position
    assert (
        0
        < out.find("add_subdirectory(dummy)")
        < out.find("add_subdirectory(FooBar)")
        < out.find("add_subdirectory(HdfBench)")
    )

    # Without adding to CMakeLists.txt ...
    copy_model_files(
        model_name="CopyMeBare",
        add_to_cmakelists=False,
        new_name="FooBar2",
        target_project="Utopia",
    )
    out, _ = capsys.readouterr()
    print(out, "\n" + "#" * 79)
    assert not (0 < out.find("add_subdirectory(FooBar2)"))
    assert 0 < out.find("Remember to register the new model in the ")

    # These should not work due to bad model or project names
    with pytest.raises(ValueError, match="'dummy' is already registered!"):
        copy_model_files(
            model_name="CopyMeBare", new_name="dummy", target_project="Utopia"
        )
    _ = capsys.readouterr()

    with pytest.raises(ValueError, match="No Utopia project with name 'NoSu"):
        copy_model_files(
            model_name="CopyMeBare",
            new_name="FooBar",
            target_project="NoSuchProject",
        )
    _ = capsys.readouterr()

    # These should not work, because use_prompts == False
    with pytest.raises(ValueError, match="Missing new_name argument!"):
        copy_model_files(model_name="CopyMeBare")
    _ = capsys.readouterr()

    with pytest.raises(ValueError, match="Missing target_project argument!"):
        copy_model_files(model_name="CopyMeBare", new_name="FooBar")
    _ = capsys.readouterr()

    # Now, do it again, mocking some of the prompts
    copy_model_files = lambda **kws: clt.copy_model_files(**kws, dry_run=True)

    monkeypatch.setattr("builtins.input", lambda x: "MyNewModel")
    copy_model_files(model_name="CopyMeBare", target_project="Utopia")
    out, _ = capsys.readouterr()
    print(out, "\n" + "#" * 79)
    assert 0 < out.find("Name of the new model:      MyNewModel")

    monkeypatch.setattr("builtins.input", lambda x: "Utopia")
    copy_model_files(model_name="CopyMeBare", new_name="FooBar")
    out, _ = capsys.readouterr()
    print(out, "\n" + "#" * 79)
    assert 0 < out.find("Utopia project to copy to:  Utopia")

    monkeypatch.setattr("builtins.input", lambda x: "N")
    copy_model_files(
        model_name="CopyMeBare", new_name="FooBar", target_project="Utopia"
    )
    out, _ = capsys.readouterr()
    print(out, "\n" + "#" * 79)
    assert 0 < out.find("Not proceeding")

    def raise_KeyboardInterrupt(*_):
        raise KeyboardInterrupt()

    monkeypatch.setattr("builtins.input", raise_KeyboardInterrupt)
    copy_model_files(model_name="CopyMeBare", target_project="Utopia")
    out, _ = capsys.readouterr()
    print(out, "\n" + "#" * 79)

    monkeypatch.setattr("builtins.input", raise_KeyboardInterrupt)
    copy_model_files(model_name="CopyMeBare", new_name="FooBar")
    out, _ = capsys.readouterr()
    print(out, "\n" + "#" * 79)

    monkeypatch.setattr("builtins.input", raise_KeyboardInterrupt)
    copy_model_files(
        model_name="CopyMeBare", new_name="FooBar", target_project="Utopia"
    )
    out, _ = capsys.readouterr()
    print(out, "\n" + "#" * 79)


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
