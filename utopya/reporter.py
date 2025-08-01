"""Implementation of the reporter framework which can be used to report on the
progress or result of operations within utopya.
"""

import copy
import getpass
import logging
import os
import platform
from collections import Counter, OrderedDict, defaultdict, deque
from datetime import datetime as dt
from datetime import timedelta
from functools import partial
from shutil import get_terminal_size as _get_terminal_size
from typing import Callable, Dict, List, Optional, Set, Union

import numpy as np
from yayaml import yaml_dumps as _yaml_dumps

from .tools import TTY_COLS, format_time, get_physical_memory_str

log = logging.getLogger(__name__)

_DEFAULT_distributed_status_fstr: str = (
    "  {progress_here:>5s}  @  {host_name_short:12s} - {pid:7d}: "
    "{status:10s}  ({tags})"
)
"""The format string to use for the joined run status"""

# -----------------------------------------------------------------------------


class ReportFormat:
    """A report format aggregates callables for a single report parser and
    potentially multiple report writers. As a whole, it contains all arguments
    needed to generate a certain kind of report.

    It is used in :py:class:`utopya.reporter.Reporter` and derived classes,
    which are the classes that actually implement the parsers and writers.
    """

    def __init__(
        self,
        *,
        parser: Callable,
        writers: List[Callable],
        min_report_intv: float = None,
    ):
        """Initializes a ReportFormat object, which gathers callables needed to
        create a report in a certain format.

        Args:
            parser (Callable): The parser method to use
            writers (List[Callable]): The writer method(s) to use
            min_report_intv (float, optional): The minimum report interval of
                reports in this format. Determines the time (in seconds) that
                needs to have passed before the next report will be emitted.
        """
        self.parser = parser
        self.writers = writers

        self._min_report_intv = None
        self.min_report_intv = min_report_intv

        self.num_reports = 0
        self.last_report = dt.fromtimestamp(0)  # waaay back

    @property
    def min_report_intv(self) -> Union[timedelta, None]:
        """Returns the minimum report interval, i.e. the time that needs to
        have passed between two reports.
        """
        return self._min_report_intv

    @min_report_intv.setter
    def min_report_intv(self, sec: float):
        """Set the minimum report interval, directly converting it into a
        timedelta value.
        """
        self._min_report_intv = timedelta(seconds=sec) if sec else None

    @property
    def reporting_blocked(self) -> bool:
        """Determines whether this ReportFormat may be blocked from emission,
        e.g. because of the minimum report interval not having passed yet.

        If no minimum report interval is given, will always return False.
        Otherwise checks if at least that interval has passed since the last
        report.
        """
        if not self.min_report_intv:
            return False

        return (dt.now() - self.last_report) < self.min_report_intv

    def report(
        self, *, force: bool = False, parser_kwargs: dict = None
    ) -> bool:
        """Parses and writes a report corresponding to the callables defined in
        this report format.

        Args:
            force (bool, optional): If True, will ignore the minimum report
                interval and always perform a report.
            parser_kwargs (dict, optional): Keyword arguments passed on to the
                parser

        Returns:
            bool: Whether a report was generated or not
        """
        if not force and self.reporting_blocked:
            # Do not report
            return False

        # Generate the report
        log.debug("Creating report using parser '%s' ...", self.parser)
        report = self.parser(
            report_no=self.num_reports,
            **(parser_kwargs if parser_kwargs else {}),
        )
        log.debug("Parser created report of length %d.", len(report))

        # Write the report
        for writer_name, writer in self.writers.items():
            log.debug("Writing report using writer '%s' ...", writer_name)
            writer(report)

        # Update counter and last report time
        self.num_reports += 1
        self.last_report = dt.now()

        return True


# -----------------------------------------------------------------------------


