"""Tests the YAML registry submodule"""

import copy
import os

import pydantic
import pytest

from utopya._yaml_registry import BaseSchema, RegistryEntry, YAMLRegistry
from utopya.exceptions import *
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


def test_entry_initialization():
    """Tests initializing an entry (without registry)"""
    payload = dict(an_int=1, a_str="2", a_dict={})
    entry = SimpleEntry("test00", **payload)

    # Cannot create an entry without data if there is no registry
    with pytest.raises(
        MissingRegistryError, match="registry needs to be associated"
    ):
        SimpleEntry("test123")

    # Data needs to adhere to schema
    with pytest.raises(SchemaValidationError, match="Failed parsing data"):
        SimpleEntry("test00", **payload, extra_key="I am superfluous!")

    # Cannot load, write, or remove without registry associated
    with pytest.raises(MissingRegistryError):
        entry.load()

    with pytest.raises(MissingRegistryError):
        entry.write()

    with pytest.raises(MissingRegistryError):
        entry.remove_registry_file()


def test_entry_interface():
    """Tests some methods of the RegistryEntry class"""
    payload = dict(
        desc="foo",
        nested=dict(an_int=1, a_str="bar", a_dict={}),
    )
    entry = NestedEntry("test_entry", **payload)

    assert entry.name == "test_entry"

    # cannot change name
    with pytest.raises(AttributeError):
        entry.name = "new name"

    # __str__ and __repr__
    assert str(entry) == "<NestedEntry 'test_entry'>"
    assert repr(entry) == f"<NestedEntry 'test_entry': {entry.data}>"

    # __eq__
    equal_entry = NestedEntry("test_entry", **payload)
    assert entry == equal_entry

    unequal_entry = NestedEntry("unequal", **payload)
    assert entry != unequal_entry  # because the name is different

    assert entry != "an object of another type"

    # data access via attributes
    assert entry.desc == "foo"
    assert entry.nested.a_str == "bar"
    assert entry.nested.a_float == 1.23

    # data access via item access
    assert entry["desc"] is entry.desc
    assert entry["nested"]["a_str"] is entry.nested.a_str

    # data access via .get, behaving like `getattr`
    assert entry.get("desc") == entry.desc
    assert entry.get("i_do_not_exist", "FaLLbaCK") == "FaLLbaCK"
    assert entry.nested.get("i_do_not_exist", "FaLLbaCK") == "FaLLbaCK"

    with pytest.raises(AttributeError):
        entry.nested.get("i_do_not_exist")

    # dict representation
    assert entry.model_dump() == entry._data.model_dump()


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

    # Check entries
    for name, entry in reg.items():
        # files have been created and contain the expected values
        assert entry.registry_file_path.endswith(f"{name}.yml")
        assert os.path.isfile(entry.registry_file_path)

        d = load_yml(entry.registry_file_path)
        assert d["nested"]["a_str"] == reg[name].nested.a_str

        # entries have a reference to the registry itself
        assert entry._registry is reg

    # __str__
    assert "YAMLRegistry" in str(reg)
    assert "NestedEntry" in str(reg)
    assert str(tmpdir) in str(reg)

    # Create another registry that automatically loads existing entries from
    # the registry directory -- stray files and directories are ignored
    os.mkdir(tmpdir.join("some_directory"))
    with open(tmpdir.join("stray_file.txt"), mode="w") as f:
        f.write("foo")

    with open(tmpdir.join("file_without_extension"), mode="w") as f:
        f.write("bar")

    reg2 = YAMLRegistry(NestedEntry, registry_dir=tmpdir)
    assert len(reg2) == 2

    # EntryCls needs to be a subclass of RegistryEntry
    with pytest.raises(TypeError, match="needs to be a subclass"):
        YAMLRegistry(NestedSchema, registry_dir=tmpdir)

    with pytest.raises(TypeError, match="needs to be a subclass"):
        YAMLRegistry(str, registry_dir=tmpdir)


def test_registry_reload(test_registry):
    """Tests reloading"""
    reg = test_registry
    old_entries = copy.copy(reg._registry)

    reg.reload()
    assert len(reg) == len(old_entries)
    for entry_name, old_entry in old_entries.items():
        assert entry_name in reg
        assert reg[entry_name] is not old_entry


def test_registry_adding_and_removing_entries(test_registry):
    """Tests the dict-like interface for the registry"""
    reg = test_registry

    # Add a new entry
    payload = dict(desc="spam", nested=dict(an_int=0, a_str="fish", a_dict={}))
    reg.add_entry("test02", **payload)
    assert "test02" in reg

    # Adding an already existing entry will (by default) raise an error
    assert "test00" in reg
    with pytest.raises(EntryExistsError, match="already exists"):
        reg.add_entry("test00", **payload)

    # Removing an entry
    entry = reg["test00"]
    registry_file_path = entry.registry_file_path
    reg.remove_entry("test00")
    assert "test00" not in reg
    assert entry._registry is None
    assert not os.path.exists(registry_file_path)

    # Cannot remove it again
    with pytest.raises(MissingEntryError, match="no such entry"):
        reg.remove_entry("test00")


