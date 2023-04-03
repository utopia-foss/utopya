"""Benchmarking tools for Models"""

import logging
import time
from typing import Callable, Dict

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class Timer:
    """Implements a simple timer that can be paused and continued."""

    _name: str
    _one_shot: bool
    _time_func: Callable = time.time

    _running: bool = False
    _latest: float = None
    _elapsed: float = 0.0
    _finished: bool = False

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
        if time_func is not None:
            self._time_func = time_func
        if start:
            self.start()

    def _get_time(self) -> float:
        return self._time_func()

    def _check_not_finished(self):
        if self.finished:
            raise RuntimeError(
                f"Tried to update timer '{self}' that was already marked "
                "as finished."
            )

    def __str__(self) -> str:
        segments = []
        segments.append(f"Timer '{self.name}'")
        segments.append(f"{self.elapsed:.3g}s elapsed")
        segments.append("running" if self.running else "not running")
        if self.finished:
            segments.append("finished")
        return f"<{', '.join(segments)}>"

    def start(self):
        self._check_not_finished()
        self._unpause()

    def pause(self) -> float:
        self._check_not_finished()
        self._elapsed += self._get_time() - self._latest
        self._latest = None
        self._running = False
        return self.elapsed

    def unpause(self):
        if self.one_shot:
            raise ValueError(
                f"{self} is a one-shot timer and cannot be unpaused!"
            )
        self._check_not_finished()
        self._unpause()

    def _unpause(self):
        self._latest = self._get_time()
        self._running = True

    def stop(self) -> float:
        self._check_not_finished()
        if self.running:
            self.pause()
        self._finished = True
        return self.elapsed

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
    time that individual parts of the model iteration require."""

    _timers: Dict[str, Timer]

    def __init__(self, *args, benchmark: dict = None, **kwargs):
        self._setup_benchmark(**(benchmark if benchmark else {}))

        self.start_timer("init")
        super().__init__(*args, **kwargs)
        self.stop_timer("init")

    def _setup_benchmark(self, *, enabled: bool = True):
        self.__enabled = enabled
        self._timers = dict()

        self.add_one_shot_timers(
            "init", "setup", "prolog", "epilog", "teardown", "simulation"
        )
        self.add_cumulative_timers(
            "model_iteration", "full_iteration", "monitor", "write_data"
        )

    # .. Inject into simulation procedure .....................................
    # Note that __init__ also contains a timer

    def _invoke_setup(self):
        self.start_timer("setup")
        super()._invoke_setup()
        self.stop_timer("setup")

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

    def _post_monitor(self):
        super()._post_monitor()
        self.pause_timer("monitor")

    def _invoke_write_data(self):
        self.unpause_timer("write_data")
        super()._invoke_write_data()
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

    # .. Adding timers ........................................................

    def add_one_shot_timers(self, *names, **kwargs):
        if not self.__enabled:
            return

        for name in names:
            self._add_timer(name, one_shot=True, **kwargs)

    def add_cumulative_timers(self, *names, **kwargs):
        if not self.__enabled:
            return

        for name in names:
            self._add_timer(name, one_shot=False, **kwargs)

    def _add_timer(self, name, *, one_shot: bool, **kwargs):
        self._timers[name] = Timer(name, one_shot=one_shot, **kwargs)
        return self._timers[name]

    # .. Controlling timers ...................................................

    @property
    def timers(self) -> Dict[str, Timer]:
        return self._timers

    def start_timer(self, name: str):
        if not self.__enabled:
            return

        self._timers[name].start()

    def pause_timer(self, name: str) -> float:
        if not self.__enabled:
            return

        return self._timers[name].pause()

    def unpause_timer(self, name: str):
        if not self.__enabled:
            return

        self._timers[name].unpause()

    def stop_timer(self, name: str) -> float:
        if not self.__enabled:
            return

        return self._timers[name].stop()

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

    # .. Storing timer data ...................................................

    def _write_timing_data(self):
        raise NotImplementedError("_write_timing_data")

    # TODO Write timing data to a hdf5 dataset, injecting at the appropriate
    #      place in the base class. Allow to disable writing altogether.