class Reporter:
    """The Reporter class holds general reporting capabilities.

    It needs to be subclassed in order to specialize its reporting functions.
    """

    def __init__(
        self,
        *,
        report_formats: Union[List[str], Dict[str, dict]] = None,
        default_format: str = None,
        report_dir: str = None,
        suppress_cr: bool = False,
    ):
        """Initialize the Reporter base class.

        Args:
            report_formats (Union[List[str], Dict[str, dict]], optional): The
                report formats to use with this reporter. If given as list
                of strings, the strings are the names of the report formats as
                well as those of the parsers; all other parameters are the
                defaults. If given as dict of dicts, the keys are the names of
                the formats and the inner dicts are the parameters to create
                report formats from.
            default_format (str, optional): The name of the default report
                format; if None is given, the .report method requires the name
                of a report format.
            report_dir (str, optional): if reporting to a file; this is the
                base directory that is reported to.
            suppress_cr (bool, optional): Whether to suppress carriage return
                characters in writers. This option is useful when the reporter
                is not the only class that writes to a stream.
        """

        super().__init__()

        # Property-managed attributes
        self._report_formats = dict()
        self._default_format = None
        self._suppress_cr = False

        # Ensure the report_formats argument is a dict, then register them
        if report_formats is None:
            report_formats = dict()

        elif isinstance(report_formats, (list, tuple)):
            report_formats = {f: dict() for f in report_formats}

        for name, params in report_formats.items():
            self.add_report_format(name, **params)

        # Set default report format
        if default_format:
            self.default_format = default_format

        # Store report directory
        if report_dir:
            self.report_dir = os.path.expanduser(str(report_dir))
        else:
            self.report_dir = None

        # Other attributes
        self.suppress_cr = suppress_cr  # NOTE writers need to implement this

        self._tmp_files: Dict[str, Set[str]] = defaultdict(set)

        log.debug("Reporter.__init__ finished.")

    # Properties ..............................................................

    @property
    def report_formats(self) -> dict:
        """Returns the dict of ReportFormat objects."""
        return self._report_formats

    @property
    def default_format(self) -> Union[None, ReportFormat]:
        """Returns the default report format or None, if not set."""
        return self._default_format

    @default_format.setter
    def default_format(self, name: str):
        """Given the name of the report formats, set the default value."""
        if name is not None:
            self._default_format = self.report_formats[name]
            log.debug("Set default report format to '%s'.", name)
        else:
            self._default_format = None
            log.debug("Unset default report format.")

    @property
    def suppress_cr(self) -> bool:
        """Whether to suppress a carriage return. Objects using the reporter
        can set this property to communicate that they will be putting content
        into the stdout stream as well. The writers can check this property
        and adjust their behaviour accordingly.
        """
        return self._suppress_cr

    @suppress_cr.setter
    def suppress_cr(self, val: bool):
        """Set the suppress_cr property.

        When setting this to True the first time, a linebreak is issued in
        order to not overwrite any previously written lines that ended with
        a carriage return character.
        """
        if val and not self.suppress_cr:
            print("")

        self._suppress_cr = val

    # Public API ..............................................................

    def add_report_format(
        self,
        name: str,
        *,
        parser: str = None,
        write_to: Union[str, Dict[str, dict]] = "stdout",
        min_report_intv: float = None,
        rf_kwargs: dict = None,
        **parser_kwargs,
    ):
        """Add a report format to this reporter.

        Args:
            name (str): The name of this format
            parser (str, optional): The name of the parser; if not given, the
                name of the report format is assumed
            write_to (Union[str, Dict[str, dict]], optional): The name of the
                writer. If this is a dict of dict, the keys will be
                interpreted as the names of the writers and the nested dict as
                the ``**kwargs`` to the writer function.
            min_report_intv (float, optional): The minimum report interval (in
                seconds) for this report format
            rf_kwargs (dict, optional): Further kwargs to ReportFormat.__init__
            **parser_kwargs: The kwargs to the parser function

        Raises:
            ValueError: A report format with this ``name`` already exists
        """
        if name in self.report_formats:
            raise ValueError(
                f"A report format with the name '{name}' already exists."
            )

        # Get the parser and writer function
        parser = self._resolve_parser(
            parser if parser else name, **parser_kwargs
        )
        writers = self._resolve_writers(write_to)

        # Initialise the ReportFormat object with the parsers and writers
        rf = ReportFormat(
            parser=parser,
            writers=writers,
            min_report_intv=min_report_intv,
            **(rf_kwargs if rf_kwargs else {}),
        )

        self._report_formats[name] = rf
        log.debug(
            "Added report format '%s' to %s.", name, self.__class__.__name__
        )

    def report(self, report_format: str = None, **kwargs) -> bool:
        """Create a report with the given format; if none is given, the default
        format is used.

        Args:
            report_format (str, optional): The report format to use
            **kwargs: Passed on to the ReportFormat.report() call

        Returns:
            bool: Whether there was a report

        Raises:
            ValueError: If no default format was set and no report format name
                was given
        """
        # Get the report format to use
        if report_format is None:
            if self.default_format is None:
                raise ValueError(
                    "Either a default format needs to be set for this "
                    f"{self.__class__.__name__} or the name of the report "
                    "format needs to be supplied to the .report method."
                )

            rf = self.default_format

        else:
            rf = self.report_formats[report_format]

        # Delegate reporting to the ReportFormat class
        return rf.report(**kwargs)

    def parse_and_write(
        self,
        *,
        parser: Union[str, Callable],
        write_to: Union[str, Callable],
        **parser_kwargs,
    ):
        """This function allows to select a parser and writer explicitly.

        Args:
            parser (Union[str, Callable]): The parser method to use.
            write_to (Union[str, Callable]): The write method to use. Can also
                be a sequence of names and/or callables or a Dict. For allowed
                specification formats, see the ._resolve_writers method.
            **parser_kwargs: Passed to the parser, if given
        """
        parser = self._resolve_parser(parser, **parser_kwargs)

        # Parse the report
        report = parser()
        log.debug(
            "Parsed report using '%s', got string of length %d.",
            parser,
            len(report),
        )

        # Determine the writers and write
        writers = self._resolve_writers(write_to)

        for writer_name, writer in writers.items():
            writer(report)
            log.debug("Wrote report using %s .", writer_name)

    # TODO implement temp file deletion

    # Private methods .........................................................

    def _resolve_parser(
        self, parser: Union[str, Callable], **parser_kwargs
    ) -> Callable:
        """Given a string or a callable, returns the corresponding callable.

        Args:
            parser (Union[str, Callable]): If a callable is already given,
                returns that; otherwise looks for a parser method with the
                given name in the attributes of this class.
            **parser_kwargs: Arguments that should be passed to the parser.
                If given, a new function is created where these arguments are
                already included.

        Returns:
            Callable: The desired parser function

        Raises:
            ValueError: If no parser with the given name is available
        """
        if not callable(parser):
            # A name was given; try to resolve from attributes
            try:
                parser = getattr(self, "_parse_" + parser)
            except AttributeError as err:
                raise ValueError(
                    f"No parser named '{parser}' available in "
                    f"{self.__class__.__name__}!"
                ) from err

            log.debug("Resolved parser: %s", str(parser))

        # `parser` is now a callable.
        # May want to partially apply kwargs
        if parser_kwargs:
            log.debug("Binding `parser_kwargs` to parser method ...")
            parser = partial(parser, **parser_kwargs)

        return parser

    def _resolve_writers(self, write_to) -> Dict[str, Callable]:
        """Resolves the given argument to a list of callable writer functions.

        Args:
            write_to: a specification of the writers to use. Allows many
                different ways of specifying the writer functions, depending
                on the type of the argument:

                    - str: the name of the writer method of this reporter
                    - Callable: the writer function to use
                    - sequence of str and/or Callable: the names and/or
                      functions to use
                    - Dict[str, dict]: the names of the writer functions and
                      additional keyword arguments.

                If the type is wrong, will raise.

        Returns:
            Dict[str, Callable]: the writers (key: name, value: writer method)

        Raises:
            TypeError: Invalid ``write_to`` argument
            ValueError: A writer with that name was already added or a writer
                with the given name is not available.
        """

        def get_callable_name(c) -> str:
            """Returns the name of the callable by inspecting attributes"""
            if hasattr(c, "__name__"):
                return c.__name__
            # Does not have that attribute, e.g. because it is a partial func
            return str(c)

        # The target dict of callables
        writers = {}

        # First, need to bring the argument into a uniform structure.
        # This requires checking the many possible input formats.

        # -- Single callable: can directly return
        if callable(write_to):
            return {get_callable_name(write_to): write_to}

        # -- Single string: bring it into dict format
        elif isinstance(write_to, str):
            write_to = {write_to: {}}

        # -- list: move the callables to the writers dict; string items remain.
        elif isinstance(write_to, (list, tuple)):
            wt = {}
            for item in write_to:
                if callable(item):
                    # Check if already present
                    if item in writers.values():
                        raise ValueError(
                            "Given writer callable with name "
                            f"'{get_callable_name(item)}' was already added!"
                        )
                    writers[get_callable_name(item)] = item

                elif isinstance(item, str):
                    # Add an empty entry to the new write_to dict
                    wt[item] = dict()

                else:
                    raise TypeError(
                        f"One item of given `write_to` argument {write_to} "
                        f"of type {type(write_to)} was neither a string nor a "
                        "callable!"
                    )

            # Use the new write_to dict
            write_to = wt

        # Ensure that the format is a dict now
        if not isinstance(write_to, dict):
            raise TypeError(
                f"Invalid type {type(write_to)} for argument `write_to`!"
            )

        # Now populate the writers dict with the remaining str-specified funcs
        for writer_name, params in write_to.items():
            try:
                writer = getattr(self, "_write_to_" + writer_name)

            except AttributeError as err:
                raise ValueError(
                    "No writer named '{}' available in {}!"
                    "".format(writer_name, self.__class__.__name__)
                ) from err

            # If given, partially apply the params
            if params:
                writer = partial(writer, **params)

            # Store in dict of writers
            writers[writer_name] = writer
            log.debug("Added writer with name '%s'.", writer_name)

        return writers

    # Parser methods ..........................................................

    # None available in the base class

    # Writer methods ..........................................................

    def _write_to_stdout(self, s: str, *, flush: bool = True, **print_kws):
        """Writes the given string to stdout using the print function.

        Args:
            s (str): The string to write
            flush (bool, optional): Whether to flush directly; default: True
            **print_kws: Other print function keyword arguments
        """
        if self.suppress_cr and print_kws.get("end") == "\r":
            # Enforce line feed
            print_kws["end"] = "\n"

        print(s, flush=flush, **print_kws)

    def _write_to_stdout_noreturn(self, s: str, *, prepend="  "):
        """Writes to stdout without ending the line. Always flushes.

        Args:
            s (str): The string to write
            prepend (str, optional): Is prepended to the string; useful because
                the cursor might block this point of the terminal
            report_no (int, optional): accepted from ReportFormat call
        """
        if not self.suppress_cr:
            print(prepend + s, flush=True, end="\r")
        else:
            print(prepend + s, flush=True, end="\n")

    def _write_to_log(
        self, s: str, *, lvl: int = 10, skip_if_empty: bool = False
    ):
        """Writes the given string via the logging module.

        Args:
            s (str): The string to log
            lvl (int, optional): The level at which to log at; default is 10,
                corresponding to the ``DEBUG`` level
            skip_if_empty (bool, optional): Whether to skip writing if ``s`` is
                empty.
        """
        if not s and skip_if_empty:
            return
        log.log(lvl, s)

    def _write_to_file(
        self,
        s: str,
        *,
        path: str = "_report.txt",
        mode: str = "w",
        skip_if_empty: bool = False,
    ):
        """Writes the given string to a file

        Args:
            s (str): The string to write
            path (str, optional): The path to write it to; will be assumed
                relative to the ``report_dir`` attribute; if that is not
                given, ``path`` needs to be absolute. By default, assumes that
                there is a ``report_dir`` given.
            mode (str, optional): Writing mode of that file
            skip_if_empty (bool, optional): Whether to skip writing if ``s`` is
                empty.

        Raises:
            ValueError: If ``report_dir`` was not set and ``path`` is relative.
        """
        if not s and skip_if_empty:
            log.debug("Not writing to file because the given string is empty.")
            return

        # For given relative paths, join them to the report directory
        if not os.path.isabs(path):
            if not self.report_dir:
                raise ValueError(
                    "Need either an absolute `path` argument or initialize "
                    f"the {self.__class__.__name__} with the `report_dir` "
                    "argument such that `path` can be "
                    "interpreted relative to that directory."
                )

            path = os.path.join(self.report_dir, path)

        log.debug("Writing given string (length %d) to %s ...", len(s), path)
        with open(path, mode) as file:
            file.write(s)

        log.debug("Finished writing.")


