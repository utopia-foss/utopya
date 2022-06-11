"""Test the model_registry submodule"""

import copy
import os

import pytest

import utopya.model_registry as umr
from utopya.model_registry import BundleExistsError, ModelRegistryError
from utopya.yaml import load_yml, write_yml, yaml

from . import DEMO_DIR, DEMO_PROJECT_NAME, get_cfg_fpath
from ._utils import tmp_cfg_dir, tmp_model_registry, tmp_projects

TEST_CFG = load_yml(get_cfg_fpath("model_registry.yml"))


# Fixtures --------------------------------------------------------------------


def mib_kwargs(**misc_metadata) -> dict:
    """Some default kwargs for a ModelInfoBundle

    The additional arguments can be used to insert metadata keys such that the
    resulting info bundles differ from each other
    """
    return dict(
        paths=dict(
            executable="/abs/foo/executable/path",
            default_cfg="/abs/foo/config/path",
        ),
        metadata=dict(description="bar", misc=misc_metadata),
        project_name=DEMO_PROJECT_NAME,
    )


# Utilities module ------------------------------------------------------------


def test_load_model_cfg():
    """Tests the loading of model configurations by name"""
    # Load the dummy configuration, for testing
    mcfg, path, params_to_validate = umr.load_model_cfg(
        model_name="MinimalModel"
    )

    # Assert correct types
    assert isinstance(mcfg, dict)
    assert isinstance(path, str)
    assert isinstance(params_to_validate, dict)

    # Assert expected content
    assert mcfg["state_size"] == 100
    assert "distribution_params" in mcfg
    assert os.path.isfile(path)
    assert not params_to_validate  # none specified for this model


# Info Bundle module ----------------------------------------------------------


def test_ModelInfoBundle(tmpdir, tmp_projects):
    """Tests the ModelInfoBundle"""
    # Most basic
    mib = umr.ModelInfoBundle(model_name="foo", **mib_kwargs())

    assert mib.model_name == "foo"
    assert mib.registration_time

    assert "paths" in mib.as_dict
    assert "metadata" in mib.as_dict

    # Paths and metadata access
    assert mib["paths"] is mib.paths
    assert mib["metadata"] is mib.metadata
    assert mib["project_name"] is mib.project_name

    # as_dict returns a deep copy
    assert mib.as_dict is not mib._d

    # missing paths access
    assert isinstance(mib.missing_paths, dict)
    assert len(mib.missing_paths) == 2  # in this test

    # String representation
    assert "foo" in str(mib)

    # Equality
    assert mib == mib_kwargs()
    assert mib == umr.ModelInfoBundle(model_name="foo", **mib_kwargs())
    assert mib != umr.ModelInfoBundle(model_name="bar", **mib_kwargs())

    # YAML representation
    with open(tmpdir.join("yaml_repr.yml"), "w+") as f:
        yaml.dump(mib, f)

        f.seek(0)
        s = "".join(f.readlines())
        assert "paths" in s
        assert "metadata" in s
        assert "registration_time" not in s


def test_ModelInfoBundle_path_parsing():
    """Test the path parsing method of the ModelInfoBundle"""
    cfg = TEST_CFG["ModelInfoBundle_path_parsing"]

    for spec_name, spec in cfg.items():
        print(f"--- Test case: {spec_name}")
        spec = copy.deepcopy(spec)
        raises = spec.pop("_raises", False)
        match = spec.pop("_match", None)

        if not raises:
            mib = umr.ModelInfoBundle(**spec)

        else:
            with pytest.raises(eval(raises), match=match):
                umr.ModelInfoBundle(**spec)


# Model Registry Entry module -------------------------------------------------


