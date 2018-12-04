"""This module provides plotting functions to 
   visualize the attractive set of a dynamical system."""

from ._setup import *

import logging

import numpy as np
from scipy.signal import find_peaks

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from utopya import DataManager


# Get a logger
log = logging.getLogger(__name__)

# Increase log threshold for animation plotting
# logging.getLogger('matplotlib.animation').setLevel(logging.WARNING)

def bifurcation_codimension_one(dm: DataManager, *,
                                out_path: str,
                                mv_data,
                                dim: str,
                                time_fraction: float=0,
                                spin_up_fraction: float=0,
                                find_peaks_kwargs: dict=None,
                                to_plot_kwargs: dict,
                                plot_kwargs: dict=None,
                                save_kwargs: dict=None):
    """Plots a bifurcation diagram for one parameter dimension (dim)
        i.e. plots the final state over the parameter

    Configuration:
        creator: multiverse
        use the `select/field` key to associate one or multiple datasets
        add a matching entry in `to_plot_kwargs` with at least a 
        `plot_kwargs/color` sub_key
        choose the dimension (dim) in which the sweep was performed
    
    Arguments:
        dm (DataManager): The data manager from which to retrieve the data
        out_path (str): Where to store the plot to
        mv_data (xr.Dataset): The extracted multidimensional dataset
        dim (str): The parameter dimension of the bifurcation diagram
        time_fraction(float, optional): fraction of the simulation
            used for analysis.
            Spin up fraction is `1 - time_fraction`.
                Default: eq. of 1 step.
            Will be overwritten by specific `to_plot_kwargs/time_fraction`.
            Unused if analysis performed.
        spin_up_fraction(float, optional): fraction of the simulation
            snot used for analysis in case on signal analysis, e.g. find_peaks.
            Unused if no analysis performed.
        find_peaks_kwargs (dict, optional): if given requires `height` key
            passed on to find_peaks
            then only the return points are plotted (for stable oscillations)
            may be overwritten by `to_plot_kwargs/*/find_peak_kwargs`
        to_plot_kwargs (dict): The plotting configuration. The entries of this key
            need to match the data_vars selected in mv_data.
            sub_keys: 
                label (str, optional): label in plot
                time_fraction (str, optional): fraction of the simulation
                    used for analysis.
                    Spin up fraction is `1 - time_fraction`.
                    Default: eq. of 1 step.
                    Unused if analysis performed.
                spin_up_fraction(float, optional): fraction of the simulation
                    snot used for analysis in case on signal analysis, 
                    e.g. find_peaks.
                    Unused if no analysis performed.
                plot_kwargs (dict, optional): passed to scatter for every universe
                    color (str, recommended): unique color for multiverses
        plot_kwargs (dict, optional): Passed on to ax.set
        save_kwargs (dict, optional): kwargs to the plt.savefig function

    Raises:
        ValueError: for an invalid `dim` value
        ValueError: for an invalid or non-matching `prop_name` value
        TypeError: for a parameter dimesion higher than 2
        ValueError: for an invalid `to_plot_kwargs/*/time_fraction` value
        Warning: no color defined for `to_plot_kwargs` entry (coloring misleading)
        Warning: Simulation has one codimension, may be hard to read
    """
    if not dim in mv_data.dims:
        raise ValueError("Dimension `dim` not available in multiverse data."
                         " Was: {} with value: '{}'."
                         " Available: {}"
                         "".format(type(dim), 
                                   dim,
                                   mv_data.coords))
    if len(mv_data.coords) > 2:
        raise TypeError("mv_data has more than two parameter dimensions."
                        " Are: {}. Chosen dim: {}"
                        "".format(mv_data.coords, dim))
    elif len(mv_data.coords) > 1:
        log.warning("mv_data has codimensional parameter space."
                    " It may be difficult to read."
                    " Dimension of bifurcation: {}."
                    " Available dimensions: {}."
                    "".format(dim, mv_data.coords))
    
    def scatter(raw_data, ax, diagram_kwargs):
        plot_kwargs = diagram_kwargs['plot_kwargs']

        # scatter data
        if diagram_kwargs['find_peaks_kwargs'] is None:
            time_fraction = diagram_kwargs['time_fraction']
            plot_time = int(max(time_fraction * len(raw_data), 1.))

            ax.scatter([ raw_data[dim] ] *plot_time, raw_data[-plot_time:],
                       **plot_kwargs)
        
        # use signal analysis: find_peaks
        else:
            spin_up_fraction = diagram_kwargs['spin_up_fraction']
            spin_up_time = int(spin_up_fraction * len(raw_data))
            plot_time = len(raw_data) - spin_up_time

            find_peaks_kwargs = diagram_kwargs['find_peaks_kwargs']
            # find maxima
            maxima, max_props = find_peaks(raw_data[-plot_time:],
                                           **find_peaks_kwargs)
            
            # find minima
            amax = np.amax(raw_data)
            minima, min_props = find_peaks(amax - raw_data[-plot_time:],
                                           **find_peaks_kwargs)
            
            # print result
            if maxima.size is 0:
                plt.scatter(raw_data[dim], raw_data[-1],
                            **plot_kwargs)
            else:
                plt.scatter([ raw_data[dim] ]*len(maxima), 
                            max_props['peak_heights'], 
                            **props['plot_kwargs'])
                plt.scatter([ raw_data[dim] ]*len(minima), 
                        [ amax ]*len(minima) - min_props['peak_heights'],
                        **props['plot_kwargs'])
            

    fig = plt.figure()
    ax = fig.add_subplot(111)

    legend_handles = []
    ## scatter data for all properties to plot
    for (prop_name, props) in to_plot_kwargs.items():
        if not prop_name in mv_data.data_vars:
            raise ValueError("Key to_plot_kwargs/prop_name not available"
                             " in multiverse data."
                             " Was: {} with value: '{}'."
                             " Available in multiverse field: {}"
                             "".format(type(prop_name),
                                       prop_name,
                                       mv_data.data_vars))

        # get label
        if 'label' in props.keys(): 
            label = props['label']
        else:
            label = prop_name

        # add label to legend
        if 'plot_kwargs' in props.keys() and 'color' in props['plot_kwargs']:
            legend_handles.append(mpatches.Patch(label=label, 
                           color=props['plot_kwargs']['color']))
        else:
            # coloring misleading
            log.warning("Warning: No color defined for to_plot_kwargs "+ prop_name)


        diagram_kwargs = dict()
        if 'plot_kwargs' in props.keys():
            diagram_kwargs['plot_kwargs'] = props['plot_kwargs']
        else:
            diagram_kwargs['plot_kwargs'] = {}
        
        ## get cfg of plot mode
        # use find_peaks function
        diagram_kwargs['find_peaks_kwargs'] = find_peaks_kwargs
        # update the find_peaks_kwargs from props
        if 'find_peaks_kwargs' in props.keys():
            diagram_kwargs['find_peaks_kwargs'] = props['find_peaks_kwargs']
        
        # get time of simulation used for analysis
        if diagram_kwargs['find_peaks_kwargs'] is None:
            diagram_kwargs['time_fraction'] = time_fraction
            # check validity
            if time_fraction > 1:
                raise ValueError("Value of argument"
                        " `time_fraction` not valid."
                        " Was: {} with value: '{}'."
                        " Must be in [0., 1.]."
                        "".format(type(props['time_fraction']),
                                  props['time_fraction']))
            
            # update from props
            if 'time_fraction' in props.keys():
                diagram_kwargs['time_fraction'] = time_fraction
                # check validity
                if time_fraction > 1:
                    raise ValueError("Value of argument"
                            " `to_plot_kwargs/{}/time_fraction` not valid."
                            " Was: {} with value: '{}'."
                            " Must be in [0., 1.]."
                            "".format(prop_name,
                                      type(props['time_fraction']),
                                      props['time_fraction']))
        
        else:
            diagram_kwargs['spin_up_fraction'] = spin_up_fraction
            # check validity
            if spin_up_fraction < 0 or spin_up_fraction > 1:
                raise ValueError("Value of argument"
                        " `spin_up_fraction` not valid."
                        " Was: {} with value: '{}'."
                        " Must be in [0., 1.]."
                        "".format(type(spin_up_fraction),
                                  spin_up_fraction))
            # update from props
            if 'spin_up_time' in props.keys():
                spin_up_fraction = props['spin_up_fraction']
                diagram_kwargs['spin_up_fraction'] = spin_up_fraction
                # check validity
                if spin_up_fraction < 0 or spin_up_fraction > 1:
                    raise ValueError("Value of argument"
                            " `to_plot_kwargs/{}/spin_up_fraction` not valid."
                            " Was: {} with value: '{}'."
                            " Must be in [0., 1.]."
                            "".format(prop_name,
                                      type(spin_up_fraction),
                                      spin_up_fraction))

        # plot data
        if (len(mv_data.coords) == 1):
            for data in mv_data[prop_name]:
                scatter(data, ax, diagram_kwargs)
        elif (len(mv_data.coords) == 2):
            for datasets in mv_data[prop_name]:
                for data in datasets:
                    scatter(data, ax, diagram_kwargs)
        # else: Error raised
    # end for: property
            
    # plot legend
    if len(legend_handles) > 0:
        ax.legend(handles=legend_handles)

    # set figure kwargs
    ax.set_xlabel(dim)
    ax.set_ylabel("final State")
    ax.set(**(plot_kwargs if plot_kwargs else {}))

    # Save and close figure
    plt.savefig(out_path, **(save_kwargs if save_kwargs else {}))
    plt.close()