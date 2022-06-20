"""This module implements the ModelRegistryEntry class, which contains a set
of ModelInfoBundle objects. These can be combined in a labelled and unlabelled
fashion.
"""

import copy
import logging
import os
import time
from itertools import chain
from typing import Generator, Iterator, Tuple, Union

from .._yaml import load_yml, write_yml
from ..cfg import UTOPYA_CFG_DIR
from ..exceptions import (
    BundleExistsError,
    BundleValidationError,
    MissingBundleError,
    ModelRegistryError,
)
from ..tools import pformat
from .info_bundle import TIME_FSTR, ModelInfoBundle

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


class ModelRegistryEntry:
    """Holds model config bundles for a single model.

    Instances of this class are associated with a file in the model registry
    directory. Upon change, they update that file.
    """

    def __init__(self, model_name: str, *, registry_dir: str):
        """Initialize a model registry entry from a registry directory.

        Expects a file named <model_name>.yml in the registry directory. If it
        does not exist, creates an empty one.
        """
        self._model_name = model_name
        self._registry_dir = registry_dir

        self._bundles = dict()
        self._default_label = None

        # If no file exists for this entry, create empty one. Otherwise: load.
        if not os.path.exists(self.registry_file_path):
            log.debug(
                "Creating empty registry file for registry entry of "
                "model '%s' ...",
                self.model_name,
            )
            self._update_registry_file()  # creates file if path doesn't exist

        else:
            self._load_from_registry()

        log.debug(
            "Initialized registry entry for model '%s' with a total "
            "of %d bundles.",
            self.model_name,
            len(self),
        )

    @property
    def model_name(self) -> str:
        """Name of this model"""
        return self._model_name

    @property
    def registry_dir(self) -> str:
        """The associated registry directory"""
        return self._registry_dir

    @property
    def registry_file_path(self) -> str:
        """The absolute path to the registry file"""
        return os.path.join(self.registry_dir, f"{self.model_name}.yml")

    @property
    def default_label(self) -> Union[str, None]:
        """The default label"""
        return self._default_label

    @default_label.setter
    def default_label(self, val: Union[str, None]):
        """Sets the default label value. If None, there will be no default."""
        self.set_default_label(val, update_registry_file=True)

    @property
    def default_bundle(self) -> ModelInfoBundle:
        """Returns the default bundle, if set; raises if not"""
        if self.default_label is not None:
            return self._bundles[self.default_label]

        raise ModelRegistryError(
            f"No `default_label` set for {self}; "
            "cannot return a default bundle!"
        )

    # Magic methods ...........................................................

    def __len__(self) -> int:
        """Returns number of registered bundles"""
        return len(self._bundles)

    def __contains__(self, other: Union[ModelInfoBundle, str]) -> bool:
        """Checks if the given object *or* key is part of this registry entry."""
        if isinstance(other, str):
            return other in self._bundles
        return other in self.values()

    def __str__(self) -> str:
        return "<{} '{}'; {} bundle{}, default: '{}'>".format(
            type(self).__name__,
            self.model_name,
            len(self),
            "s" if len(self) != 1 else "",
            self.default_label,
        )

    def __eq__(self, other) -> bool:
        """Check for equality by inspecting stored bundles and model name"""
        if not isinstance(other, ModelRegistryEntry):
            return False
        return self._as_dict(self) == other._as_dict(other)

    # Access ..................................................................

    def __getitem__(self, key: str) -> ModelInfoBundle:
        """Return a bundle for the given label. If None, tries to return the
        single registered item.
        """
        try:
            return self._bundles[key]

        except KeyError as err:
            _avail = ", ".join(self.keys())
            raise MissingBundleError(
                f"No bundle labelled '{key}' registered in {self}!\n"
                f"Available labels:  {_avail}"
            ) from err

    def item(self) -> ModelInfoBundle:
        """Retrieve a single bundle for this model, if not ambiguous.

        This will work only in two cases:
            - If a default label is set, returns the corresponding bundle
            - If there is only a single bundle availble, returns that one

        Returns:
            ModelInfoBundle: The unambiguously selectable model info bundle

        Raises:
            ModelRegistryError: In case the selection was ambiguous
        """
        log.remark("Getting info bundle for model '%s' ...", self.model_name)
        if self.default_label is not None:
            log.remark("  ... using default label:  %s", self.default_label)
            return self.default_bundle

        elif len(self) != 1:
            _avail = ", ".join(self.keys())
            raise MissingBundleError(
                f"Could not unambiguously select single bundle from {self}, "
                "because no default was set or because the number of bundles "
                "is not exactly one.\n"
                "Define a `default_label` or use `__getitem__` to access a "
                f"bundle with a specific label (available: {_avail})."
            )

        label = next(iter(self.keys()))
        log.remark("  ... selecting only registered info bundle:  %s", label)
        return self[label]

    def keys(self) -> Iterator[str]:
        """Returns keys for item access, i.e.: all registered keys"""
        return self._bundles.keys()

    def values(self) -> Generator[ModelInfoBundle, None, None]:
        """Returns stored model config bundles, starting with labelled ones"""
        for k in self.keys():
            yield self[k]

    def items(
        self,
    ) -> Generator[Tuple[Union[str, int], ModelInfoBundle], None, None]:
        """Returns keys and registered bundles, starting with labelled ones"""
        for k in self.keys():
            yield k, self[k]

    # Manipulation ............................................................

    def add_bundle(
        self,
        *,
        label: str,
        set_as_default: bool = None,
        exists_action: str = "raise",
        update_registry_file: bool = True,
        **bundle_kwargs,
    ) -> ModelInfoBundle:
        """Add a new configuration bundle to this registry entry.

        This makes sure that the added bundle does not compare equal to an
        already existing bundle.

        Args:
            label (str): The label under which to add it.
            set_as_default (bool, optional): Controls whether to set this
                bundle's ``label`` as the default label for this entry.
            exists_action (str, optional): What to do if the given ``label``
                already exists:

                * ``raise``: Do not add a new bundle and raise (default)
                * ``skip``: Do not add a new bundle, instead return the exist
                * ``overwrite``: Overwrite the existing bundle
                * ``validate``: Make sure that the new bundle compares equal
                    to the one that already exists.

            update_registry_file (bool, optional): Whether to write changes
                directly to the registry file.
            **bundle_kwargs: Passed on to construct the ``ModelInfoBundle``
                that is to be stored.

        Raises:
            BundleExistsError: If ``label`` already exists and
                ``exists_action`` was set to ``raise``.
            BundleValidationError: If ``validate`` was given but the bundle
                already stored under the given ``label`` does not compare
                equal to the to-be-added bundle.
        """
        EXISTS_ACTIONS = ("raise", "skip", "overwrite", "validate")

        if not isinstance(label, str):
            raise TypeError(
                "The label for a model info bundle needs to be a string, "
                f"but was {type(label)} {label}!"
            )

        if exists_action not in EXISTS_ACTIONS:
            raise ValueError(
                f"Invalid `exists_action` '{exists_action}'! "
                f"Possible values: {', '.join(EXISTS_ACTIONS)}"
            )

        bundle = ModelInfoBundle(model_name=self.model_name, **bundle_kwargs)

        if label in self:
            if exists_action == "skip":
                log.caution(
                    "A bundle labelled '%s' already exists; not adding.", label
                )
                return self[label]

            elif exists_action == "validate":
                if self[label] != bundle:
                    # Generate a diff such that its clearer where they differ
                    import difflib

                    diff = "\n".join(
                        difflib.Differ().compare(
                            pformat(self[label].as_dict).split("\n"),
                            pformat(bundle.as_dict).split("\n"),
                        )
                    )

                    raise BundleValidationError(
                        f"Bundle validation failed for label '{label}'! "
                        "The to-be-added bundle did not compare equal to the "
                        "bundle that already exists under that label.\n"
                        "Either change the `exists_action` argument to "
                        "'overwrite' or make sure the bundles are equal; "
                        f"their diff is as follows:\n\n{diff}"
                    )

                log.debug("Validation successful for label '%s'.", label)
                return self[label]

            elif exists_action == "overwrite":
                pass

            else:  # "raise"
                raise BundleExistsError(
                    f"An info bundle with label '{label}' already exists in "
                    f"{self}!\n"
                    "Set `exists_action` to 'overwrite', 'skip', or "
                    "'validate' to handle this error."
                )

        log.debug(
            "Adding bundle '%s' for model '%s' ...", label, self.model_name
        )
        self._bundles[label] = bundle

        if set_as_default:
            self.set_default_label(label, update_registry_file=False)

        if update_registry_file:
            self._update_registry_file()

        return bundle

    def pop(
        self, key: str, *, update_registry_file: bool = True
    ) -> ModelInfoBundle:
        """Pop a configuration bundle from this entry."""
        log.debug(
            "Removing bundle '%s' from registry entry for model '%s' ...",
            key,
            self.model_name,
        )
        bundle = self._bundles.pop(key)

        if key == self.default_label:
            self.set_default_label(None, update_registry_file=False)

        if update_registry_file:
            self._update_registry_file()

        return bundle

    def clear(self, *, update_registry_file: bool = True):
        """Removes all configuration bundles from this entry."""
        self._bundles = dict()
        self.default_label = None

        if update_registry_file:
            self._update_registry_file()

    def set_default_label(
        self, label: str, *, update_registry_file: bool = True
    ):
        """Sets the default label

        Args:
            label (str): The new label
            update_registry_file (bool, optional): Whether to update the
                registry file.
        """
        if label is not None and label not in self.keys():
            _avail = ", ".join(self.keys())
            raise ValueError(
                f"Given info bundle label '{label}' for the "
                f"'{self.model_name}' model does not exist and thus cannot be "
                "set as default!\n"
                f"Available labels:  {_avail}"
            )

        self._default_label = label
        log.debug("Set default label to '%s'", self.default_label)

        if update_registry_file:
            self._update_registry_file()

    # Loading and Storing .....................................................

    def _load_from_registry(self):
        """Load the YAML registry entry for this model from the associated
        registry file path.
        """
        try:
            obj = load_yml(self.registry_file_path)

        except Exception as exc:
            raise type(exc)(
                "Failed loading model registry file "
                f"from {self.registry_file_path}!"
            ) from exc

        # Loaded successfully
        # If a model name is given, make sure it matches the file name
        if self.model_name != obj.get("model_name", self.model_name):
            raise ValueError(
                f"Mismatch between expected model name '{self.model_name}' "
                f"and the model name '{obj['model_name']}' specified in the "
                f"registry file at {self.registry_file_path}! "
                "Check the file name and the registry file and make sure the "
                "model name matches exactly."
            )

        # Populate self. Need not update because content is freshly loaded.
        for label, kwargs in obj.get("info_bundles", {}).items():
            self.add_bundle(label=label, **kwargs, update_registry_file=False)

        self.set_default_label(
            obj.get("default_label"), update_registry_file=False
        )

    def _update_registry_file(self, *, overwrite_existing: bool = True) -> str:
        """Stores a YAML representation of this bundle in a file in the given
        directory and returns the full path.

        The file is saved under ``<model_name>.yml``, preserving the case of
        the model name.
        Before saving, this makes sure that no file exists in that directory
        whose lower-case version would compare equal to the lower-case version
        of this model.
        """
        if not os.path.exists(self.registry_dir):
            os.makedirs(self.registry_dir)

        fpath = self.registry_file_path
        fname = os.path.basename(fpath)

        # Check for duplicates, including lower case
        lc_duplicates = [
            fn
            for fn in os.listdir(self.registry_dir)
            if fn.lower() == fname.lower()
        ]
        if lc_duplicates and not overwrite_existing:
            _duplicates = ", ".join(lc_duplicates)
            raise FileExistsError(
                "At least one file with a file name conflicting with "
                f"'{fname}' was found in {self.registry_dir}: {_duplicates}. "
                "Manually delete or rename the conflicting "
                "file(s), taking care to not mix cases."
            )

        # Write to separate location; move only after write was successful.
        write_yml(self, path=f"{fpath}.tmp")
        os.replace(f"{fpath}.tmp", fpath)
        # NOTE fpath need not exist for os.replace to work

        log.debug("Successfully stored %s at %s.", self, fpath)

    # YAML representation .....................................................

    @classmethod
    def _as_dict(cls, obj) -> dict:
        """Return a copy of the dict representation of this object"""
        d = dict(
            model_name=obj.model_name,
            info_bundles=obj._bundles,
            default_label=obj.default_label,
        )
        return copy.deepcopy(d)

    @classmethod
    def to_yaml(cls, representer, node):
        """Creates a YAML representation of the data stored in this entry.
        As the data is a combination of a dict and a sequence, instances of
        this class are also represented as such.

        Args:
            representer (ruamel.yaml.representer): The representer module
            node (ModelRegistryEntry): The node to represent, i.e. an instance
                of this class.

        Returns:
            A YAML representation of the given instance of this class.
        """
        d = cls._as_dict(node)

        # Add some more information to it
        d["time_of_last_change"] = time.strftime(TIME_FSTR)

        # Return a YAML representation of the data
        return representer.represent_data(d)