def test_ModelRegistryEntry(tmpdir):
    """Test the basic workings of the ModelRegistryEntry class"""
    e = umr.ModelRegistryEntry("foo", registry_dir=tmpdir)

    # Should have created a file
    assert tmpdir.join("foo.yml").isfile()

    # Test properties and magic methods
    assert e.model_name == "foo"
    assert e.registry_dir == str(tmpdir)
    assert e.registry_file_path == str(tmpdir.join("foo.yml"))
    assert len(e) == 0
    assert "ModelRegistryEntry" in str(e)

    # Equality
    assert not e == "some object"
    assert e == e
    assert e == copy.deepcopy(e)
    assert e == umr.ModelRegistryEntry("foo", registry_dir=tmpdir)


def test_ModelRegistryEntry_bundle_handling(tmpdir):
    """Test adding bundles to a model registry entry"""
    e = umr.ModelRegistryEntry("foo", registry_dir=tmpdir)

    b_0 = e.add_bundle(**mib_kwargs(some_val=123), label="first")

    # should have item access now
    assert e.item() is b_0
    assert e["first"] is b_0
    assert b_0 in e
    assert b_0 in e.values()
    assert "first" in e
    assert "first" in e.keys()
    assert ("first", b_0) in e.items()
    assert len(e) == 1

    # Add a labelled bundle
    b_l = e.add_bundle(label="second", **mib_kwargs(some_val=234))
    assert "second" in e.keys()
    assert len(e) == 2
    assert b_l in e
    assert "second" in e
    assert b_l in e.values()
    assert ("second", b_l) in e.items()
    assert e["second"] is b_l

    # Create a new entry object to check whether it loads things correctly
    e2 = umr.ModelRegistryEntry("foo", registry_dir=tmpdir)
    assert e == e2
    assert list(e.items()) == list(e2.items())

    # After changing one of them, no longer have equality
    e2.pop("first")
    assert e != e2

    # Item access should no longer work as there are now two bundles
    with pytest.raises(ModelRegistryError, match="Could not unambiguously"):
        e.item()

    # Can also add a bundle that already exists (compares equal) if using
    # a different label
    e.add_bundle(label="a_new_label", **mib_kwargs(some_val=123))
    assert len(e) == 3
    assert e["a_new_label"] == e["first"]
    e.pop("a_new_label")
    assert "a_new_label" not in e

    # Bad label type
    with pytest.raises(TypeError, match="needs to be a string"):
        e.add_bundle(label=42, **mib_kwargs(some_val=345))
    assert len(e) == 2

    # Already existing bundles are only overwritten if explicitly allowed
    with pytest.raises(BundleExistsError, match="already exists"):
        e.add_bundle(label="first", **mib_kwargs(some_val=345))
    assert len(e) == 2

    e.add_bundle(
        label="second", **mib_kwargs(some_val=345), exists_action="overwrite"
    )
    assert len(e) == 2

    # Popping elements
    e.pop("first")
    assert len(e) == 1
    e.pop("second")
    assert len(e) == 0

    # Clearing
    e.add_bundle(label="first", **mib_kwargs(some_val=123))
    e.add_bundle(label="second", **mib_kwargs(some_val=234))
    assert len(e) == 2
    e.clear()
    assert len(e) == 0


def test_ModelRegistryEntry_file_handling(tmpdir):
    """Test adding bundles to a model registry entry"""
    # There should be no file at
    registry_file_path = tmpdir.join("foo.yml")
    assert not registry_file_path.exists()

    # Create an entry object
    e = umr.ModelRegistryEntry("foo", registry_dir=tmpdir)

    # There should now be an (empty) file
    assert str(registry_file_path) == e.registry_file_path
    assert registry_file_path.isfile()
    fsize_empty = registry_file_path.size()
    assert fsize_empty > 0

    # Add a bundle without writing
    e.add_bundle(
        **mib_kwargs(some_val=123), label="first", update_registry_file=False
    )
    assert registry_file_path.size() == fsize_empty

    # Add another, this time with updating
    e.add_bundle(**mib_kwargs(some_val=234), label="second")

    # Data should be written now
    assert registry_file_path.size() > fsize_empty

    # Add another bundle
    e.add_bundle(label="some_label", **mib_kwargs(some_val=345))

    # Error is raised when overwriting is disabled
    with pytest.raises(FileExistsError, match="At least one file"):
        e._update_registry_file(overwrite_existing=False)

    # Delete the file and make sure this leads to errors
    registry_file_path.remove()
    with pytest.raises(FileNotFoundError, match="Failed loading model reg"):
        e._load_from_registry()

    # Write some bad data to the file
    write_yml(dict(model_name="some_bad_model_name"), path=registry_file_path)
    with pytest.raises(ValueError, match="Mismatch between expected model"):
        e._load_from_registry()

    # Creation of some subdirectory works
    umr.ModelRegistryEntry("foo", registry_dir=tmpdir.join("sub", "sub"))
    assert tmpdir.join("sub", "sub").isdir()