def test_registry_exists_action(test_registry):
    """Tests the behavior of the `exists_action` argument"""
    reg = test_registry
    payload = dict(
        desc="spam",
        nested=dict(
            an_int=0,
            a_str="fish",
            a_dict=dict(foo="bar", spam=123, another_level=dict(foo="bar")),
        ),
    )

    entry = reg.add_entry("entry", **payload)
    assert "entry" in reg

    # exists_action: not given -> default -> raise
    with pytest.raises(EntryExistsError):
        reg.add_entry("entry", **payload)

    # exists_action: validate -> existing entry does not change
    reg.add_entry("entry", exists_action="validate", **payload)
    assert reg["entry"] is entry

    # exists_action: validate, but with in-place changed entry (wrt. payload)
    entry.desc = "some changed value"
    with pytest.raises(EntryValidationError, match="some changed value"):
        reg.add_entry("entry", exists_action="validate", **payload)
    assert reg["entry"] is entry

    # exists_action: validate, but with changed payload
    payload["desc"] = "another changed value"
    with pytest.raises(EntryValidationError, match="another changed value"):
        reg.add_entry("entry", exists_action="validate", **payload)
    assert reg["entry"] is entry

    # exists_action: overwrite
    new_entry = reg.add_entry("entry", exists_action="overwrite", **payload)
    assert reg["entry"] is not entry
    assert new_entry is not entry
    assert new_entry.desc == "another changed value"

    # exists_action: skip
    payload["desc"] = "some new value"
    reg.add_entry("entry", exists_action="skip", **payload)
    assert reg["entry"] is new_entry
    assert reg["entry"].desc == "another changed value"

    # exists_action: update
    payload["nested"]["a_dict"] = dict(
        spam=234, fish="fish", another_level=dict(bar="baz")
    )
    reg.add_entry("entry", exists_action="update", **payload)
    assert reg["entry"].nested.a_dict == dict(
        foo="bar",
        spam=234,
        fish="fish",
        another_level=dict(foo="bar", bar="baz"),
    )

    # exist_action: (invalid)
    with pytest.raises(ValueError, match="Invalid"):
        reg.add_entry("entry", exists_action="bad value", **payload)


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
    with pytest.raises(MissingEntryError, match="NestedEntry"):
        reg["a key that does not exist"]

    # Item deletion
    assert "test00" in reg
    del reg["test00"]
    assert "test00" not in reg
    assert len(reg) == initial_len - 1


def test_entry_manipulation_and_validation(test_registry):
    """Checks that entries can be manipulated but writing to the YAML store is
    only successful if the schema can be validated"""
    reg = test_registry
    payload = dict(
        desc="i will be manipulated",
        nested=dict(an_int=1, a_str="2", a_dict=dict(foo="bar"), a_float=3.4),
    )
    entry = NestedEntry("test_entry", registry=reg, **payload)
    assert entry.desc == "i will be manipulated"

    # Change the entry and store it back to the YAML file
    original_desc = "I used to have a different value!"
    entry.desc = original_desc
    entry.write()

    entry_from_file = NestedEntry("test_entry", registry=reg)
    assert entry_from_file.desc == "I used to have a different value!"

    # Change the entry to an invalid value ...
    # ... that *could* be coerced: assignment leads to type coercion
    with pytest.raises(pydantic.ValidationError):
        entry.desc = 1.23
    assert entry.desc == original_desc
    entry.write()

    entry_from_file = NestedEntry("test_entry", registry=reg)
    assert entry_from_file.desc == original_desc

    # ... that could *not* be coerced: fails to set attribute (because of
    # config option `validate_assignment`)
    with pytest.raises(pydantic.ValidationError):
        entry.desc = dict(foo="bar")

    # ... that *could* be coerced -- but without validation
    entry.model_config["validate_assignment"] = False

    entry.desc = -123
    assert entry.desc == -123

    # ... will have a warning upon serializing
    with pytest.warns(
        UserWarning, match="serialized value may not be as expected"
    ):
        entry.write()

    # ... but cannot read it from file now
    with pytest.raises(SchemaValidationError):
        entry_from_file = NestedEntry("test_entry", registry=reg)


def test_missing_registry_file(test_registry):
    """Tests that there is an error message if there is a corrupt registry file
    that cannot be read"""
    reg = test_registry
    entry = reg[list(reg)[0]]

    os.remove(entry.registry_file_path)
    with pytest.raises(FileNotFoundError, match="Missing registry file"):
        entry.load()


def test_corrupt_registry_file(test_registry):
    """Tests that there is an error message if there is a corrupt registry file
    that cannot be read"""
    reg = test_registry

    payload = dict(
        desc="foo",
        nested=dict(an_int=1, a_str="bar", a_dict={}),
    )
    entry_from_dict = NestedEntry("entry", registry=reg, **payload)

    registry_file_path = entry_from_dict.registry_file_path
    with open(registry_file_path, mode="w") as f:
        f.write("!bad-yaml-tag: {{asdasd [|–¡“{¶}|¡“¶≠¡“¶]]")

    with pytest.raises(Exception, match="Failed loading registry"):
        NestedEntry("entry", registry=reg)
