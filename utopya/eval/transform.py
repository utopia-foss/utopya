"""Overloads and additions for dantro's data transformation framework."""

from typing import Callable, Union

import dantro.data_ops as dops

# -----------------------------------------------------------------------------


def register_operation(*args, skip_existing: bool = True, **kws) -> None:
    """Register an operation with the dantro data operations database.

    This invokes :py:func:`~dantro.data_ops.db_tools.register_operation`, but
    has ``skip_existing == True`` as default in order to reduce number of
    arguments that need to be specified in utopya model plots, where duplicate
    module imports frequently cause existing entries.

    Args:
        *args: Passed to :py:func:`dantro.data_ops.db_tools.register_operation`
        skip_existing (bool, optional): Whether to skip (without an error) if
            an operation
        **kws: Passed to :py:func:`dantro.data_ops.db_tools.register_operation`
    """
    return dops.register_operation(*args, **kws, skip_existing=skip_existing)


def is_operation(arg: Union[str, Callable] = None, /, **kws):
    """Overload of dantro's ``is_operation`` decorator, using utopya's own
    registration function.

    Usage example:

    .. testcode:: is_operation_decorator

        from utopya.eval import is_operation

        @is_operation
        def my_operation(data, *args):
            pass

        @is_operation("op_with_custom_name")
        def my_other_operation(data, *args):
            pass

        @is_operation("my_operation", overwrite_existing=True)
        def yet_some_other_operation(data, *args):
            pass

    .. testcode:: is_operation_decorator
        :hide:

        from dantro.data_ops.db import _OPERATIONS
        assert "my_operation" in _OPERATIONS
        assert "op_with_custom_name" in _OPERATIONS

    Args:
        arg (Union[str, Callable], optional): The name that should be used in
            the operation registry. If not given, will use the name of the
            decorated function instead. If a callable, this refers to the
            ``@is_operation`` call syntax and will use that as a function.
        **kws: Passed to :py:func:`~.register_operation`.
    """
    return dops.is_operation(arg, _reg_func=register_operation, **kws)