# -----------------------------------------------------------------------------


class WorkerManagerReporter(Reporter):
    """This class specializes the base :py:class:`~utopya.reporter.Reporter`
    to report on the :py:class:`~utopya.workermanager.WorkerManager` state and
    its progress.
    """

    TTY_MARGIN = 4
    """Margin to use when writing to terminal"""

    PROGRESS_BAR_SYMBOLS = dict(
        success="▓", active_progress="▒", active="░", skipped="»", space=" "
    )
    """Symbols to use in progress bar parser"""

    LATEST_WM_REPORT_TO_STATUS: Dict[str, str] = dict(
        after_work="finished",
        after_cancel="cancelled",
        after_fail="failed",
    )
    """Maps WorkerManager report names to a worker status; used in determining
    the work status."""

    # .........................................................................

    def __init__(
        self,
        wm: "utopya.workermanager.WorkerManager",
        *,
        mv: "utopya.multiverse.Multiverse" = None,
        **reporter_kwargs,
    ):
        """Initialize the specialized reporter for the
        :py:class:`~utopya.workermanager.WorkerManager`.

        It is aware of the WorkerManager and may additionally have acces to the
        :py:class:`~utopya.multiverse.Multiverse` it is embedded in, which
        provides additional information to report parsers.

        Args:
            wm (utopya.workermanager.WorkerManager): The associated
                WorkerManager instance
            mv (utopya.multiverse.Multiverse, optional): The Multiverse this
                reporter is used in. If this is provided, it can be used in
                report parsers, e.g. to provide additional information on
                simulations.
            **reporter_kwargs: Passed on to parent method
        """
        super().__init__(**reporter_kwargs)

        # Make sure that formats 'while_working' and 'after_work' are available
        if "while_working" not in self.report_formats:
            log.debug(
                "No report format 'while_working' found; adding one "
                "because it is needed by the WorkerManager."
            )

            self.add_report_format(
                "while_working",
                parser="progress_bar",
                write_to="stdout_noreturn",
            )

        if "after_work" not in self.report_formats:
            log.debug(
                "No report format 'after_work' found; adding one "
                "because it is needed by the WorkerManager."
            )

            self.add_report_format(
                "after_work", parser="progress_bar", write_to="stdout_noreturn"
            )

        # Other attributes
        self.mv = mv

        self.runtimes: List[float] = []
        self.exit_codes = Counter()
        self.tasks_by_exit_codes: Dict[int, list] = defaultdict(list)

        self._eta_info = dict()

        # Store the WorkerManager and associate it with this reporter
        self._wm = wm
        self._latest_wm_report = None
        wm.reporter = self
        log.debug("Associated reporter with WorkerManager.")

        # Finally, gather host information
        self._host_info = dict(
            user=getpass.getuser(),
            host_name=platform.node(),
            host_name_short=platform.node().split(".")[0],
            cpu_count=os.cpu_count(),
            num_workers=self.wm.num_workers,
            memory=get_physical_memory_str(),
            architecture=platform.machine(),
            processor=platform.processor(),
            platform=platform.system(),
            release=platform.release(),
            pid=os.getpid(),
        )

        log.debug("WorkerManagerReporter initialised.")

    @property
    def wm(self) -> "utopya.workermanager.WorkerManager":
        """Returns the associated
        :py:class:`~utopya.workermanager.WorkerManager`
        """
        return self._wm

    # Properties that extract info from the WorkerManager .....................

    @property
    def task_counters(self) -> OrderedDict:
        """Returns a dict of task counters from the WorkerManager"""
        return self.wm.task_counters

    @property
    def wm_finished(self) -> bool:
        cntrs = self.task_counters
        return cntrs["finished"] == cntrs["total"]

    @property
    def wm_active_tasks_progress(self) -> np.ndarray:
        """Array of active tasks' progress"""
        return np.array([t.progress for t in self.wm.active_tasks])

    @property
    def wm_elapsed(self) -> Union[timedelta, None]:
        """Seconds elapsed since start of working or None if not yet started"""
        times = self.wm.times

        if times["start_working"] is None:
            # Not started yet
            return None

        elif times["end_working"] is None:
            # Currently working: measure against now
            return dt.now() - times["start_working"]

        # Finished working: measure against end of work
        return times["end_working"] - times["start_working"]

    @property
    def wm_times(self) -> dict:
        """Return the characteristics of WorkerManager times. Calls
        :py:meth:`~utopya.reporter.WorkerManagerReporter.get_progress_info`
        without any additional arguments.
        """
        return self.get_progress_info()

    # Methods working on data .................................................

    def register_task(self, task: "utopya.task.WorkerTask"):
        """Given the task object, extracts and stores some information like
        its run time or its exit code.
        Exit codes are aggregated over multiple registrations.

        This can be called from a callback function of a WorkerTask object in
        order to relay information to the reporter.

        Args:
            task (utopya.task.WorkerTask): The WorkerTask to extract
                information from.
        """
        if "run_time" in task.profiling:
            # The run time may be NaN (e.g. for skipped tasks)
            self.runtimes.append(task.profiling["run_time"])

        self.exit_codes[int(task.worker_status)] += 1
        self.tasks_by_exit_codes[int(task.worker_status)].append(task.name)

    def calc_runtime_statistics(self, min_num: int = 10) -> OrderedDict:
        """Calculates the current runtime statistics.

        Args:
            min_num (int, optional): Minimum number of runtimes that need to
                be registered for advanced statistics to actually be computed.
                If below this number, not all entries will exist.

        Returns:
            OrderedDict: The runtime statistics. If there are no runtimes yet,
                only the ``total (wall)`` entry will be there.
                If there are too few
        """
        d = OrderedDict()
        if self.wm_elapsed is not None:
            d["total (wall)"] = self.wm_elapsed.total_seconds()

        if not self.runtimes:
            return d

        # Throw out Nones and convert to np.array
        _rts = np.array([rt for rt in self.runtimes if rt is not None])
        rts = _rts[np.isfinite(_rts)]

        d["num_success"] = rts.size
        d["num_skipped"] = _rts.size - rts.size

        d["total (CPU)"] = np.sum(rts)
        if len(rts) < min_num:
            return d

        d["mean"] = np.mean(rts).item()
        d[" (last 50%)"] = np.mean(rts[-len(rts) // 2 :]).item()
        d[" (last 20%)"] = np.mean(rts[-len(rts) // 5 :]).item()
        d[" (last 5%)"] = np.mean(rts[-len(rts) // 20 :]).item()
        d["std"] = np.std(rts).item()
        d["min"] = np.min(rts).item()
        d["at 25%"] = np.percentile(rts, 25).item()
        d["median"] = np.median(rts).item()
        d["at 75%"] = np.percentile(rts, 75).item()
        d["max"] = np.max(rts).item()

        return d

    def get_progress_info(self, **eta_options) -> Dict[str, float]:
        """Compiles a dict containing progress information for the current
        work session.

        Args:
            **eta_options: Passed on to method calculating ``est_left``,
                :py:meth:`._compute_est_left`.

        Returns:
            Dict[str, float]: Progress information. Guaranteed to contain the
                keys ``start``, ``now``, ``elapsed``, ``est_left``,
                ``est_end``, and ``end``.
        """
        d = dict(
            start=self.wm.times["start_working"],
            now=dt.now(),
            elapsed=self.wm_elapsed,
            est_left=None,
            est_end=None,
            end=self.wm.times["end_working"],
        )

        # Add estimate time remaining and ETA, if the WorkerManager started.
        if d["start"] is not None:
            progress: dict = self._compute_progress()
            if progress["total"] > 0.0:
                d["est_left"] = self._compute_est_left(
                    progress=progress, elapsed=d["elapsed"], **eta_options
                )

        if d["est_left"] is not None:
            d["est_end"] = d["now"] + d["est_left"]

        return d

    def _compute_progress(
        self, counters: Dict[str, int] = None
    ) -> Dict[str, float]:
        """Given task counters, computes various progress measures, each values
        between 0 and 1."""
        progress = dict(
            skipped=0.0,
            active=0.0,
            total=0.0,
            worked_on=0.0,
            left_to_do=1.0,
            success=0.0,
            failed=0.0,
        )

        cntr = counters
        if cntr is None:
            cntr = self.task_counters

        if cntr["total"] == 0:
            return progress

        # Compute active progress in units of total progress, i.e. in [0, 1]
        active_progress: np.ndarray = self.wm_active_tasks_progress
        if active_progress.size:
            active_progress = float(np.nansum(active_progress) / cntr["total"])
        else:
            active_progress = 0.0

        # The rest just depends on the counts
        progress["total"] = cntr["finished"] / cntr["total"] + active_progress
        progress["active"] = active_progress
        progress["skipped"] = cntr["skipped"] / cntr["total"]
        progress["success"] = cntr["success"] / cntr["total"]
        progress["failed"] = cntr["failed"] / cntr["total"]
        progress["worked_on"] = (
            cntr["worked_on"] / cntr["total"] + active_progress
        )
        progress["left_to_do"] = 1.0 - progress["total"]

        return progress

    def _compute_est_left(
        self,
        *,
        progress: Dict[str, float],
        elapsed: timedelta,
        mode: str = "from_start",
        progress_buffer_size: int = 60,
    ) -> Optional[timedelta]:
        """Computes the estimated time left until the end of the work session
        (ETA) using the current progress value and the elapsed time.
        Depending on ``mode``, additional information may be included in the
        calculation.

        .. note::

            When task skipping is enabled, ETA computation becomes more
            difficult.

        Args:
            progress (float): The current progress value, in (0, 1]
            elapsed (datetime.timedelta): The elapsed time since start
            mode (str, optional): By which mode to calculate the ETA. Available
                modes are:

                    - ``from_start``, where ETA is computed from the start of
                        work session.
                    - ``from_buffer``, where ETA is computed from a more
                        recent point during the work session. This uses a
                        buffer to keep track of recent progress and computes
                        the ETA against the oldest record (controlled by
                        argument ``progress_buffer_size``), giving more
                        accurate estimates for long-running work sessions.

            progress_buffer_size (int, optional): The size of the ring buffer
                used in  ``from_buffer`` mode.

        Returns:
            Optional[datetime.timedelta]: Estimate for how much time is left
                until the end of the work session. If it cannot be estimated
                yet, e.g. because no progress was made, will return None.
        """
        if mode is None or mode == "from_start":
            try:
                if progress["skipped"] == 0:
                    progress = progress["total"]
                    return ((1.0 - progress) / progress) * elapsed
                else:
                    rel_left = progress["left_to_do"] / progress["worked_on"]
                    return rel_left * elapsed

            except ZeroDivisionError:
                return None

        elif mode == "from_buffer":
            progress_total = progress["total"]
            if progress_total <= 0:
                return None

            # Get / set up the progress buffer: a circular buffer which holds
            # at most ``progress_buffer_size`` elements.
            # Each element is a (progress, elapsed) tuple.
            try:
                pbuf = self._eta_info["progress_buffer"]

            except KeyError:
                log.debug(
                    "Setting up progress buffer (maxlen: %d) ...",
                    progress_buffer_size,
                )
                pbuf = deque(
                    [(0.0, timedelta(0.0))], maxlen=progress_buffer_size
                )
                self._eta_info["progress_buffer"] = pbuf

            # Add new information to buffer
            pbuf.append((progress_total, elapsed))

            # Compute progress speed compared to first element of buffer
            _progress, _elapsed = pbuf[0]
            dp = progress_total - _progress

            if elapsed == _elapsed or dp <= 1.0e-16:
                # Buffer useless or too little progress made; use simpler mode
                return self._compute_est_left(
                    progress=progress, elapsed=elapsed, mode="from_start"
                )

            return ((1.0 - progress_total) / dp) * (elapsed - _elapsed)

        else:
            raise ValueError(
                f"Invalid ETA computation mode '{mode}'! "
                "Available modes: from_start, from_buffer"
            )

    # Parser methods ..........................................................

    # One-line parsers . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def _parse_task_counters(self, *, report_no: int = None) -> str:
        """Return a string that shows the task counters of the WorkerManager

        Args:
            report_no (int, optional): A counter variable passed by the
                :py:class:`~utopya.reporter.ReportFormat` call, indicating
                how often this parser was called so far.

        Returns:
            str: A str representation of the task counters of the WorkerManager
        """
        return ",  ".join([f"{k}: {v}" for k, v in self.task_counters.items()])

    def _parse_progress(self, *, report_no: int = None) -> str:
        """Returns a progress string

        Args:
            report_no (int, optional): A counter variable passed by the
                :py:class:`~utopya.reporter.ReportFormat` call, indicating
                how often this parser was called so far.

        Returns:
            str: A simple progress indicator
        """
        cntr = self.task_counters

        if cntr["total"] <= 0:
            return "(No tasks assigned to WorkerManager yet.)"

        return (
            "Finished  {fin:>{digs:}d} / {tot:d}  ({p:.1f}%, {s:d} skipped)"
        ).format(
            fin=cntr["finished"],
            tot=cntr["total"],
            digs=len(str(cntr["total"])),
            p=cntr["finished"] / cntr["total"] * 100,
            s=cntr["skipped"],
        )

    def _parse_progress_bar(
        self,
        *,
        num_cols: Union[str, int] = "fixed",
        fstr: str = "  ╠{:}╣ {info:}{times:}",
        info_fstr: str = "{prg[total]:>5.1f}% ",
        show_times: bool = False,
        times_fstr: str = "| {elapsed:} elapsed | ~{est_left:} left ",
        times_fstr_final: str = "| finished in {elapsed:} ",
        times_kwargs: dict = {},
        report_no: int = None,
    ) -> str:
        """Returns a progress bar.

        It shows the amount of finished tasks, active tasks, and a percentage.

        Args:
            num_cols (Union[str, int], optional): The number of columns
                available for creating the progress bar. Can also be a string
                ``adaptive`` to poll terminal size upon each call, or ``fixed``
                to use the number of columns determined at import time.
            fstr (str, optional): The format string for the final output.
                Should contain the ``pbar`` string, which makes up the
                progress bar, and can optionally contain the``info`` and
                ``times`` segments, formatted using the respective format
                string arguments.
            info_fstr (str, optional): The format string for the ``info``
                section of the final output. Available keys:

                    - ``prg``, dict with various progress measures in percent:
                      ``total``, ``active``, ``skipped``, ``failed``,
                      ``success``, ...
                    - ``cnt``, the task counters dictionary, see:
                      :py:meth:`~utopya.reporter.WorkerManagerReporter.task_counters`

            show_times (bool, optional): Whether to show a short version of the
                results of the times parser
            times_fstr (str, optional): Format string for times information
            times_fstr_final (str, optional): Format string for times
                information once the work session has ended
            times_kwargs (dict, optional): Passed on to ``times`` parser.
                Only used if ``show_times`` is set.
            report_no (int, optional): A counter variable passed by the
                :py:class:`~utopya.reporter.ReportFormat` call, indicating
                how often this parser was called so far.

        Returns:
            str: The one-line progress bar
        """
        # Get the task counter and check that some tasks have been assigned
        cntr = self.task_counters

        if cntr["total"] <= 0:
            return "(No tasks assigned to WorkerManager yet.)"

        # Determine the format string for the times
        if show_times:
            if cntr["finished"] == cntr["total"]:
                times_fstr = times_fstr_final
            times_str = self._parse_times(fstr=times_fstr, **times_kwargs)

        else:
            times_str = ""

        # Determine number of available columns
        if num_cols == "adaptive":
            num_cols = (
                _get_terminal_size((TTY_COLS, 20)).columns - self.TTY_MARGIN
            )

        elif num_cols == "fixed":
            num_cols = TTY_COLS - self.TTY_MARGIN

        # Get the active tasks' mean progress and calculate the total progress
        progress = self._compute_progress(cntr)

        # Get the information string ready
        progress_percent = {k: v * 100 for k, v in progress.items()}
        info_str = info_fstr.format(cnt=cntr, prg=progress_percent)

        # Determine how much room is available for the progress bar
        pb_width = num_cols - len(
            fstr.format("", info=info_str, times=times_str)
        )

        # Only return percentage indicator if the width would be _very_ short
        if pb_width < 5:
            return " {:>5.1f}% ".format(cntr["finished"] / cntr["total"] * 100)

        # Calculate the ticks
        ticks = dict()
        factor = pb_width / cntr["total"]  # == symbols per task

        # For successful and skipped tasks, simply round
        ticks["success"] = round(cntr["success"] * factor)
        ticks["skipped"] = round(cntr["skipped"] * factor)

        # Calculate the active ticks and those in progress
        # NOTE Important to round only one of the two, leads to artifacts
        #      otherwise
        ticks["active_progress"] = int(
            progress["active"] * cntr["total"] * factor
        )
        ticks["active"] = (
            round(cntr["active"] * factor) - ticks["active_progress"]
        )

        # Calculate spaces from the sum of all of the above
        ticks["space"] = pb_width - sum(ticks.values())
        # TODO Make sure that this is >= 0, otherwise there was a rounding
        #      error somewhere above ...

        # Have all info now, let's go format!
        syms = self.PROGRESS_BAR_SYMBOLS
        pbar = "".join(
            [
                syms["skipped"] * ticks["skipped"],
                syms["success"] * ticks["success"],
                syms["active_progress"] * ticks["active_progress"],
                syms["active"] * ticks["active"],
                syms["space"] * ticks["space"],
            ]
        )

        return fstr.format(pbar, info=info_str, times=times_str)

    def _parse_times(
        self,
        *,
        fstr: str = (
            "Elapsed:  {elapsed:<8s}  "
            "|  Est. left:  {est_left:<8s}  "
            "|  Est. end:  {est_end:<10s}"
        ),
        timefstr_short: str = "%H:%M:%S",
        timefstr_full: str = "%d.%m., %H:%M:%S",
        use_relative: bool = True,
        times: dict = None,
        report_no: int = None,
        **progress_info_kwargs,
    ) -> str:
        """Parses the WorkerManager's time information, including estimated
        time left or others.

        Args:
            fstr (str, optional): The main format string; gets as keys the
                results of the WorkerManager time information.
                Available keys: ``elapsed``, ``est_left``, ``est_end``,
                ``start``, ``now``, ``end``.
            timefstr_short (str, optional): A time format string for absolute
                dates; short version.
            timefstr_full (str, optional): A time format string for absolute
                dates; long (ideally: full) version.
            use_relative (bool, optional): Whether for a date difference of 1
                to use relative dates, e.g. ``Today, 13:37``.
            times (dict, optional): A dict of times to use; this is mainly
                for testing purposes!
            report_no (int, optional): The report number passed by ReportFormat
            **progress_info_kwargs: Passed on to method calculating progress
                :py:meth:`~utopya.reporter.WorkerManagerReporter.get_progress_info`

        Returns:
            str: A string representation of the time information
        """
        # If no explicit times were given, calculate them now
        if times is None:
            times = self.get_progress_info(**progress_info_kwargs)

        # The dict of strings that is filled and passed to the fstr
        tstrs = dict()

        # Convert some values to duration strings
        if times["elapsed"]:
            tstrs["elapsed"] = format_time(times["elapsed"])
        else:
            tstrs["elapsed"] = "(not started)"

        if times["est_left"]:
            tstrs["est_left"] = format_time(times["est_left"], max_num_parts=2)
        else:
            # No est_left available
            # Distinguish between finished and not started simulaltions
            if self.wm_finished:
                tstrs["est_left"] = "(finished)"
            else:
                tstrs["est_left"] = "∞"

        # Check if the start and end times are given
        if not (times["start"] and times["est_end"]):
            # Not given -> not started yet
            tstrs["start"] = "(not started)"
            tstrs["now"] = times["now"].strftime(timefstr_full)
            tstrs["est_end"] = "(unknown)"
            tstrs["end"] = "(unknown)"

        else:
            # Were given.
            # Decide which time format string to use, depending on whether
            # start and end are on the same day, and whether to put a manual
            # prefix in front
            prefixes = dict()

            # Calculate timedelta in days
            delta_days = (times["est_end"].date() - times["start"].date()).days

            if delta_days == 0:
                # All on the same day -> use short format, no prefixes
                timefstr = timefstr_abs = timefstr_short

            elif delta_days == 1 and use_relative:
                # Use short format with prefixes
                timefstr = timefstr_short
                timefstr_abs = timefstr_full

                if times["now"].date() == times["start"].date():
                    # Same day as start -> end is tomorrow
                    prefixes["start"] = "Today, "
                    prefixes["est_end"] = "Tomorrow, "
                else:
                    # Same day as est end -> start was yesterday
                    prefixes["start"] = "Yesterday, "
                    prefixes["est_end"] = "Today, "

            else:
                # Full format
                timefstr = timefstr_abs = timefstr_full

            # Create the strings
            tstrs["start"] = times["start"].strftime(timefstr)
            tstrs["now"] = times["now"].strftime(timefstr_abs)
            tstrs["est_end"] = times["est_end"].strftime(timefstr)

            if times["end"]:
                tstrs["end"] = times["end"].strftime(timefstr_abs)
            else:
                tstrs["end"] = "(unknown)"

            # Add prefixes
            for key, prefix in prefixes.items():
                tstrs[key] = prefix + tstrs[key]

        return fstr.format(**tstrs)

    # Multi-line parsers . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def _parse_runtime_stats(
        self,
        *,
        fstr: str = "  {k:<13s} {v:}",
        join_char="\n",
        ms_precision: int = 1,
        report_no: int = None,
    ) -> str:
        """Parses the runtime statistics dict into a multiline string

        Args:
            fstr (str, optional): The format string to use. Gets passed the
                keys ``k`` and ``v`` where ``k`` is the name of the entry and
                ``v`` its value. Note that ``v`` is a non-numeric value.
            join_char (str, optional): The join character / string to join the
                elements together.
            ms_precision (int, optional): Number of digits to represent the
                milliseconds part of the runtimes.
            report_no (int, optional): A counter variable passed by the
                :py:class:`~utopya.reporter.ReportFormat` call, indicating
                how often this parser was called so far.

        Returns:
            str: The multi-line runtime statistics
        """
        rtstats = self.calc_runtime_statistics()

        parts = [
            fstr.format(k=k, v=format_time(v, ms_precision=ms_precision))
            for k, v in rtstats.items()
        ]

        return join_char.join(parts)

    def _parse_distributed_work_status(
        self,
        *,
        fstr: str = _DEFAULT_distributed_status_fstr,
        distributed_work_status: dict = None,
        include_header: bool = True,
        report_no: int = None,
    ) -> str:
        """Loads the work status of this *and* the distributed workers and
        creates a status string from it."""
        from .multiverse import get_distributed_work_status

        if self.mv is None:
            return (
                "No Multiverse associated; "
                "cannot determine distributed work status."
            )

        dws = distributed_work_status
        if dws is None:
            dws = get_distributed_work_status(self.mv.dirs["run"])

        if len(dws) <= 1:
            return ""

        parts = list()

        if include_header:
            parts += ["Distributed Multiverses"]
            parts += ["-----------------------"]
            parts += [""]
            parts += [
                f"Detected {len(dws)} Multiverses working together "
                "on this run.\nTheir name and status is shown below.\n"
                "Note that this information may be delayed or outdated."
            ]
            parts += [""]

        for status in dws.values():
            if not status:
                parts.append("  [Multiverse with currently unknown status]")
                continue

            tags = list(status["run_tags"])
            if (
                status["pid"] == self._host_info["pid"]
                and status["host_name"] == self._host_info["host_name"]
            ):
                tags.append("this report")

            parts.append(fstr.format(**status, tags=", ".join(tags)))

        return "\n".join(parts)

    def _parse_report(
        self,
        *,
        fstr: str = "  {k:<{w:}s}  {v:}",
        min_num: int = 2,
        report_no: int = None,
        show_host_info: bool = True,
        show_exit_codes: bool = True,
        show_distributed_run_info: bool = True,
        distributed_status_fstr: str = _DEFAULT_distributed_status_fstr,
        show_individual_runtimes: bool = True,
        max_num_to_show: int = 2048,
        task_label_singular: str = "task",
        task_label_plural: str = "tasks",
    ) -> str:
        """Parses a report for all tasks that were being worked on into a
        multiline string. The headings can be adjusted by keyword arguments.

        Args:
            fstr (str, optional): The format string to use. Gets passed the
                keys ``k`` and ``v`` where ``k`` is the name of the entry and
                ``v`` its value. Note that this format string is also used
                with ``v`` being a non-numeric value. Also, ``w`` can be used
                to have a key column of constant width.
            min_num (int, optional): The minimum number of universes needed to
                calculate extended runtime statistics.
            report_no (int, optional): A counter variable passed by the
                :py:class:`~utopya.reporter.ReportFormat` call, indicating
                how often this parser was called so far.
            show_host_info (bool, optional): Whether to show basic information
                about the host machine
            show_exit_codes (bool, optional): Whether to show a table of exit
                codes of the finished simulations
            show_distributed_run_info (bool, optional): Whether to look for work
                status report files and show their information.
            distributed_status_fstr (str, optional): How to represent the work
                status of joined runs. Available keys are those from the status
                file plus ``tags``, which is a comma-separated string with
                information on whether this was a joined run (or main run) and
                a marker which run belongs to this report file.
            show_individual_runtimes (bool, optional): Whether to report
                individual universe runtimes; default: True. This should be
                disabled if there are a huge number of universes.
            max_num_to_show (int, optional): Maximum number of tasks to list
                in the report
            task_label_singular (str, optional): The label to use in the report
                when referring to a single task.
            task_label_plural (str, optional): The label to use in the report
                when referring to multiple tasks.

        Returns:
            str: The multi-line simulation report string
        """
        from .task import SKIP_EXIT_CODE
        from .workermanager import STOPCOND_EXIT_CODES

        # .. Get data
        # Work duration information
        tfstr = "%d.%m.%Y, %H:%M:%S"

        t_start = self.wm.times["start_working"]
        if t_start is not None:
            t_now = dt.now()
            duration = t_now - t_start

        # Counters, progress, statistics, ...
        cnt = self.task_counters

        rtstats = self.calc_runtime_statistics(min_num=min_num)
        num_success = rtstats.pop("num_success", 0)
        num_skipped = rtstats.pop("num_skipped", 0)

        run_finished = cnt["finished"] == cnt["total"]

        # .. Format data
        # List that contains the lines that will be written, joined later on
        parts = []

        # Let's have a pretty title :)
        parts += [
            r" __                       __             ",
            r"(_ . _    | _ |_. _  _   |__)_ _  _  _|_ ",
            r"__)|||||_||(_||_|(_)| )  | \(-|_)(_)| |_ ",
            r"==============================|==========",
            "",
        ]

        # Multiverse information
        if self.mv:
            run_dirname = os.path.basename(self.mv.dirs["run"])
            if "_" in run_dirname:
                _, run_note = run_dirname.split("_", 1)
            else:
                _ = run_dirname
                run_note = ""

            parts += [f"From:    {type(self.mv).__name__}"]
            if run_note:
                run_note = run_note.replace("_", " ").replace("-", " ")
                parts += [f"Note:    {run_note}"]
            parts += [f"Tags:    {', '.join(self.mv._run_tags)}"]
            parts += [""]

        # Runtime information and indication if run finished
        if t_start is not None:
            parts += [f"{'Start:':6s}   {t_start.strftime(tfstr)}"]
            parts += [
                f"{'End:' if run_finished else 'Now:':6s}   "
                f"{t_now.strftime(tfstr)}  (Δ: {format_time(duration)})"
            ]
        else:
            parts += ["Work has not begun yet."]

        parts += [""]

        # Host information
        if show_host_info:
            parts += ["Host Information"]
            parts += ["----------------"]
            parts += [""]
            parts += [
                fstr.format(k=k.replace("_", " ").title(), v=v, w=12)
                for k, v in self._host_info.items()
                if k not in ("host_name_short", "pid")
            ]
            parts += [""]
            parts += [""]

        # Short: overall progress
        parts += ["Current Progress"]
        parts += ["----------------"]
        parts += [""]

        _c_tot = cnt["total"]
        if _c_tot:
            _w = len(str(_c_tot))
            parts += [
                fstr.format(
                    k="Finished",
                    v=(
                        f"{cnt['finished']:>{_w}d} / {_c_tot}  "
                        f"({cnt['finished']/_c_tot*100:.3g}%)"
                    ),
                    w=12,
                )
            ]
            parts += [
                fstr.format(
                    k=k.title(),
                    v=f"{v:>{_w}d}{' '*(_w + 3)}  ({v/_c_tot*100:.3g}%)",
                    w=12,
                )
                for k, v in cnt.items()
                if k in ("success", "skipped", "stopped", "failed")
            ]
        else:
            parts += ["No {} defined.".format(task_label_plural)]

        parts += [""]
        parts += [""]

        # Calculate and display runtime statistics
        parts += ["Runtime Statistics"]
        parts += ["------------------"]
        parts += [""]
        parts += [
            "  # {}:  {} / {}{}".format(
                task_label_plural,
                num_success,
                len(self.wm.tasks),
                f"  ({num_skipped} skipped)" if num_skipped else "",
            )
        ]

        parts += [""]
        parts += [
            fstr.format(k=k, v=format_time(v, ms_precision=1), w=12)
            for k, v in rtstats.items()
        ]

        parts += [""]
        parts += [""]

        # Check other parts of a potentially distributed run
        if show_distributed_run_info:
            dws_info = self._parse_distributed_work_status(
                fstr=distributed_status_fstr, include_header=True
            )
            if dws_info:
                parts += [dws_info, "", ""]

        # In cluster mode, add more information
        if self.wm.cluster_mode:
            _rcps = self.wm.resolved_cluster_params

            parts += ["Cluster Mode Information"]
            parts += ["------------------------"]
            parts += [""]
            parts += [
                fstr.format(k=k.replace("_", " "), v=_rcps[k], w=12)
                for k in (
                    "node_name",
                    "node_index",
                    "num_nodes",
                    "node_list",
                    "job_id",
                    "job_name",
                    "job_account",
                    "cluster_name",
                    "num_procs",
                )
                if _rcps.get(k) is not None
            ]
            parts += [""]
            parts += [""]

        # Exit Codes
        if show_exit_codes:
            parts += ["Exit Codes"]
            parts += ["----------"]

            tasks_by_exit_codes = copy.deepcopy(self.tasks_by_exit_codes)
            n_tasks_exited = sum(len(t) for t in tasks_by_exit_codes.values())
            n_tasks_total = len(self.wm.tasks)
            n_tasks_left = n_tasks_total - n_tasks_exited
            _w = max(
                [1] + [len(str(len(t))) for t in tasks_by_exit_codes.values()]
            )
            task_label = (
                task_label_singular
                if n_tasks_exited == 1
                else task_label_plural
            )

            # Successful
            n_success = len(tasks_by_exit_codes.get(0, []))
            parts += [""]
            parts += [
                fstr.format(
                    k="success",
                    v=(
                        f"{n_success:>{_w}d} / {n_tasks_exited} finished "
                        f"{task_label}"
                        + (f",  {n_tasks_left} left" if n_tasks_left else "")
                    ),
                    w=12,
                )
            ]

            # Skipped
            n_skipped = len(tasks_by_exit_codes.get(SKIP_EXIT_CODE, []))
            if n_skipped:
                parts += [""]
                parts += [
                    fstr.format(
                        k="skipped",
                        v=(
                            f"{n_skipped:>{_w}d} / {n_tasks_exited} finished "
                            f"{task_label}  "
                            f"({n_skipped/n_tasks_exited*100:.3g}%)"
                        ),
                        w=12,
                    )
                ]

            # Others (stop conditions and errors)
            for exit_code, task_names in sorted(tasks_by_exit_codes.items()):
                if exit_code in (0, SKIP_EXIT_CODE):
                    continue

                parts += [""]
                _n = len(task_names)
                _desc = (
                    "stopped" if exit_code in STOPCOND_EXIT_CODES else "failed"
                )

                # else: failed or stopped
                parts += [
                    fstr.format(
                        k=f"code {exit_code:d}",
                        v=f"{_n:>{_w}d} / {n_tasks_exited} {_desc}",
                        w=12,
                    )
                ]
                if len(task_names) <= max_num_to_show:
                    parts += [
                        fstr.format(
                            k="",
                            v=", ".join(task_names),
                            w=12,
                        )
                    ]

            parts += [""]
            parts += [""]

        # If stop conditions were fulfilled, inform about those
        if self.wm.stop_conditions:

            def task_names(sc: set) -> str:
                if not sc.fulfilled_for:
                    return "(None)"
                return ", ".join(sorted(t.name for t in sc.fulfilled_for))

            total_stopped = sum(
                len(sc.fulfilled_for) for sc in self.wm.stop_conditions
            )

            parts += ["Stop Conditions"]
            parts += ["---------------"]
            parts += [""]
            parts += [
                f"  {total_stopped} / {len(self.wm.tasks)} "
                f"{task_label_plural} were stopped due to at least one "
                "of the following stop conditions:"
            ]
            parts += [""]
            parts += [
                f"  {sc}\n" f"      {task_names(sc)}\n"
                for sc in self.wm.stop_conditions
            ]
            parts += [""]
            parts += [""]

        # Add individual universe run times, up to a limit
        if show_individual_runtimes and len(self.wm.tasks) <= max_num_to_show:
            parts += [f"{task_label_singular.capitalize()} Runtimes"]
            parts += ["-" * len(parts[-1])]
            parts += [""]

            max_name_len = max([12] + [len(t.name) for t in self.wm.tasks])

            for task in self.wm.tasks:
                if "run_time" in task.profiling:
                    rt = task.profiling["run_time"]
                    if task.was_skipped:
                        info = "--  skipped"
                    else:
                        # There should be a formattable runtime
                        info = format_time(rt, ms_precision=1)

                        if task.worker_status in STOPCOND_EXIT_CODES:
                            info += "  --  stopped"

                        elif task.worker_status not in (None, 0, "0"):
                            info += f"  --  error code:  {task.worker_status}"

                    parts += [
                        fstr.format(
                            k=task.name,
                            v=info,
                            w=max_name_len,
                        )
                    ]

        return " \n".join(parts)

    def _parse_pspace_info(
        self,
        *,
        fstr: str = "{sweep_info:}",
        min_tasks_added: int = 0,
        report_no: int = None,
    ) -> str:
        """Provides information about the parameter space.

        Extracts the ``parameter_space`` from the associated Multiverse's meta
        configuration and provides information on that.

        If there are multiple tasks specified, it is assumed that a sweep is or
        was being carried out and an information string is retrieved from the
        :py:class:`paramspace.paramspace.ParamSpace` object, which is then
        returned.
        If only a single task was defined, returns an empty string.

        Args:
            fstr (str, optional): The format string the sweep info should be
                embedded into. Needs to contain ``sweep_info`` key.
            min_tasks_added (int, optional): Number of tasks that need to have
                been added in order for showing the parameter space info.
                If zero, will always return the pspace info, this can be useful
                if invoking this before the WorkerManager got *any* tasks!
            report_no (int, optional): A counter variable passed by the
                :py:class:`~utopya.reporter.ReportFormat` call, indicating
                how often this parser was called so far.

        Returns:
            str: If there is more than one task, returns the result of
                :py:meth:`paramspace.paramspace.ParamSpace.get_info_str`.
                If not, returns a string denoting that there was only one task.
        """
        if self.mv is None:
            raise ValueError(
                "No Multiverse associated with this reporter! "
                "Cannot parse ParamSpace information."
            )

        if len(self.wm.tasks) < min_tasks_added:
            return ""

        pspace = self.mv.meta_cfg["parameter_space"]

        try:
            return fstr.format(sweep_info=pspace.get_info_str())
        except (AttributeError, TypeError) as exc:
            raise TypeError(
                f"Expected a ParamSpace object, got:\n\n{pspace}"
            ) from exc

    def _parse_work_status(self, *, report_no: int = None) -> str:
        """Supplies a very simple, YAML-formatted status string for *this*
        WorkerManager run."""
        cntr = self.task_counters

        if self._latest_wm_report:
            wm_status = self.LATEST_WM_REPORT_TO_STATUS.get(
                self._latest_wm_report, "working"
            )
        else:
            wm_status = "unknown"

        progress = self._compute_progress(cntr)
        status = dict(
            status=wm_status,
            time=dt.now().isoformat(),
            counters=dict(cntr),
            progress=progress,
            progress_here=f"{progress['worked_on']*100:.3g}%",
            host_name=self._host_info["host_name"],
            host_name_short=self._host_info["host_name_short"],
            pid=self._host_info["pid"],
            run_tags=self.mv._run_tags if self.mv else [],
        )

        try:
            return _yaml_dumps(status)
        except Exception:
            print(status)
            print(repr(status))
            raise

    # Writer methods ..........................................................

    def _write_to_file(
        self,
        *args,
        path: str = "_report.txt",
        cluster_mode_path: str = "{}_{node_name}{ext}",
        dmv_mode_path: str = "{}__{host_name_short}-{pid}{ext}",
        skip_if_dmv: bool = False,
        **kwargs,
    ):
        """Overloads the parent method with capabilities needed in cluster mode

        All args and kwargs are passed through. If in cluster mode, the path
        is changed such that it includes the name of the node.

        Args:
            *args: Passed on to parent method
            path (str, optional): The path to save to
            cluster_mode_path (str, optional): The format string to use for the
                path in cluster mode. *Requires* to contain the format key
                ``{0:}`` which retains the given ``path``, extension split off.
                Extension can be used via ``ext`` (already includes the dot).
                Additional format keys: ``node_name``, ``job_id``.
            dmv_mode_path (str, optional): The format string to use for the
                path in a distributed Multiverse run.
            skip_if_dmv (bool, optional): Whether to skip reporting if part
                of a joined or continued run, i.e.: originating from a
                :py:class:`~utopya.multiverse.DistributedMultiverse` run.
            **kwargs: Passed on to parent method
        """
        from .multiverse import DistributedMultiverse

        is_dmv_run = self.mv and isinstance(self.mv, DistributedMultiverse)
        if skip_if_dmv and is_dmv_run:
            return

        always_format_path = "{" in path and "}" in path
        if not (self.wm.cluster_mode or is_dmv_run or always_format_path):
            return super()._write_to_file(*args, path=path, **kwargs)

        # else: need to create a new path and/or parse additional information
        #       into the format string
        base_path, ext = os.path.splitext(path)
        fstr_kwargs = dict(ext=ext, **self._host_info)

        if self.wm.cluster_mode:
            rcp = self.wm.resolved_cluster_params
            fstr_kwargs.update(rcp)
            fstr = cluster_mode_path

        elif dmv_mode_path:
            fstr_kwargs["run_tags"] = ", ".join(self.mv._run_tags)
            fstr = dmv_mode_path

        else:
            fstr = "{}{ext}"

        # Apply formatting to the base path, then combine them
        base_path = base_path.format(**fstr_kwargs)
        path = fstr.format(base_path, **fstr_kwargs)

        # Let the parent do the rest ...
        return super()._write_to_file(*args, path=path, **kwargs)
