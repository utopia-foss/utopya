"""This module implements the :py:class:`~utopya.stop_conditions.StopCondition`
class, which is used by the :py:class:`~utopya.workermanager.WorkerManager` to
stop a worker process in certain situations.

In addition, it implements a set of basic stop condition functions and
provides the :py:func:`~utopya.stop_conditions.stop_condition_function`
decorator which is required to make them accessible by name.
"""

import copy
import logging
import time
import warnings
from typing import Callable, Dict, List, Set, Tuple, Union

from dantro.data_ops.db import BOOLEAN_OPERATORS as _OPERATORS
from paramspace.tools import recursive_getitem as _recursive_getitem

log = logging.getLogger(__name__)

SIG_STOPCOND = "SIGUSR1"
"""Signal to use for stopping workers with fulfilled stop conditions"""

STOP_CONDITION_FUNCS: Dict[str, Callable] = dict()
"""Registered stop condition functions are stored in this dictionary. These
functions evaluate whether a certain stop condition is actually fulfilled.

To that end, a :py:class:`~utopya.task.WorkerTask` object is passed to these
functions, the information in which can be used to determine whether the
condition is fulfilled.
The signature of these functions is: ``(task: WorkerTask, **kws) -> bool``
"""

_FAILED_MONITOR_ENTRY_CHECKS = []
"""Keeps track of failed monitor entry checks in the
:py:func:`~utopya.stop_conditions.check_monitor_entry`
stop condition function in order to avoid repetitive warnings.
"""

# -----------------------------------------------------------------------------


class StopCondition:
    """A StopCondition object holds information on the conditions in which a
    worker process should be stopped.
    """

    def __init__(
        self,
        *,
        to_check: List[dict] = None,
        name: str = None,
        description: str = None,
        enabled: bool = True,
        func: Union[Callable, str] = None,
        **func_kwargs,
    ):
        """Create a new stop condition object.

        Args:
            to_check (List[dict], optional): A list of dicts, that holds the
                functions to call and the arguments to call them with. The only
                requirement for the dict is that the ``func`` key is available.
                All other keys are unpacked and passed as kwargs to the given
                function. The ``func`` key can be either a callable or a string
                corresponding to a name in the utopya.stopcond_funcs module.
            name (str, optional): The name of this stop condition
            description (str, optional): A short description of this stop
                condition
            enabled (bool, optional): Whether this stop condition should be
                checked; if False, it will be created but will always be un-
                fulfilled when checked.
            func (Union[Callable, str], optional): (For the short syntax
                only!) If no ``to_check`` argument is given, a function can be
                given here that will be the only one that is checked. If this
                argument is a string, it is also resolved from the utopya
                stopcond_funcs module.
            **func_kwargs: (For the short syntax) The kwargs that are passed
                to the single stop condition function
        """
        self.to_check = self._resolve_sc_funcs(to_check, func, func_kwargs)

        self.enabled = enabled
        self.description = description
        self.name = (
            name
            if name
            else " && ".join([fspec[1] for fspec in self.to_check])
        )

        # Keep track of tasks this stop condition was fulfilled for
        self._fulfilled_for = set()

        # Store the initialization kwargs such that they can be used for yaml
        # representation
        self._init_kwargs = dict(
            to_check=to_check,
            name=name,
            description=description,
            enabled=enabled,
            func=func,
            **func_kwargs,
        )

        log.debug(
            "Initialized stop condition '%s' with %d checking " "function(s).",
            self.name,
            len(self.to_check),
        )

    @property
    def fulfilled_for(self) -> Set["utopya.task.Task"]:
        """The set of tasks this stop condition was fulfilled for"""
        return self._fulfilled_for

    @staticmethod
    def _resolve_sc_funcs(
        to_check: List[dict], func: Union[str, Callable], func_kwargs: dict
    ) -> List[tuple]:
        """Resolves the functions and kwargs that are to be checked.

        The callable is either retrieved from the module-level stop condition
        functions registry or, if the given ``func`` is already a callable,
        that one will be used.
        """

        def retrieve_func(
            func_or_func_name: Union[str, Callable]
        ) -> Tuple[Callable, str]:
            """If this is already a callable, retrieve the name and return that
            tuple. Otherwise retrieve that information from the module-level
            stop condition function registry.
            """
            if callable(func_or_func_name):
                func = func_or_func_name
                return func, func.__name__

            elif not isinstance(func_or_func_name, str):
                raise TypeError(
                    "Expected callable or name of a registered stop condition "
                    f"function, but got {type(func_or_func_name).__name__} "
                    f"with value {repr(func_or_func_name)}!"
                )

            func_name = func_or_func_name
            log.debug(
                "Getting function with name '%s' from the registry.", func_name
            )
            func = STOP_CONDITION_FUNCS.get(func_name)

            if not func or not callable(func):
                _avail = ", ".join(STOP_CONDITION_FUNCS.keys())
                raise ValueError(
                    f"No stop condition function '{func_name}' available! "
                    f"Registered functions: {_avail}"
                )

            return func, func_name

        # Check different argument combinations . . . . . . . . . . . . . . . .
        # Simple case: Without `to_check`
        if func and not to_check:
            log.debug(
                "Got `func` directly and no `to_check` argument; will "
                "use only this function for checking."
            )
            func, func_name = retrieve_func(func)

            return [(func, func_name, func_kwargs)]

        elif to_check and (func or func_kwargs):
            raise ValueError(
                "Got arguments `to_check` and (one or more of) "
                "`func` or `func_kwargs`! Please pass either the "
                "`to_check` (list of dicts) or a single `func` "
                "with a dict of `func_kwargs`."
            )

        elif to_check is None and func is None:
            raise TypeError(
                "Need at least one of the required "
                "keyword-arguments `to_check` or `func`!"
            )

        # Multiple functions: need to resolve the `to_check` list
        funcs_and_kws = []

        for func_dict in to_check:
            # Work on a copy (to be able to pop the `func` entry off and reduce
            # mutability issues in the remaining dict: the func_kwargs)
            func_dict = copy.deepcopy(func_dict)
            func, func_name = retrieve_func(func_dict.pop("func"))
            log.debug("Got function '%s' for stop condition ...", func_name)

            funcs_and_kws.append((func, func_name, func_dict))

        log.debug(
            "Resolved %d stop condition function(s).", len(funcs_and_kws)
        )
        return funcs_and_kws

    def __str__(self) -> str:
        """A string representation for this StopCondition, including the name
        and, if given, the description.
        """
        if self.description:
            return f"StopCondition '{self.name}': {self.description}"
        return f"StopCondition '{self.name}'"

    def fulfilled(self, task: "utopya.task.Task") -> bool:
        """Checks if the stop condition is fulfilled for the given worker,
        using the information from the dict.

        All given stop condition functions are evaluated; if all of them return
        True, this method will also return True.

        Furthermore, if the stop condition is fulfilled, the task's set of
        fulfilled stop conditions will

        Args:
            task (utopya.task.Task): Task object that is to be checked

        Returns:
            bool: If all stop condition functions returned true for the given
                worker and its current information
        """
        if not self.enabled or not self.to_check:
            return False

        # Now perform the check on this task with all stop condition functions
        for sc_func, name, kws in self.to_check:
            if not sc_func(task, **kws):
                # One was not True -> not fulfilled, need not check the others
                log.debug("%s not fulfilled! Returning False ...", name)
                return False

        # All were True -> fulfilled
        task.fulfilled_stop_conditions.add(self)
        self._fulfilled_for.add(task)
        return True

    # YAML Constructor & Representer ..........................................
    yaml_tag = "!stop-condition"

    @classmethod
    def to_yaml(cls, representer, node):
        """Creates a yaml representation of the StopCondition object by storing
        the initialization kwargs as a yaml mapping.

        Args:
            representer (ruamel.yaml.representer): The representer module
            node (StopCondition): The node, i.e. an instance of this class

        Returns:
            a yaml mapping that is able to recreate this object
        """
        # Filter out certain entries that are None
        d = copy.deepcopy(node._init_kwargs)
        d = {
            k: v
            for k, v in d.items()
            if not (
                k in ("name", "description", "func", "to_check") and v is None
            )
            and not (k == "enabled" and v is True)
        }

        # Create the mapping representation from the filtered dict
        return representer.represent_mapping(cls.yaml_tag, d)

    @classmethod
    def from_yaml(cls, constructor, node):
        """Creates a StopCondition object by unpacking the given mapping such
        that all stored arguments are available to ``__init__``.
        """
        return cls(**constructor.construct_mapping(node, deep=True))


