"""Implements a YAML-based registry infrastructure"""

import logging
import os

import dantro.utils

from ..tools import make_columns

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

    FILE_EXTENSIONS = (".yml", ".yaml")

    def __init__(self, EntryCls: type, *, registry_dir: str):
        """Set up a registry directory for a certain class of registry entries.

        Args:
            EntryCls (type): Type of the individual entries
            registry_dir (str): Path to the directory in which the individual
                registry entry files are to be stored.
        """
        self._registry_dir = registry_dir
        self._EntryCls = EntryCls

        self._registry = KeyOrderedDict()
        self._load_from_registry_dir()

    def _load_from_registry_dir(self):
        """Load all available entries from the registry directory.

        If called multiple times, will only load entries that are not already
        loaded.
        """
        log.debug("Loading new entries from registry directory ...")

        new_entries = []
        for fname in os.listdir(self.registry_dir):
            name, ext = os.path.splitext(fname)

            if not ext.lower() in self.FILE_EXTENSIONS or name in self:
                continue

            self.add_entry(name)
            new_entries.append(name)

        log.debug(
            "Loaded %s new entr%s: %s",
            len(new_entries),
            "ies" if len(new_entries) != 1 else "y",
            ", ".join(new_entries),
        )

    @property
    def registry_dir(self) -> str:
        """The associated registry directory"""
        return self._registry_dir

    def __str__(self) -> str:
        return f"<{type(self).__name__} for {self._EntryCls.__name__} @ {self.registry_dir}>"

    # Dict interface ..........................................................

    def keys(self):
        return self._registry.keys()

    def values(self):
        return self._registry.values()

    def items(self):
        return self._registry.items()

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
            raise ValueError(
                f"No entry with name '{name}' found! "
                f"Available entries:\n{make_columns(self.keys())}"
            ) from err

    def __delitem__(self, name: str):
        """Removes a registry entry"""
        self.remove_entry(name)

    # Adding and removing .....................................................

    def add_entry(self, name: str, **data):
        """Adds a new entry of a certain name; raises if it already exists."""
        if name in self:
            raise ValueError(
                f"An {self._EntryCls.__name__} named '{name}' already exists "
                f"in {self}! Remove it or "
            )

        entry = self._EntryCls(
            name=name, registry_dir=self.registry_dir, **data
        )
        self._registry[entry.name] = entry

        log.debug("Added entry '%s'.", entry.name)
        return entry

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
            raise ValueError(
                f"Could not remove registry entry '{name}', because "
                "no such entry is present.\nAvailable entries:\n"
                f"{make_columns(self.keys())}"
            ) from err
        else:
            log.debug("Removed entry '%s' from %s.", name, self)

        os.remove(entry.registry_file_path)
        log.debug(
            "Removed associated registry file:  %s", entry.registry_file_path
        )
        # Entry goes out of scope now and is then be garbage-collected if it
        # does not exist anywhere else... Only if some action is taken on that
        # entry does it lead to file being created again.
