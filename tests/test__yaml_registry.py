"""Tests the YAML registry submodule"""

import os

import pydantic
import pytest

from utopya._yaml_registry import BaseSchema, RegistryEntry, YAMLRegistry
from utopya.exceptions import ValidationError
from utopya.yaml import load_yml

# -----------------------------------------------------------------------------


class SimpleSchema(BaseSchema):
    an_int: int
    a_str: str
    a_dict: dict
    a_float: float = 1.23


class NestedSchema(BaseSchema):
    desc: str
    nested: SimpleSchema


# .............................................................................


class SimpleEntry(RegistryEntry):
    SCHEMA = SimpleSchema


class NestedEntry(RegistryEntry):
    SCHEMA = NestedSchema


# -- Fixtures -----------------------------------------------------------------


@pytest.fixture
def test_registry(tmpdir):
    reg = YAMLRegistry(NestedEntry, registry_dir=tmpdir)
    reg.add_entry(
        "test00",
        desc="foo",
        nested=dict(an_int=1, a_str="foo", a_dict={}),
    )
    reg.add_entry(
        "test01",
        desc="bar",
        nested=dict(an_int=2, a_str="bar", a_dict=dict(a="a")),
    )
    assert len(reg) == 2

    return reg


# -- Tests --------------------------------------------------------------------


def test_entry_initialization(tmpdir):
    """Tests initializing an entry from a file and from a data dict"""
    # From dict
    entry_from_dict = SimpleEntry(
        "test00", registry_dir=tmpdir, an_int=1, a_str="2", a_dict={}
    )

    # This will have created a file
    assert os.path.isfile(entry_from_dict.registry_file_path)

    # Creating another entry object with the same name will load that file
    entry_from_file = SimpleEntry("test00", registry_dir=tmpdir)

    # They should compare equal
    assert entry_from_file == entry_from_dict

    # Cannot create an entry with the same name from dict
    with pytest.raises(
        FileExistsError, match="there already exists a registry file"
    ):
        SimpleEntry("test00", registry_dir=tmpdir, an_int=2)

    # Cannot create an entry without data if it is missing
    with pytest.raises(FileNotFoundError, match="Missing registry file"):
        SimpleEntry("test123", registry_dir=tmpdir)


def test_entry_interface(tmpdir):
    """Tests some methods of the RegistryEntry class"""
    payload = dict(
        desc="foo",
        nested=dict(an_int=1, a_str="bar", a_dict={}),
    )
    entry = NestedEntry("test_entry", registry_dir=tmpdir, **payload)

    # Registry directory and file path
    assert entry.registry_dir == tmpdir
    assert entry.registry_file_path.endswith("test_entry.yml")

    # __str__ and __repr__
    assert str(entry) == "<NestedEntry 'test_entry'>"
    assert repr(entry) == f"<NestedEntry 'test_entry': {entry.data}>"

    # __eq__
    equal_entry = NestedEntry("test_entry", registry_dir=tmpdir)
    assert entry == equal_entry

    unequal_entry = NestedEntry("unequal", registry_dir=tmpdir, **payload)
    assert entry != unequal_entry  # because the name is different

    assert entry != "an object of another type"

    # data access via attributes
    assert entry.desc == "foo"
    assert entry.nested.a_str == "bar"
    assert entry.nested.a_float == 1.23


def test_entry_manipulation_and_validation(tmpdir):
    """Checks that entries can be manipulated but writing to the YAML store is
    only successful if the schema can be validated"""
    payload = dict(
        desc="i will be manipulated",
        nested=dict(an_int=1, a_str="2", a_dict=dict(foo="bar"), a_float=3.4),
    )
    entry = NestedEntry("test_entry", registry_dir=tmpdir, **payload)
    assert entry.desc == "i will be manipulated"

    # Change the entry and store it back to the YAML file
    entry.desc = "I used to have a different value!"
    entry.write()

    entry_from_file = NestedEntry("test_entry", registry_dir=tmpdir)
    assert entry_from_file.desc == "I used to have a different value!"

    # Change the entry to an invalid value ...
    # ... that *could* be coerced: fails to write and value stays as before
    entry.desc = 1.23
    with pytest.raises(ValidationError, match="required type coercion"):
        entry.write()

    entry_from_file = NestedEntry("test_entry", registry_dir=tmpdir)
    assert entry_from_file.desc == "I used to have a different value!"

    # ... that could *not* be coerced: fails to write and value stays as before
    entry.desc = dict(foo="bar")
    with pytest.raises(pydantic.ValidationError):
        entry.write()

    entry_from_file = NestedEntry("test_entry", registry_dir=tmpdir)
    assert entry_from_file.desc == "I used to have a different value!"

    # ... that *could* be coerced -- but with coercion now allowed
    entry.RAISE_ON_COERCION = False

    entry.desc = -123
    entry.write()

    entry_from_file = NestedEntry("test_entry", registry_dir=tmpdir)
    assert entry_from_file.desc == "-123"