def stop_condition_function(f: Callable):
    """A decorator that registers the decorated callable in the module-level
    stop condition function registry. The callable's ``__name__`` attribute
    will be used as the key.

    Args:
        f (Callable): A callable that is to be added to the function registry.

    Raises:
        AttributeError: If the name already exists in the registry
    """
    func_name = f.__name__
    if (
        func_name in STOP_CONDITION_FUNCS
        and STOP_CONDITION_FUNCS.get(func_name) is not f
    ):
        raise AttributeError(
            f"A stop condition function with name '{func_name}' is already "
            f"registered, pointing to {STOP_CONDITION_FUNCS[func_name]}! "
            "Please choose a different name for the to-be-registered function."
        )

    STOP_CONDITION_FUNCS[func_name] = f
    return f


# -----------------------------------------------------------------------------
# -- Stop condition functions -------------------------------------------------
# -----------------------------------------------------------------------------


@stop_condition_function
def timeout_wall(task: "utopya.task.WorkerTask", *, seconds: float) -> bool:
    """Checks the wall timeout of the given worker

    Args:
        task (utopya.task.WorkerTask): The WorkerTask object to check
        seconds (float): After how many seconds to trigger the wall timeout

    Returns:
        bool: Whether the timeout is fulfilled
    """
    return bool((time.time() - task.profiling["create_time"]) > seconds)


@stop_condition_function
def check_monitor_entry(
    task: "utopya.task.WorkerTask",
    *,
    entry_name: str,
    operator: str,
    value: float,
) -> bool:
    """Checks if a monitor entry compares in a certain way to a given value

    Args:
        task (utopya.task.WorkerTask): The WorkerTask object to check
        entry_name (str): The name of the monitor entry, leading to the value
            to the left-hand side of the operator
        operator (str): The binary operator to use
        value (float): The right-hand side value to compare to

    Returns:
        bool: Result of op(entry, value)
    """
    # See if there were and parsed objects
    if not task.outstream_objs:
        # Nope. Nothing to check yet.
        return False

    # Try to recursively retrieve the entry from the latest monitoring output
    latest_monitor = task.outstream_objs[-1]
    try:
        entry = _recursive_getitem(latest_monitor, keys=entry_name.split("."))

    except KeyError:
        # Only warn once
        if entry_name not in _FAILED_MONITOR_ENTRY_CHECKS:
            log.caution(
                "Failed evaluating stop condition due to missing entry '%s' "
                "in monitor output!\nAvailable monitor data: %s",
                entry_name,
                latest_monitor,
            )
            _FAILED_MONITOR_ENTRY_CHECKS.append(entry_name)
        return False

    # Now perform the comparison
    return _OPERATORS[operator](entry, value)
