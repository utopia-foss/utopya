"""Benchmarking tools for Models"""

import logging
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import h5py as h5
from dantro.tools import format_time as _format_time

log = logging.getLogger(__name__)

DEFAULT_TIMERS_ONE_SHOT: Tuple[str, ...] = (
    "init",
    "setup",
    "prolog",
    "run",
    "epilog",
    "teardown",
    "simulation",
)
"""Names of default one-shot timers in :py:class:`.ModelBenchmarkMixin`"""

DEFAULT_TIMERS_CUMULATIVE: Tuple[str, ...] = (
    "model_iteration",
    "monitor",
    "write_data",
    "full_iteration",
)
"""Names of default cumulative timers in :py:class:`.ModelBenchmarkMixin`"""


# -----------------------------------------------------------------------------


class Timer:
    """Implements a simple timer that can be paused and continued."""

    _name: str
    _one_shot: bool
    _time_func: Callable = time.time

    _running: bool
    _latest: float
    _elapsed: float
    _finished: bool

    def __init__(
        self,
        name: str,
        *,
        time_func: Callable = None,
        one_shot: bool = False,
        start: bool = False,
    ):
        self._name = name
        self._one_shot = one_shot
        self.reset()

        if time_func is not None:
            self._time_func = time_func

        if start:
            self.start()

    def _get_time(self) -> float:
        return self._time_func()

    def _assert_not_finished(self):
        if self.finished:
            raise RuntimeError(
                f"Tried to update timer '{self}' that was already marked "
                "as finished."
            )

    def __str__(self) -> str:
        segments = []
        segments.append(f"Timer '{self.name}'")
        segments.append(f"{self.elapsed:.3g}s elapsed")
        if self.running:
            segments.append("running")
        if self.finished:
            segments.append("finished")
        return f"<{', '.join(segments)}>"

    def start(self):
        self._assert_not_finished()
        self._unpause()

    def pause(self) -> float:
        self._assert_not_finished()

        if not self.running:
            raise RuntimeError(f"Cannot pause already paused timer {self}!")

        self._elapsed += self._get_time() - self._latest
        self._latest = None
        self._running = False

        if self.one_shot:
            self._finished = True
        return self.elapsed

    def unpause(self):
        if self.one_shot:
            raise RuntimeError(
                f"{self} is a one-shot timer and cannot be unpaused!"
            )
        self._assert_not_finished()
        self._unpause()

    def _unpause(self):
        self._latest = self._get_time()
        self._running = True

    def stop(self) -> float:
        self._assert_not_finished()
        if self.running:
            self.pause()
        self._finished = True
        return self.elapsed

    def reset(self):
        self._latest = None
        self._running = False
        self._finished = False
        self._elapsed = 0.0

    @property
    def name(self) -> str:
        return self._name

    @property
    def running(self) -> bool:
        return self._running

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def elapsed(self) -> float:
        if self._running:
            return self._elapsed + (self._get_time() - self._latest)
        return self._elapsed

    @property
    def one_shot(self) -> bool:
        return self._one_shot


# -----------------------------------------------------------------------------


