"""Implements a YAML-based registry infrastructure"""

import copy
import logging
import os

import dantro.utils

from ..exceptions import (
    EntryExistsError,
    EntryValidationError,
    MissingEntryError,
)
from ..tools import make_columns, pformat, recursive_update
from .entry import RegistryEntry

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class KeyOrderedDict(dantro.utils.KeyOrderedDict):
    """A key-ordered dict that expects string keys and sorts by the lower-case
    representation of keys.
    """

    DEFAULT_KEY_COMPARATOR = lambda _, k: k.lower()


# -----------------------------------------------------------------------------


class YAMLRegistry:
    """A registry framework that persistently stores the registry entries as
    YAML files within a common directory.

    Individual registry entries can be retrieved via a dict-like interface.
    """

    def __init__(self, EntryCls: type, *, registry_dir: str):
        """Set up a registry directory for a certain class of registry entries.

        Args:
            EntryCls (type): Type of the individual entries
            registry_dir (str): Path to the directory in which the individual
                registry entry files are to be stored.
        """
        if not issubclass(EntryCls, RegistryEntry):
            raise TypeError(
                f"EntryCls needs to be a subclass of {RegistryEntry}, "
                f"but was {EntryCls}!"
            )

        self._registry_dir = registry_dir
        self._EntryCls = EntryCls

        self._registry = KeyOrderedDict()
        self.reload()

    @property
    def registry_dir(self) -> str:
        """The associated registry directory"""
        return self._registry_dir

    def __str__(self) -> str:
        return "<{}, entry type: {}, @ {} >".format(
            type(self).__name__, self._EntryCls.__name__, self.registry_dir
        )

    def reload(self):
        """Load all available entries from the registry directory.

        If called multiple times, will only load entries that are not already
        loaded.
        """
        log.debug("Disassociating existing entries ...")
        for entry in self.values():
            entry._registry = None
        self._registry = KeyOrderedDict()

        log.debug("Re-loading entries from registry directory ...")
        new_entries = []
        for fname in os.listdir(self.registry_dir):
            name, ext = os.path.splitext(fname)

            if name in self or ext != self._EntryCls.FILE_EXTENSION:
                continue

            entry = self._EntryCls(name=name, registry=self)
            self._registry[entry.name] = entry
            new_entries.append(name)

        log.debug(
            "Loaded %s entr%s: %s",
            len(new_entries),
            "ies" if len(new_entries) != 1 else "y",
            ", ".join(new_entries),
        )

    # Dict interface ..........................................................

    def keys(self):
        return self._registry.keys()

    def values(self):
        return self._registry.values()

    def items(self):
        return self._registry.items()

    def __iter__(self):
        return self._registry.__iter__()

    def __contains__(self, name: str) -> bool:
        """Whether an entry of the given name exists in the registry"""
        return name in self._registry

    def __len__(self) -> int:
        return len(self._registry)

    # Working on entries ......................................................

    def __getitem__(self, name: str):
        """Retrieve a deep copy of a model registration entry for the given
        model name.
        """
        try:
            return self._registry[name]

        except KeyError as err:
            raise MissingEntryError(
                f"{self._EntryCls.__name__} '{name}' not found in {self}! "
                f"Available entries:\n{make_columns(self.keys())}"
            ) from err

    def __delitem__(self, name: str):
        """Removes a registry entry"""
        self.remove_entry(name)

    # Adding and removing .....................................................

    def add_entry(
        self, name: str, *, exists_action: str = "raise", **data
    ) -> RegistryEntry:
        """Creates a new entry and stores it in the registry. If an entry of
        the same name already exists, allows according to the ``exists_action``
        Adds a new entry of a certain name; raises if it already exists.

        TODO Write

        Args:
            name (str): Description
            exists_action (str, optional): Description
            **data: Description

        Returns:
            RegistryEntry: Description

        Raises:
            EntryExistsError: Description
            ValidationError:
            ValueError:
        """
        # Construct the entry itself, but *without* associating it with the
        # registry -- this allows to evaluate the exists action:
        new_entry = self._EntryCls(name=name, registry=None, **data)

        if name in self:
            log.caution("An entry named '%s' already exists!", name)

            if exists_action == "raise":
                raise EntryExistsError(
                    f"An entry '{name}' in {self} already exists! "
                    "Either remove it or choose a different `exists_action`."
                )

            elif exists_action == "validate":
                log.remark("Validating new entry against existing entry ...")
                if self[name] != new_entry:
                    # Generate a diff such that its clearer where they differ
                    import difflib
                    import json

                    natify = lambda d: json.loads(d.json())

                    diff = "\n".join(
                        difflib.Differ().compare(
                            pformat(natify(self[name])).split("\n"),
                            pformat(natify(new_entry)).split("\n"),
                        )
                    )

                    raise EntryValidationError(
                        f"Validation of project '{name}' failed!\n"
                        "The to-be-added project information did not compare "
                        "equal to the already existing one for that project.\n"
                        "Either change the `exists_action` argument to "
                        "'overwrite' or 'update' or make sure the information "
                        f"is equal.\nTheir YAML diff is as follows:\n\n{diff}"
                    )

                # else: no need to change anything below
                log.remark("Validation of entry '%s' succeeded.", name)
                return

            elif exists_action == "update":
                log.remark("Updating existing entry with new entry ...")
                data = recursive_update(self[name].dict(), copy.deepcopy(data))
                new_entry = self._EntryCls(name=name, registry=None, **data)

            elif exists_action == "overwrite":
                log.remark("Overwriting already existing entry ...")
                pass

            elif exists_action == "skip":
                log.remark("Not adding the new entry.")
                return

            else:
                raise ValueError(
                    f"Invalid `exists_action` '{exists_action}'!\n"
                    "Possible values: raise, validate, update, overwrite, skip"
                )

        # Now, make the registry association, store it here and write the file
        new_entry._set_registry(self)
        new_entry.write()
        self._registry[new_entry.name] = new_entry

        log.success("Added entry '%s'.", new_entry.name)
        return new_entry

    def remove_entry(self, name: str):
        """Removes a registry entry and deletes the associated registry file.

        Args:
            name (str): The name of the entry that is to be removed

        Raises:
            ValueError: On invalid (non-existing) model
        """
        try:
            entry = self._registry.pop(name)

        except KeyError as err:
            raise MissingEntryError(
                f"Could not remove registry entry '{name}', because "
                "no such entry is present.\nAvailable entries:\n"
                f"{make_columns(self.keys())}"
            ) from err
        else:
            log.debug("Removed entry '%s' from %s.", name, self)

        entry.remove_registry_file()
        log.debug(
            "Removed associated registry file:  %s", entry.registry_file_path
        )
        entry._registry = None
        # Entry goes out of scope now and is then be garbage-collected if it
        # does not exist anywhere else... Only if some action is taken on that
        # entry does it lead to file being created again.