def test_corrupt_registry_file(tmpdir):
    """Tests that there is an error message if there is a corrupt registry file
    that cannot be read"""
    entry_from_dict = SimpleEntry(
        "entry", registry_dir=tmpdir, an_int=1, a_str="2", a_dict={}
    )

    registry_file_path = entry_from_dict.registry_file_path
    with open(registry_file_path, mode="w") as f:
        f.write("!bad-yaml-tag: {{asdasd [|–¡“{¶}|¡“¶≠¡“¶]]")

    with pytest.raises(Exception, match="Failed loading registry"):
        SimpleEntry("entry", registry_dir=tmpdir)


# -----------------------------------------------------------------------------


def test_registry_basics(tmpdir):
    """Tests the basics of the YAMLRegistry framework"""

    # Initialize empty, then add some data
    reg = YAMLRegistry(NestedEntry, registry_dir=tmpdir)
    assert len(reg) == 0

    reg.add_entry(
        "test00",
        desc="foo",
        nested=dict(an_int=1, a_str="foo", a_dict={}),
    )
    reg.add_entry(
        "test01",
        desc="bar",
        nested=dict(an_int=2, a_str="bar", a_dict=dict(a="a")),
    )
    assert len(reg) == 2

    # Check that files have been created and contain the expected values
    for name, entry in reg.items():
        assert entry.registry_file_path.endswith(f"{name}.yml")
        assert os.path.isfile(entry.registry_file_path)

        d = load_yml(entry.registry_file_path)
        assert d["nested"]["a_str"] == reg[name].nested.a_str

    # Create another registry that automatically loads existing entries from
    # the registry directory -- stray files and directories are ignored
    os.mkdir(tmpdir.join("some_directory"))
    with open(tmpdir.join("stray_file.txt"), mode="w") as f:
        f.write("foo")

    with open(tmpdir.join("file_without_extension"), mode="w") as f:
        f.write("bar")

    reg2 = YAMLRegistry(NestedEntry, registry_dir=tmpdir)
    assert len(reg2) == 2

    assert "YAMLRegistry" in str(reg)
    assert "NestedEntry" in str(reg)
    assert str(tmpdir) in str(reg)


def test_registry_adding_and_removing_entries(test_registry):
    """Tests the dict-like interface for the registry"""
    reg = test_registry

    # Add a new entry
    reg.add_entry(
        "test02", desc="spam", nested=dict(an_int=0, a_str="fish", a_dict={})
    )
    assert "test02" in reg

    # Adding an already existing entry will raise an error
    assert "test00" in reg
    with pytest.raises(ValueError, match="already exists"):
        reg.add_entry("test00")

    # Removing an entry
    entry = reg["test00"]
    reg.remove_entry("test00")
    assert "test00" not in reg
    assert not os.path.exists(entry.registry_file_path)

    # Cannot remove it again
    with pytest.raises(ValueError, match="no such entry"):
        reg.remove_entry("test00")


def test_registry_dict_interface(test_registry):
    """Tests the dict-like interface for the registry"""
    reg = test_registry
    initial_len = len(reg)

    # Iterators
    assert list(reg.items()) == list(reg._registry.items())
    assert list(reg.keys()) == list(reg._registry.keys())
    assert list(reg.values()) == list(reg._registry.values())

    # Item access
    assert reg["test00"] is reg._registry["test00"]
    with pytest.raises(ValueError, match="No entry with name"):
        reg["a key that does not exist"]

    # Item deletion
    assert "test00" in reg
    del reg["test00"]
    assert "test00" not in reg
    assert len(reg) == initial_len - 1