class ModelBenchmarkMixin:
    """A mixin class that allows to conveniently gather information on the run
    time that individual parts of the model iteration require and also store it
    in the model's dataset.

    To use this, simply inherit it into your model class definition:

    .. testcode::

        from utopya_backend import BaseModel, ModelBenchmarkMixin

        class MyModel(ModelBenchmarkMixin, BaseModel):
            pass

    By default, this will enable the benchmarking and will both show the
    result at the end of the run as well as write it to a separate benchmarking
    group in the default HDF5 data group.
    To further configure its behaviour, add a ``benchmark`` entry to your
    model's configuration. For available parameters and default values, refer
    to :py:meth:`._configure_benchmark`.
    """

    _timers: Dict[str, Timer]

    _TIMER_FALLBACK_RV: Any = -1
    """The fallback value that is returned by :py:meth:`.pause_timer` and
    :py:meth:`.stop_timer` when benchmarking is completely disabled.
    """

    _dgrp_bench: Optional[h5.Group] = None
    _dset_total: Optional[h5.Dataset] = None
    _dset_cumulative: Optional[h5.Dataset] = None
    __dgrp_name: str
    __dset_dtype: str
    __dset_compression: int
    _dset_cumulative_invocation_times: List[int]

    __enabled: bool = True
    __write: bool = None
    _show_on_exit: bool = True
    _add_time_elapsed_to_monitor_info: bool = False
    _time_elapsed_info_fstr: str

    # TODO consider not having default values here

    # .........................................................................

    def __init__(self, *args, **kwargs):
        # Start with default values and timers
        self._timers = OrderedDict()
        self._add_default_timers()

        self.start_timer("simulation")
        self.start_timer("init")
        super().__init__(*args, **kwargs)
        self.stop_timer("init")

        # Have the configuration available only now, after init (running setup)
        self._configure_benchmark(**self._bench_cfg)

        # Find out if the class this is mixed-in to has a step-based iteration
        # scheme, in which case some procedures may run differently.
        self._is_stepwise_model = hasattr(self, "write_start") and hasattr(
            self, "write_every"
        )

        if self.__enabled:
            # Create the group that benchmark data will be written to
            if self.__write:
                self._dgrp_bench = self.h5group.create_group(self.__dgrp_name)

            self.log.info("Model benchmarking set up.")
        else:
            self.log.debug("Model benchmarking disabled.")

    def _add_default_timers(self):
        self.add_one_shot_timers(*DEFAULT_TIMERS_ONE_SHOT)
        self.add_cumulative_timers(*DEFAULT_TIMERS_CUMULATIVE)

    def _configure_benchmark(
        self,
        *,
        enabled: bool = True,
        show_on_exit: bool = True,
        add_to_monitor: bool = False,
        write: bool = True,
        group_name: str = "benchmark",
        compression: int = 3,
        dtype: str = "float32",
        info_fstr: str = (
            "  {time_str:>13s}   {percent_of_max:5.1f}%   {name:s}"
        ),
        info_kwargs: dict = None,
    ):
        """Applies benchmark configuration parameters.

        Args:
            enabled (bool, optional): Whether to enable benchmarking. If False,
                the behaviour will be exactly the same, but timer invocations
                will simply be ignored.

                .. note::

                    Despite being disabled, a very minor performance hit can
                    still be expected (a few booleans that are evaluated).
                    Only removing the mixin altogether will alleviate that.

            show_on_exit (bool, optional): Whether to print an info-level log
                message at the end of the simulation, showing elapsed times.
            add_to_monitor (bool, optional): Whether to add elapsed times to
                the monitoring data.
            write (bool, optional): Whether to write data to HDF5 dataset.
                The cumulative timers are stored at each invocation of
                ``write_data``, while the one-shot timers are only written at
                the end of a simulation run.
            group_name (str, optional): The name of the HDF5 group to nest the
                output datasets in.
            compression (int, optional): HDF5 compression level.
            dtype (str, optional): HDF5 data type for timing information.
                By default, this is reduced float precision, because the times
                given by :py:func:`time.time` are not as precise anyway.
            info_fstr (str, optional): The format string to use for generation
                of :py:meth:`.elapsed_info` and as default when invoking
                :py:meth:`.format_elapsed_info`.
                Available keys: ``name``, ``seconds`` (float), ``time_str``
                (pre-formatted using :py:func:`dantro.tools.format_time`),
                ``w`` (width of longest ``name``), ``max_seconds`` (float,
                largest timer value), and ``percent_of_max`` (float, relative
                timer value in percent compared to ``max_seconds``).
            info_kwargs (dict, optional): additional arguments to configure how
                :py:meth:`.elapsed_info` formats timer information. This is not
                used when calling :py:meth:`.format_elapsed_info`.
        """
        self.__enabled = enabled
        self._add_time_elapsed_to_monitor_info = add_to_monitor
        self._show_time_elapsed_on_exit = show_on_exit
        self._time_elapsed_info_fstr = info_fstr
        self._time_elapsed_info_kwargs = info_kwargs if info_kwargs else {}

        self.__write = write
        self.__dset_compression = compression
        self.__dset_dtype = dtype
        self.__dgrp_name = group_name

        if not self.__enabled:
            # Some timers have already started; easiest way is to just reset
            # all of them so that they behave effectively as disabled.
            for t in self.timers.values():
                t.reset()

    # .. Adding timers ........................................................

    def add_one_shot_timers(self, *names, **kwargs):
        for name in names:
            self._add_timer(name, one_shot=True, **kwargs)

    def add_cumulative_timers(self, *names, **kwargs):
        for name in names:
            self._add_timer(name, one_shot=False, **kwargs)

    def _add_timer(self, name, *, one_shot: bool, **kwargs):
        self.timers[name] = Timer(name, one_shot=one_shot, **kwargs)
        return self.timers[name]

    # .. Controlling timers ...................................................

    @property
    def timers(self) -> Dict[str, Timer]:
        return self._timers

    def _get_timer(self, name: str) -> Timer:
        try:
            return self.timers[name]
        except KeyError as err:
            _avail = ", ".join(sorted(self.timers))
            raise ValueError(
                f"No benchmark timer named '{name}' was added!\n"
                f"Available timers:  {_avail}"
            ) from err

    def start_timer(self, name: str) -> None:
        if not self.__enabled:
            return

        self._get_timer(name).start()

    def pause_timer(self, name: str) -> Union[float, Any]:
        if not self.__enabled:
            return self._TIMER_FALLBACK_RV

        return self._get_timer(name).pause()

    def unpause_timer(self, name: str) -> None:
        if not self.__enabled:
            return

        self._get_timer(name).unpause()

    def stop_timer(self, name: str) -> Union[float, Any]:
        if not self.__enabled:
            return self._TIMER_FALLBACK_RV

        return self._get_timer(name).stop()

    # .. Retrieving timer data ................................................

    @property
    def elapsed(self) -> Dict[str, float]:
        return {k: t.elapsed for k, t in self._timers.items()}

    @property
    def elapsed_cumulative(self) -> Dict[str, float]:
        return {
            k: t.elapsed for k, t in self._timers.items() if not t.one_shot
        }

    @property
    def elapsed_one_shot(self) -> Dict[str, float]:
        return {k: t.elapsed for k, t in self._timers.items() if t.one_shot}

    @property
    def elapsed_info(self) -> str:
        """Prepares a formatted string with all elapsed times.

        Calls :py:meth:`.format_elapsed_info` with the ``info_fstr`` and
        ``info_kwargs`` arguments specified at initialization.
        """
        return self.format_elapsed_info(
            self._time_elapsed_info_fstr, **self._time_elapsed_info_kwargs
        )

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def format_elapsed_info(
        self,
        info_fstr: str = None,
        *,
        sort: bool = False,
        width: int = None,
        ms_precision: int = 2,
        **fstr_kwargs,
    ) -> str:
        """Prepares a formatted string with all elapsed times.

        Args:
            info_fstr (str, optional): The format string to use. If not given,
                will use the default ``info_fstr`` specified at initialization.
                Available keys: ``name``, ``seconds`` (float), ``time_str``
                (pre-formatted using :py:func:`dantro.tools.format_time`),
                ``w`` (width of longest ``name``), ``max_seconds`` (float,
                largest timer value), and ``percent_of_max`` (float, relative
                timer value in percent compared to ``max_seconds``).
            sort (bool, optional): Whether to sort timers (in descending order)
                before formatting them.
            width (int, optional): If given, will use this fixed value for the
                ``w`` format key instead of the maximum width.
            ms_precision (int, optional): How many digits precision to use
                for millisecond time intervals.
            **fstr_kwargs: Passed on to the format operation.
        """
        if info_fstr is None:
            info_fstr = self._time_elapsed_info_fstr

        max_w = (
            width
            if width
            else max([1] + [len(name) for name in self.elapsed.keys()])
        )
        max_seconds = max([0] + [s for s in self.elapsed.values()])

        if sort:
            names_and_seconds = list(self.elapsed.items())
            names_and_seconds.sort(key=lambda item: item[1], reverse=True)
        else:
            names_and_seconds = self.elapsed.items()

        return "\n".join(
            info_fstr.format(
                name=name,
                seconds=seconds,
                time_str=_format_time(seconds, ms_precision=ms_precision),
                max_seconds=max_seconds,
                percent_of_max=(
                    (seconds / max_seconds) * 100 if max_seconds > 0.0 else 0.0
                ),
                w=max_w,
                **fstr_kwargs,
            )
            for name, seconds in names_and_seconds
        )

    # .. Storing timer data ...................................................

    def _write_dset_total(self):
        if not self.__enabled or not self.__write:
            return

        elapsed = self.elapsed
        N = len(elapsed)

        # May still need to create the dataset
        if self._dset_total is None:
            ds = self._dgrp_bench.create_dataset(
                "total",
                (N,),
                maxshape=(N,),
                chunks=True,
                compression=self.__dset_compression,
                dtype=self.__dset_dtype,
            )

            ds.attrs["dim_names"] = ["label"]
            ds.attrs["coords_mode__label"] = "values"
            ds.attrs["coords__label"] = list(elapsed.keys())

            self._dset_total = ds

        # TODO check what happens if invoked repeatedly, possibly with new
        #      timers added in between

        self._dset_total[:] = list(elapsed.values())

    def _write_dset_cumulative(self):
        if not self.__enabled or not self.__write:
            return

        elapsed_cumulative = self.elapsed_cumulative
        N = len(elapsed_cumulative)

        # May still need to create it
        if self._dset_cumulative is None:
            ds = self._dgrp_bench.create_dataset(
                "cumulative",
                (0, N),
                maxshape=(None, N),
                chunks=True,
                compression=self.__dset_compression,
                dtype=self.__dset_dtype,
            )
            ds.attrs["dim_names"] = ["n_iterations", "label"]

            if not self._is_stepwise_model:
                # As constantly updating write times attribute would be too
                # costly, denote the times as trivial indices for now and
                # later update that attribute (at the very end) using the list
                # containing invocation times (in number of iterations) that
                # is built up meanwhile.
                ds.attrs["coords_mode__n_iterations"] = "trivial"
            else:
                ds.attrs["coords_mode__n_iterations"] = "start_and_step"
                _sas = [self.write_start, self.write_every]
                ds.attrs["coords__n_iterations"] = _sas

            ds.attrs["coords_mode__label"] = "values"
            ds.attrs["coords__label"] = list(elapsed_cumulative.keys())

            self._dset_cumulative = ds
            self._dset_cumulative_invocation_times = []

        # May need to expand size along time dimension
        ds = self._dset_cumulative
        ds.resize(ds.shape[0] + 1, axis=0)

        # Now write:
        ds[-1, :] = list(elapsed_cumulative.values())

        # Extend list of write times (to be written to attribute at the end
        # of the run)
        if not self._is_stepwise_model:
            self._dset_cumulative_invocation_times.append(self.n_iterations)

    # .. Inject into simulation procedure .....................................
    # Note that __init__ also contains a timer

    def _invoke_setup(self):
        self.start_timer("setup")
        self._bench_cfg = self.cfg.pop("benchmark", {})
        super()._invoke_setup()
        self.stop_timer("setup")

    def _pre_run(self):
        self.start_timer("run")
        super()._pre_run()

    def _post_run(self, *, finished_run: bool):
        super()._post_run(finished_run=finished_run)

        # Stop all remaining timers
        self.stop_timer("run")
        for timer in self.timers.values():
            if timer.finished or timer.name == "teardown":
                continue
            self.stop_timer(timer.name)

        # Write total values for all timers
        self._write_dset_total()

        # Ensure that coordinate labels for n_iterations are stored
        if (
            self.__enabled
            and self.__write
            and self._dset_cumulative is not None
            and self._dset_cumulative_invocation_times
            and not self._is_stepwise_model
        ):
            ds = self._dset_cumulative
            times = self._dset_cumulative_invocation_times
            ds.attrs["coords_mode__n_iterations"] = "values"
            ds.attrs["coords__n_iterations"] = times
            self.log.debug("times:\n%s", times)
            self.log.debug("ds.attrs:  %s", dict(ds.attrs.items()))

        # Show times
        if self.__enabled and self._show_on_exit:
            self.log.info(
                "Elapsed times for parts of this simulation:\n\n%s\n",
                self.elapsed_info,
            )

    def _invoke_prolog(self):
        self.start_timer("prolog")
        super()._invoke_prolog()
        self.stop_timer("prolog")

    def _pre_iterate(self):
        self.unpause_timer("full_iteration")
        super()._pre_iterate()

    def _invoke_iterate(self):
        self.unpause_timer("model_iteration")
        super()._invoke_iterate()
        self.pause_timer("model_iteration")

    def _pre_monitor(self):
        self.unpause_timer("monitor")
        super()._pre_monitor()

    def _emit_monitor(self):
        if self._add_time_elapsed_to_monitor_info:
            self._monitor_info["timers"] = self.elapsed
        super()._emit_monitor()

    def _post_monitor(self):
        super()._post_monitor()
        self.pause_timer("monitor")

    def _invoke_write_data(self):
        self.unpause_timer("write_data")
        super()._invoke_write_data()
        self._write_dset_cumulative()
        self.pause_timer("write_data")

    def _post_iterate(self):
        super()._post_iterate()
        self.pause_timer("full_iteration")

    def _invoke_epilog(self, **kwargs):
        self.start_timer("epilog")
        super()._invoke_epilog(**kwargs)
        self.stop_timer("epilog")

    def __del__(self):
        self.start_timer("teardown")
        super().__del__()
        self.stop_timer("teardown")
