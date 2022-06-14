"""Tests the `utopya config` subcommand"""

import os

import pytest

from utopya.cfg import get_cfg_path, load_from_cfg_dir
from utopya_cli._utils import set_entries_from_kv_pairs

from ..test_cfg import tmp_cfg_dir
from . import invoke_cli

# -----------------------------------------------------------------------------


def test_set_entries_from_kv_pairs():
    """Tests the set_entries_from_kv_pairs method"""
    d = dict()

    set_entries_from_kv_pairs(
        "foo=bar",
        "bar.foo=baz",
        "an_int=123",
        "a_float=1.23",
        "a_bool=true",
        "None=null",
        "long_string=long string with spaces",
        "not_an_int=- 10",
        "another_float=-1.E10",
        "failing_float=.E10",
        "inf=inf",
        "neg_inf=-inf",
        add_to=d,
    )

    assert d["foo"] == "bar"
    assert d["bar"]["foo"] == "baz"

    assert d["an_int"] == 123
    assert isinstance(d["an_int"], int)

    assert d["a_float"] == 1.23
    assert isinstance(d["a_float"], float)

    assert d["inf"] == float("inf")
    assert d["neg_inf"] == float("-inf")

    assert d["a_bool"] is True

    assert d["None"] is None

    assert d["long_string"] == "long string with spaces"

    assert d["not_an_int"] == "- 10"
    assert isinstance(d["not_an_int"], str)

    assert d["another_float"] == float("-1.E10")
    assert isinstance(d["another_float"], float)

    assert d["failing_float"] == ".E10"
    assert isinstance(d["failing_float"], str)

    # With YAML allowed
    set_entries_from_kv_pairs(
        "null=~",
        "list=[1, 2, 3]",
        "some_dict={1: 2, foo: bar}",
        "nested.entry=[bar, baz]",
        "invalid_yaml={{{not a dict}]>",
        add_to=d,
        allow_yaml=True,
    )
    assert d["null"] is None
    assert d["list"] == [1, 2, 3]
    assert d["some_dict"] == {1: 2, "foo": "bar"}
    assert d["nested"] == dict(entry=["bar", "baz"])
    assert d["invalid_yaml"] == "{{{not a dict}]>"

    # With eval allowed
    set_entries_from_kv_pairs(
        "squared=2**4",
        "list=[1, 2, 3]",
        "bad_syntax=foo",
        "nested.entry=bar",
        add_to=d,
        allow_eval=True,
    )

    assert d["squared"] == 16
    assert d["list"] == [1, 2, 3]
    assert d["bad_syntax"] == "foo"
    assert d["nested"]["entry"] == "bar"

    # Deletion
    set_entries_from_kv_pairs("squared=DELETE", add_to=d)
    assert "squared" not in d

    set_entries_from_kv_pairs("nested.entry=DELETE", add_to=d)
    assert "entry" not in d["nested"]

    assert "i_do_not_exist" not in d
    set_entries_from_kv_pairs("i_do_not_exist=DELETE", add_to=d)
    assert "i_do_not_exist" not in d


# -----------------------------------------------------------------------------


def test_config(tmp_cfg_dir, monkeypatch):
    """Tests the `utopya config` subcommand"""

    res = invoke_cli(("config", "user", "--get"))
    assert res.exit_code == 0
    assert "{}" in res.output

    args = ("config", "user", "--set", "--get")
    res = invoke_cli(args + ("some_test_entry=foo",))
    assert res.exit_code == 0
    assert "some_test_entry: foo" in res.output

    res = invoke_cli(args + ("foo.bar=baz", "baz.bar=[1,2,3]"))
    assert res.exit_code == 0
    assert "foo.bar: baz" in res.output
    cfg = load_from_cfg_dir("user")
    assert cfg["foo"]["bar"] == "baz"

    res = invoke_cli(args + ("foo.bar=DELETE", "spam=fish"))
    print(res.output)
    assert res.exit_code == 0
    cfg = load_from_cfg_dir("user")
    assert "bar" not in cfg["foo"]
    assert cfg["spam"] == "fish"

    # Reveal; will create an empty file if such a file does not exist
    # NOTE This will not actually reveal the file when run as part of the test
    #      suite, because this does not work in all environments.
    res = invoke_cli(("config", "user", "--reveal"))
    print(res.output)
    assert res.exit_code == 0
    assert os.path.isfile(get_cfg_path("user"))

    # Edit
    res = invoke_cli(("config", "utopya", "--edit"))
    assert res.exit_code == 1
    assert "Editing config file 'utopya' failed!" in res.output

    monkeypatch.setenv("EDITOR", "echo")  # this will always work
    res = invoke_cli(("config", "utopya", "--edit"))
    assert res.exit_code == 0
    assert "edited successfully" in res.output

    # KV_PAIRS missing
    res = invoke_cli(("config", "user", "--set"))
    assert res.exit_code != 0
    assert "KV_PAIRS argument is missing" in res.output

    # Need one of --set, --get, --edit, --reveal
    res = invoke_cli(("config", "user"))
    assert res.exit_code != 0
    assert "Need at least one of the options" in res.output

    # Cannot pass --edit AND --set
    res = invoke_cli(("config", "user", "--set", "--edit"))
    assert res.exit_code != 0
    assert "Can only pass one of --set or --edit" in res.output
