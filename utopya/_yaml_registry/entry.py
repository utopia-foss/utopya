"""Implements a single entry of the YAML-based registry framework"""

import logging
import os
from typing import Any

import pydantic

from .._yaml import load_yml as _load_yml
from .._yaml import write_yml as _write_yml
from ..exceptions import ValidationError

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


class BaseSchema(pydantic.BaseModel):
    """A base schema for registry entries"""


class RegistryEntry:
    """A registry entry holds some data (in the form of a validated pydantic
    schema) and allows to read that data from a registry file and write any
    changes to that file."""

    SCHEMA = BaseSchema
    """The data schema that is used for validation"""

    RAISE_ON_COERCION = True
    """Default behavior in case that type coercion takes place when changing
    an entry's data *after* initialization. If True, the ``check`` method will
    raise an error if there was any coercion.
    """

    _NO_FORWARDING_ATTRS = (
        "_name",
        "_data",
        "_registry_dir",
    )
    """Attribute names that are not forwarded to the underlying data object"""

    def __init__(self, name: str, *, registry_dir: str = None, **data):
        """Initialize a registry entry with a certain name.

        Args:
            name (str): The name of the registry entry, corresponding to a file
                in the registry directory.
            registry_dir (str): The path to a registry directory.
            **data: If given, uses this data to initialize the entry in case
                that there was no registry file created yet.

        Raises:
            FileExistsError: If ``data`` was given but there already existed a
                registry file.
        """
        self._name = name
        self._data = None
        self._registry_dir = registry_dir

        # Populate data either from the registry file or the given dict
        if not data:
            self.load()
            log.debug("%s initialized from file.", self)

        else:
            if os.path.exists(self.registry_file_path):
                raise FileExistsError(
                    f"Attempted creating a new {type(self).__name__} from "
                    "dict data, but there already exists a registry file at "
                    f"{self.registry_file_path}! Either delete the file or "
                    "do not supply the dict data."
                )

            self._load_data(data)
            self.write()
            log.debug("%s initialized from data and written to file.", self)

    def _load_data(self, d: dict):
        """Uses the schema to set the entry's data from the given dict"""
        self._data = self.SCHEMA(**d)

    # Magic methods ...........................................................

    def __str__(self) -> str:
        """String descriptor of this object"""
        return f"<{type(self).__name__} '{self.name}'>"

    def __repr__(self) -> str:
        return f"<{type(self).__name__} '{self.name}': {self._data}>"

    def __getattr__(self, attr: str):
        """Forward attribute calls (that do not match the entry's other
        attributes) to the underlying entry data.

        Alternatively, use the ``data`` property to directly access the data.
        """
        return getattr(self._data, attr)

    def __setattr__(self, attr: str, value: Any):
        """Forwards attribute setting calls to the underlying entry data.

        This is only done if ``attr`` is not in ``_NO_FORWARDING_ATTRS`` and
        the ``attr`` is actually a property of the schema. Otherwise, regular
        attribute setting occurs.

        .. warning::

            Changes to the data are *not* automatically written to the YAML
            file. To do so, call
            :py:meth:`~utopya._yaml_registry.entry.RegistryEntry.write` after
            all changes have been completed.

            Note that validation will occur at that point and not when changing
            any data values.
        """
        if (
            attr in type(self)._NO_FORWARDING_ATTRS
            or attr not in self._data.schema()["properties"]
        ):
            return super().__setattr__(attr, value)
        return setattr(self._data, attr, value)

    def __eq__(self, other: Any) -> bool:
        """An entry compares equal if the type is identical and the name, data,
        and registry directory compare equal"""
        if type(self) is not type(other):
            return False
        return self.__dict__ == other.__dict__

    # Properties ..............................................................

    @property
    def name(self) -> str:
        """Name of this entry"""
        return self._name

    @property
    def registry_dir(self) -> str:
        """The associated registry directory"""
        return self._registry_dir

    @property
    def registry_file_path(self) -> str:
        """The absolute path to the registry file"""
        return os.path.join(self.registry_dir, f"{self.name}.yml")

    @property
    def data(self) -> BaseSchema:
        """The entry's data"""
        return self._data

    # Checking, loading, and writing data .....................................

    def check(self, *, raise_on_coercion: bool = None):
        """Invokes schema validation on this entry's data.

        Args:
            raise_on_coercion (bool, optional): Whether to check if type
                coercion would be required to make the current data compatible
                with this entry's data scheme. If None, will use the default
                value defined in the ``RAISE_ON_COERCION`` class variable.

        Raises:
            pydantic.ValidationError: If this entry's data model could not be
                validated with the current state of this entry.
            utopya.exceptions.ValidationError: If data coercion would be
                required for the current state of this entry to be valid.
        """
        input_data = self._data.dict()
        output_data, _, validation_error = pydantic.validate_model(
            model=self.SCHEMA, input_data=input_data
        )

        if validation_error:
            raise validation_error

        if raise_on_coercion or (
            raise_on_coercion is None and self.RAISE_ON_COERCION
        ):
            if input_data != output_data:
                raise ValidationError(
                    f"The data in {self} required type coercion to be "
                    "compatible with its schema! Either ensure that all "
                    "changes are strictly compatible with the schema or "
                    "disable raising on type coercion.\n"
                    f"Input data:\n  {input_data}\n"
                    f"Output data:\n  {output_data}"
                )

    def load(self):
        """Reads the entry from the registry file, raising an error if the
        file does not exist.
        """
        if not os.path.isfile(self.registry_file_path):
            raise FileNotFoundError(
                f"Missing registry file for {self} "
                f"at {self.registry_file_path}!"
            )

        try:
            d = _load_yml(self.registry_file_path)

        except Exception as exc:
            raise type(exc)(
                f"Failed loading registry file {self.registry_file_path}! "
                "See traceback for more information."
            ) from exc

        self._load_data(d)

    def write(self):
        """Writes the registry entry to the corresponding registry file,
        creating it if it does not exist. Furthermore, this invokes checking of
        the data to ensure that only valid data is written.
        """
        self.check()
        _write_yml(self._data.dict(), path=self.registry_file_path)
