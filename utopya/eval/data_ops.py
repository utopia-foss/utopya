"""Custom data operations"""

import copy as _copy

import dantro as _dantro

from .transform import is_operation as _is_operation

# -----------------------------------------------------------------------------


@_is_operation
def update_attrs(d, attrs: dict):
    """Updates the data attributes in ``d`` with ``attrs``.

    Args:
        d (xarray.DataArray): The data array to write the attributes *to*.
        attrs (dict): The attributes to use for updating

    Returns:
        xarray.DataArray:
            A new data array like ``d`` with updated attributes.
    """
    if isinstance(d, _dantro.base.BaseDataContainer):
        d = d.data

    d = d.copy()
    d.attrs.update(_copy.deepcopy(attrs))
    return d


@_is_operation
def update_with_attrs_from(t, s):
    """Updates the data attributes in ``t`` with those from ``s``.

    Args:
        t (xarray.DataArray): The data array to write the attributes *to*.
        s (xarray.DataArray): The data array to copy the attributes *from*.

    Returns:
        xarray.DataArray:
            A new data array for ``t`` with updated attributes from ``s``.
    """
    if isinstance(t, _dantro.base.BaseDataContainer):
        t = t.data
    if isinstance(s, _dantro.base.BaseDataContainer):
        s = s.data

    return update_attrs(t, s.attrs)
