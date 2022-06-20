"""This module holds data processing functionality that is used in the plot
functions.
"""

import logging
import operator
import warnings
from typing import List, Tuple, Union

import numpy as np
import xarray as xr
from dantro.base import BaseDataGroup
from scipy.signal import find_peaks

log = logging.getLogger(__name__)


# Data Analysis ---------------------------------------------------------------


def find_endpoint(
    data: xr.DataArray, *, time: int = -1, **kwargs
) -> Tuple[bool, xr.DataArray]:
    """Find the endpoint of a dataset wrt. ``time`` coordinate.

    This function is compatible with the
    :py:func:`utopya.eval.plots.attractor.bifurcation_diagram`.

    Arguments:
        data (xarray.DataArray): The data
        time (int, optional): The time index to select
        **kwargs: Passed on to :py:meth:`xarray.DataArray.isel` call

    Returns:
        Tuple[bool, xarray.DataArray]: The result in the form of a 2-tuple
            ``(endpoint found, endpoint)``
    """
    return True, data.isel(time=time, **kwargs)


def find_fixpoint(
    data: xr.Dataset,
    *,
    spin_up_time: int = 0,
    abs_std: float = None,
    rel_std: float = None,
    mean_kwargs=None,
    std_kwargs=None,
    isclose_kwargs=None,
    squeeze: bool = True,
) -> Tuple[bool, float]:
    """Find the fixpoint(s) of a dataset and confirm it by standard deviation.
    For dimensions that are not ``time`` the fixpoints are compared and
    duplicates removed.

    This function is compatible with the
    :py:func:`utopya.eval.plots.attractor.bifurcation_diagram`.

    Arguments:
        data (xarray.Dataset): The data
        spin_up_time (int, optional): The first timestep included
        abs_std (float, optional): The maximal allowed absolute standard
            deviation
        rel_std (float, optional): The maximal allowed relative standard
            deviation
        mean_kwargs (dict, optional): Additional keyword arguments passed on
            to the appropriate array function for calculating mean on data.
        std_kwargs (dict, optional): Additional keyword arguments passed on to
            the appropriate array function for calculating std on data.
        isclose_kwargs (dict, optional): Additional keyword arguments passed
            on to the appropriate array function for calculating np.isclose for
            fixpoint-duplicates across dimensions other than 'time'.
        squeeze (bool, optional): Use the data.squeeze method to remove
            dimensions of length one. Default is True.

    Returns:
        tuple: (fixpoint found, mean)
    """
    if squeeze:
        data = data.squeeze()
    if len(data.dims) > 2:
        raise ValueError(
            "Method 'find_fixpoint' cannot handle data with more than 2 "
            f"dimensions. Data has dims {data.dims}"
        )
    if spin_up_time > data.time[-1]:
        raise ValueError(
            "Spin up time was chosen larger than actual simulation time in "
            f"module find_fixpoint. Was {spin_up_time}, but simulation time "
            f"was {data.time.data[-1]}."
        )

    # Get the data
    data = data.where(data.time >= spin_up_time, drop=True)

    # Calculate mean and std
    mean = data.mean(dim="time", **(mean_kwargs if mean_kwargs else {}))
    std = data.std(dim="time", **(std_kwargs if std_kwargs else {}))

    # Apply some masking, if parameters are given
    if abs_std is not None:
        mean = mean.where(std < abs_std)

    if rel_std is not None:
        mean = mean.where(std / mean < rel_std)

    conclusive = True
    for data_var_name, data_var in mean.data_vars.items():
        if data_var.shape:
            for i, val in enumerate(data_var[:-1]):
                mask = np.isclose(
                    val,
                    data_var[i + 1 :],
                    **(isclose_kwargs if isclose_kwargs else {}),
                )
                data_var[i + 1 :][mask] = np.nan

        conclusive = conclusive and (np.count_nonzero(~np.isnan(data_var)) > 0)

    return conclusive, mean


def find_multistability(*args, **kwargs) -> Tuple[bool, float]:
    """Find the multistabilities of a dataset.

    Invokes :py:func:`.find_fixpoint`. This function is conclusive if
    :py:func:`.find_fixpoint` is conclusive with multiple entries.

    Args:
        *args: passed to :py:func:`.find_fixpoint`
        **kwargs: passed to :py:func:`.find_fixpoint`

    Returns
        Tuple[bool, float]: ``(multistability found, mean value)``
    """
    conclusive, mean = find_fixpoint(*args, **kwargs)

    if not conclusive:
        return conclusive, mean

    for data_var_name, data_var in mean.data_vars.items():
        # Conclusive only if there are at least two non-nan values.
        # Count the non-zero entries of the inverse of boolian array np.isnan.
        # Need negation operator for that.
        if np.count_nonzero(~np.isnan(data_var)) > 1:
            return True, mean

    return False, mean


def find_oscillation(
    data: xr.Dataset,
    *,
    spin_up_time: int = 0,
    squeeze: bool = True,
    **find_peak_kwargs,
) -> Tuple[bool, list]:
    """Find oscillations in a dataset.

    This function is compatible with the
    :py:func:`utopya.eval.plots.attractor.bifurcation_diagram`.

    Arguments:
        data (xarray.Dataset): The data
        spin_up_time (int, optional): The first timestep included
        squeeze (bool, optional): Use the data.squeeze method to remove
            dimensions of length one. Default is True.
        **find_peak_kwargs: Passed on to
            :py:func:`scipy.signal.find_peaks`.
            If not given, will set ``height`` kwarg to ``-1.e+15``.

    Returns:
        Tuple[bool, list]: (oscillation found, [min, max])
    """
    if squeeze:
        data = data.squeeze()
    if len(data.dims) > 1:
        raise ValueError(
            "Method 'find_oscillation' cannot handle data with more than 1 "
            f"dimension. Data has dims {data.dims}"
        )
    if spin_up_time > data.time[-1]:
        raise ValueError(
            "Spin up time was chosen larger than actual simulation time in "
            f"module find_oscillation. Was {spin_up_time}, but simulation "
            f"time was {data.time.data[-1]}."
        )

    # Only use the data after spin up time
    data = data.where(data.time >= spin_up_time, drop=True)

    coords = {k: v for k, v in data.coords.items()}
    coords.pop("time", None)
    coords["osc"] = ["min", "max"]
    attractor = xr.Dataset(coords=coords, attrs={"conclusive": False})

    if not find_peak_kwargs.get("height"):
        find_peak_kwargs["height"] = -1e15

    for data_var_name, data_var in data.items():
        maxima, max_props = find_peaks(data_var, **find_peak_kwargs)
        amax = np.amax(data_var)
        minima, min_props = find_peaks(amax - data_var, **find_peak_kwargs)

        if not maxima.size or not minima.size:
            mean = data_var.mean(dim="time")
            attractor[data_var_name] = ("osc", [mean, mean])

        else:
            # Build (min, max) pair
            min_max = [
                amax - min_props["peak_heights"][-1],
                max_props["peak_heights"][-1],
            ]
            attractor[data_var_name] = ("osc", min_max)

            # at least one data_var performs oscillations
            attractor.attrs["conclusive"] = True

    if attractor.attrs["conclusive"]:
        return True, attractor
    return False, attractor
