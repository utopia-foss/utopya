"""Any additions to dantro's data transformation framework"""

from dantro.utils import register_operation as _register_operation

# -----------------------------------------------------------------------------


def register_operation(*, skip_existing: bool = True, **kws) -> None:
    """Register an operation with the dantro data operations database.

    This invokes :py:func:`~dantro.utils.data_ops.register_operation`, but
    has ``skip_existing == True`` as default in order to reduce number of
    arguments that need to be specified in Utopia model plots.

    Args:
        skip_existing (bool, optional): Whether to skip (without an error) if
            an operation
        **kws: Passed to :py:func:`~dantro.utils.data_ops.register_operation`
    """
    return _register_operation(**kws, skip_existing=skip_existing)


def is_operation(name: str, **kws):
    """Decorator for registering operations with the dantro data operations
    database.

    Usage example:

    .. code-block:: python

        from utopya.eval import is_operation

        @is_operation("my_operation")
        def my_operation(data, *args):
            # ...

    Args:
        name (str): The name that should be used in the operation registry
        **kws: Passed to :py:func:`~utopya.eval.transform.register_operation`
    """

    def wrapper(func):
        register_operation(name=name, func=func, **kws)
        return func

    return wrapper
