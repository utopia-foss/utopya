"""Implements a single entry of the YAML-based registry framework"""

import copy
import logging
import os
from typing import Any

import pydantic

from .._yaml import load_yml as _load_yml
from .._yaml import write_yml as _write_yml
from ..exceptions import (
    MissingRegistryError,
    SchemaValidationError,
    ValidationError,
)
from ..tools import recursive_update

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


class BaseSchema(pydantic.BaseModel):
    """A base schema for registry entries"""

    class Config:
        extra = "forbid"


class RegistryEntry:
    """A registry entry holds some data (in the form of a validated pydantic
    schema) and allows to read that data from a registry file and write any
    changes to that file."""

    SCHEMA = BaseSchema
    """The data schema that is used for validation"""

    FILE_EXTENSION = ".yml"
    """The file extension that is used for the yaml files -- case-sensitive
    and *with* leading dot.
    """

    RAISE_ON_COERCION = True
    """Default behavior in case that type coercion takes place when changing
    an entry's data *after* initialization. If True, the ``check`` method will
    raise an error if there was any coercion.
    """

    _NO_FORWARDING_ATTRS = (
        "_name",
        "_data",
        "_registry",
    )
    """Attribute names that are not forwarded to the underlying data object"""

    def __init__(self, name: str, *, registry: "YAMLRegistry" = None, **data):
        """Initialize a registry entry with a certain name.

        Args:
            name (str): The name of the registry entry, corresponding to a file
                in the registry directory.
            registry (YAMLRegistry, optional): A registry object as part of
                which this entry is managed. If not given, requires ``data``.
            **data: If given, uses this data to initialize the entry. If a
                registry is associated with this entry, will also write that
                data to the corresponding file immediately.
        """
        self._name = name
        self._data = None

        self._registry = None
        self._set_registry(registry)

        # Populate data either from the registry file or the given dict
        if not data:
            if not self.has_registry:
                raise MissingRegistryError(
                    f"To construct a {type(self).__name__} without data, a "
                    "registry needs to be associated with it!"
                )

            self.load()
            log.debug("%s initialized from file.", self)

        else:
            self._data = self._parse_data(data)
            if self.has_registry:
                self.write()
                log.debug(
                    "%s initialized from data and written to file.", self
                )
            else:
                log.debug(
                    "%s initialized from data without writing to file.", self
                )

    def _parse_data(self, d: dict) -> BaseSchema:
        """Uses the schema to set the entry's data from the given dict"""
        try:
            return self.SCHEMA(**d)

        except pydantic.ValidationError as err:
            raise SchemaValidationError(
                f"Failed parsing data into {self}!\n{err}"
            ) from err

    def _set_registry(self, registry: "YAMLRegistry"):
        """Associates a registry with this entry"""
        self._registry = registry

    # Properties ..............................................................

    @property
    def name(self) -> str:
        """Name of this entry"""
        return self._name

    @property
    def has_registry(self) -> bool:
        """Whether a registry is associated with this entry"""
        return self._registry is not None

    @property
    def registry_dir(self) -> str:
        """The associated registry directory"""
        return self._registry.registry_dir

    @property
    def registry_file_path(self) -> str:
        """The absolute path to the registry file"""
        return os.path.join(
            self.registry_dir, f"{self.name}{self.FILE_EXTENSION}"
        )

    @property
    def data(self) -> BaseSchema:
        """The entry's data"""
        return self._data

    # Magic methods ...........................................................

    def __str__(self) -> str:
        """String descriptor of this object"""
        return f"<{type(self).__name__} '{self.name}'>"

    def __repr__(self) -> str:
        return f"<{type(self).__name__} '{self.name}': {self._data}>"

    def __eq__(self, other: Any) -> bool:
        """An entry compares equal if the type is identical and the name and
        data compare equal.

        .. note::

            The associated registry is not compared!
        """
        if type(self) is not type(other):
            return False
        return self._name == other._name and self._data == other._data

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

    # Checking, loading, and writing data .....................................

    def dict(self) -> dict:
        """The entry's data in pydantic's dict format, deep-copied."""
        return copy.deepcopy(self._data.dict())

    def check(
        self, *, input_data: dict = None, raise_on_coercion: bool = None
    ):
        """Invokes schema validation on this entry's data or explicitly passed
        input data.

        Args:
            input_data (dict, optional): If given, will use this data instead
                of this entry's own data (retrieved via ``dict()`` method).
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
        # Prepare input data
        input_data = input_data if input_data is not None else self.dict()

        # Perform the validation
        output_data, _, validation_error = pydantic.validate_model(
            model=self.SCHEMA, input_data=input_data
        )

        if validation_error:
            raise validation_error

        # Evaluate whether to raise in case of type coercions
        if raise_on_coercion is None:
            raise_on_coercion = self.RAISE_ON_COERCION

        if raise_on_coercion:
            import json

            if input_data != json.loads(self.SCHEMA(**output_data).json()):
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
        file does not exist. The loaded data overwrites whatever is stored in
        the entry already.
        """
        if not self.has_registry:
            raise MissingRegistryError(
                f"No registry associated with {self}, cannot load entry data!"
            )

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

        self._data = self._parse_data(d)

    def write(self, *, check_before_writing: bool = True):
        """Writes the registry entry to the corresponding registry file,
        creating it if it does not exist. Furthermore, this invokes checking of
        the data to ensure that only valid data is written.

        .. note::

            The data is written with an intermediate json-serialization
            carried out by pydantic. That ensures that the data contains only
            native data types which can be written to YAML without any custom
            representers.
        """
        if not self.has_registry:
            raise MissingRegistryError(
                f"No registry associated with {self}, cannot write entry data!"
            )

        import json

        data = json.loads(self.data.json())

        if check_before_writing:
            self.check(input_data=data)

        _write_yml(data, path=self.registry_file_path)

    def remove_registry_file(self):
        """Removes the corresponding registry file"""
        if not self.has_registry:
            raise MissingRegistryError(
                f"No registry associated with {self}, cannot remove file!"
            )

        os.remove(self.registry_file_path)