# Model Registry Module -------------------------------------------------------


def test_ModelRegistry(tmp_cfg_dir):
    """Test the ModelRegistry class"""
    # Write a stray file into the directory; should be ignored
    os.makedirs(os.path.join(tmp_cfg_dir, "models"), exist_ok=True)
    write_yml(
        dict(), path=os.path.join(tmp_cfg_dir, "models", "some_file.notyml")
    )

    # Create the registry
    mr = umr._ModelRegistry(tmp_cfg_dir)

    # Properties and magic methods
    assert len(mr) == 0

    # Sring representation
    assert "Utopia Model Registry" in str(mr)
    assert "0 models registered" in mr.info_str
    assert "0 models registered" in mr.info_str_detailed

    # Add an entry (without bundles)
    entry1 = mr.register_model_info("model1")
    assert "model1" in mr
    assert len(entry1) == 0
    assert len(mr) == 1

    # Add another entry, this time with a bundle
    entry2 = mr.register_model_info(
        "model2", label="some_label", **mib_kwargs()
    )
    assert len(entry2) == 1
    assert len(mr) == 2

    # Try to add it again; should be skipped
    assert entry2 is mr.register_model_info(
        "model2", exists_action="skip", label="some_label", **mib_kwargs()
    )
    assert len(entry2) == 1
    assert len(mr) == 2

    # Clear bundles and start over
    mr["model2"].clear()
    assert len(entry2) == 0

    # Same with extending the bundles
    assert entry2 is mr.register_model_info(
        "model2", label="some_label", **mib_kwargs(some_val=123123)
    )
    assert len(entry2) == 1

    # Adding it again but with a different label
    mr.register_model_info(
        "model2", label="another_label", **mib_kwargs(some_val=123123)
    )
    assert len(entry2) == 2
    entry2.pop("another_label")
    assert len(entry2) == 1

    # ...unless selected to validate it
    mr.register_model_info(
        "model2",
        label="some_label",
        **mib_kwargs(some_val=123123),
        exists_action="validate",
    )
    assert len(entry2) == 1

    # Could also desire raising
    with pytest.raises(ModelRegistryError, match="already exists"):
        mr.register_model_info(
            "model2", label="some_label", **mib_kwargs(some_val=123123)
        )

    # Bad exists action
    with pytest.raises(ValueError, match="Possible values: raise, skip"):
        mr.register_model_info(
            "foo", label="some_label", exists_action="bad_value"
        )

    # String representation
    assert "bundle" not in mr.info_str
    assert "bundle" in mr.info_str_detailed

    # dict access
    assert "model1" in mr
    assert "model1" in mr.keys()
    assert entry1 in mr.values()
    assert ("model1", entry1) in mr.items()
    assert mr["model1"] is entry1

    # Error messages
    # Invalid key
    with pytest.raises(ValueError, match="No model with name"):
        mr["i_do_not_exist12312312312"]

    # Adding one that already exists does not work
    with pytest.raises(ValueError, match="already is a model registered"):
        mr._add_entry("model1")

    # Item removal
    assert os.path.isfile(entry2.registry_file_path)
    mr.remove_entry("model2")
    assert not os.path.isfile(entry2.registry_file_path)

    with pytest.raises(ValueError, match="Could not remove"):
        mr.remove_entry("i_do_not_exist12312312312")
