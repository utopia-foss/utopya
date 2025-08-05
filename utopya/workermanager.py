"""The :py:class:`.WorkerManager` is a central part of utopya in that it
spawns and controls the tasks (:py:class:`~utopya.task.WorkerTask`) that are
to be worked on.
"""

import copy
import logging
import os
import queue
import random
import sys
import time
import warnings
from datetime import datetime as dt
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from .exceptions import *
from .reporter import WorkerManagerReporter
from .stop_conditions import SIG_STOPCOND, StopCondition
from .task import SIGMAP, SKIP_EXIT_CODE, TaskList, WorkerTask
from .tools import format_time

log = logging.getLogger(__name__)

STOPCOND_EXIT_CODES: Sequence[int] = (
    -SIGMAP[SIG_STOPCOND],
    SIGMAP[SIG_STOPCOND],
    128 + abs(SIGMAP[SIG_STOPCOND]),
)
"""Exit codes of a :py:class:`~utopya.task.WorkerTask` that will be interpreted
as stemming from a stop condition. This depends on the signal used for stop
conditions (:py:data:`utopya.stop_conditions.SIG_STOPCOND`).
This sequence of possible exit codes takes into account that the sign may be
switched (depending on whether a signed or unsigned integer convention is
used) or where a convention is used such that a *handled* signal is turned into
an exit code of ``128 + abs(signum)``."""

POLL_DELAY_WARNING_THRS: float = 0.001
"""Below this `poll_delay` time, will issue a warning."""

# -----------------------------------------------------------------------------


class WorkerManager:
    """The WorkerManager class orchestrates :py:class:`~utopya.task.WorkerTask`
    objects: setting them up, invoking them, tracking their progress, and
    starting new workers if previous workers finished.

    The WorkerManager also keeps track of the status of tasks (as far as can be
    done without assuming too much about the tasks themselves).
    It then categorizes the tasks accordingly, using the following groups:

        * ``invoked``: grabbed from the task queue, nothing else done yet
        * ``spawned``: setup function completed and process spawned
        * ``active``: currently assigned to workers and not finished yet
        * ``succeeded``: finished successfully (exit status 0)
        * ``stopped``: stopped via a deliberately sent signal from the
          'outside', e.g. a stop condition or a keyboard interrupt.
        * ``skipped``: skipped some time after invocation, e.g. as was
          determined by the setup function.
        * ``failed``: failed for some task-specific reason (exit code != 0)
        * ``finished``: union of success, stop, fail, and skip, i.e. all tasks
          that are no longer in the queue but also no longer active.
    """

    pending_exceptions: queue.Queue = None
    """A (FiFo) queue of :py:exc:`Exception` objects that will be handled by
    the :py:class:`.WorkerManager` during working. This is the interface that
    allows for other threads that have access to the WorkerManager to add an
    exception and let it be handled in the main thread.
    """

    rf_spec: dict = None
    """The report format specifications that are used throughout the
    WorkerManager. These are invoked at different points of the operation:

    - ``before_working``
    - ``while_working``
    - ``after_work``
    - ``after_cancel``
    - ``after_fail``
    - ``task_spawn``
    - ``task_finished``
    - ``task_skipped``
    - ``periodic``
    """

    times: dict = None
    """Holds profiling information"""

    def __init__(
        self,
        num_workers: Union[int, str] = "auto",
        poll_delay: float = 0.05,
        spawn_rate: int = -1,
        lines_per_poll: int = 50,
        periodic_task_callback: int = None,
        QueueCls: type = queue.Queue,
        reporter: WorkerManagerReporter = None,
        rf_spec: Dict[str, Union[str, List[str]]] = None,
        save_streams_on: Sequence[str] = (),
        nonzero_exit_handling: str = "ignore",
        interrupt_params: dict = None,
        cluster_mode: bool = False,
        resolved_cluster_params: dict = None,
    ):
        """Initialize the worker manager.

        Args:
            num_workers (Union[int, str], optional): The number of workers
                that can work in parallel. If 'auto' (default), uses
                os.cpu_count(). If below zero, deduces abs(num_workers) from
                the CPU count.
            poll_delay (float, optional): How long (in seconds) the delay
                between worker polls should be. For too small delays (<0.01),
                the CPU load will become significant.
            spawn_rate (int, optional): How many workers to spawn each working
                loop iteration. If -1, will assign new tasks to all free
                workers.
            lines_per_poll (int, optional): How many lines to read from
                each stream during polling of the tasks. This value should not
                be too large, otherwise the polling is delayed by too much.
                By setting it to -1, all available lines are read.
            periodic_task_callback (int, optional): If given, an additional
                task callback will be invoked after every
                ``periodic_task_callback`` poll events.
            QueueCls (type, optional): Which class to use for the queue.
                Defaults to the FiFo :py:class:`queue.Queue`.
            reporter (WorkerManagerReporter, optional): The reporter associated
                with this WorkerManager, reporting on the progress.
            rf_spec (Dict[str, Union[str, List[str]]], optional): The names of
                report formats that should be invoked at different points of
                the WorkerManager's operation.
                Possible keys are:

                    ``before_working``, ``while_working``,
                    ``after_work``, ``after_cancel``, ``after_fail``,
                    ``task_spawn``, ``task_finished``, ``task_skipped``.

                All other keys are silently ignored.

                The values of the dict can be either strings or lists of
                strings, where the strings always refer to report formats
                registered with the WorkerManagerReporter. This argument
                updates the default report format specifications.
            save_streams_on (Sequence[str], optional): On which events to
                invoke :py:meth:`~utopya.task.WorkerTask.save_streams`
                *during* work.
                Should be a sequence containing one or both of the keys
                ``on_monitor_update``, ``periodic_callback``.
            nonzero_exit_handling (str, optional): How to react if a WorkerTask
                exits with a non-zero exit code. For 'ignore', nothing happens.
                For 'warn', a warning is printed and the last 5 lines of the
                log are shown. For 'raise', the last 20 lines of the log is
                shown, all other tasks are terminated, and the WorkerManager
                exits with the same exit code as the WorkerTask exited with.
                Note that 'warn' will not lead to any messages if the worker
                died by SIGTERM, which presumable originated from a fulfilled
                stop condition. Use 'warn_all' to also receive warnings in
                this case.
            interrupt_params (dict, optional): Parameters that determine how
                the WorkerManager behaves when receiving KeyboardInterrupts
                during working.
                Possible keys:

                    ``send_signal``: Which signal to send to the workers. Can
                        be SIGINT (default), SIGTERM, SIGKILL, or any valid
                        signal as integer.
                    ``grace_period``: how long to wait for the other workers to
                        gracefully shut down. After this period (in seconds),
                        the workers will be killed via SIGKILL. Default is 5s.
                    ``exit``: whether to sys.exit at the end of start_working.
                        Default is True.

            cluster_mode (bool, optional): Whether similar tasks to those that
                are managed by this WorkerManager are, at the same time, worked
                on by other WorkerManager. This is relevant because the output
                of files might be affected by whether another WorkerManager
                instance is currently working on the same output directory.
                Also, in the future, this argument might be used to communicate
                between nodes.
            resolved_cluster_params (dict, optional): The corresponding cluster
                parameters.

        Raises:
            ValueError: For too negative ``num_workers`` argument
        """
        log.progress("Initializing WorkerManager ...")

        # Initialize attributes, some of which are property-managed
        self._num_workers = None
        self._poll_delay = None
        self._spawn_rate = None
        self._tasks = TaskList()
        self._task_q = QueueCls()
        self._active_tasks = []

        self._work_session_status: str = "not started"
        self._stop_conditions = set()
        self._reporter = None
        self._nonzero_exit_handling = None
        self._suppress_rf_specs = []
        self.pending_exceptions = queue.Queue()

        # Task lists that keep track of the tasks status *after* they were
        # worked on. There is some overlap between the task lists, for instance
        # the `finished_tasks` contains all tasks that were activated and
        # returned, regardless of their exit status or skipping
        self.invoked_tasks = TaskList()
        self.spawned_tasks = TaskList()
        self.finished_tasks = TaskList()  # success, stop, fail, skipped
        self.succeeded_tasks = TaskList()
        self.stopped_tasks = TaskList()
        self.skipped_tasks = TaskList()
        self.failed_tasks = TaskList()

        # Hand over arguments
        self.poll_delay = poll_delay
        self.spawn_rate = spawn_rate
        self.save_streams_on = save_streams_on
        self.lines_per_poll = lines_per_poll
        self.nonzero_exit_handling = nonzero_exit_handling
        self.interrupt_params = interrupt_params if interrupt_params else {}
        self.num_workers = num_workers

        self._periodic_callback = periodic_task_callback
        self._cluster_mode = cluster_mode
        self._resolved_cluster_params = resolved_cluster_params

        # Reporter-related, setting default rf_spec
        if reporter:
            self.reporter = reporter

        self.rf_spec = dict(
            before_working="while_working",
            while_working="while_working",
            task_invoked="while_working",
            task_spawned="while_working",
            task_finished="while_working",
            task_skipped="while_working",
            after_work="after_work",
            after_cancel="after_work",
            after_fail="after_work",
        )
        if rf_spec:
            self.rf_spec.update(rf_spec)

        # Provide some information
        log.note("  Number of available CPUs:  %d", os.cpu_count())
        log.note("  Number of workers:         %d", self.num_workers)
        log.note("  Non-zero exit handling:    %s", self.nonzero_exit_handling)

        # Store some profiling information
        self.times = dict(
            init=dt.now(), start_working=None, timeout=None, end_working=None
        )
        # These are also accessed by the reporter

        log.progress("Initialized WorkerManager.")

    # Properties ..............................................................
    @property
    def tasks(self) -> TaskList:
        """The list of all tasks."""
        return self._tasks

    @property
    def task_queue(self) -> queue.Queue:
        """The task queue."""
        return self._task_q

    @property
    def task_count(self) -> int:
        """Returns the number of tasks that this manager *ever* took care of.
        Careful: This is NOT the current number of tasks in the queue!
        """
        return len(self.tasks)

    @property
    def task_counters(self) -> Dict[str, int]:
        """Returns a dict with task counter values"""
        cntrs = dict()
        cntrs["total"] = self.task_count
        cntrs["active"] = len(self.active_tasks)
        cntrs["finished"] = len(self.finished_tasks)
        cntrs["invoked"] = len(self.invoked_tasks)
        cntrs["spawned"] = len(self.spawned_tasks)
        cntrs["success"] = len(self.succeeded_tasks)
        cntrs["skipped"] = len(self.skipped_tasks)
        cntrs["stopped"] = len(self.stopped_tasks)
        cntrs["failed"] = len(self.failed_tasks)
        cntrs["worked_on"] = cntrs["finished"] - cntrs["skipped"]
        return cntrs

    @property
    def num_workers(self) -> int:
        """The number of workers that may work in parallel"""
        return self._num_workers

    @num_workers.setter
    def num_workers(self, val: Union[int, str]):
        """Set the number of workers that can work in parallel.

        Can use the string ``auto`` to use the CPU count for setting the number
        of workers. Additionally, negative integers will be summed with the
        number of available CPU cores.

        .. note::

            Will not allow to set values that are smaller than 1; any argument
            that would lead to such a value will be silently clipped to 1.
        """
        if val == "auto":
            self._num_workers = os.cpu_count()

        elif not isinstance(val, int):
            raise TypeError(
                "Expected integer or string 'auto' for setting `num_workers`, "
                f"but got {type(val).__name__} {repr(val)}!"
            )

        elif val < 0:
            self._num_workers = max(1, os.cpu_count() + val)

        else:
            self._num_workers = max(1, val)

        log.debug("Set number of workers to %d", self.num_workers)
        if self.num_workers > os.cpu_count():
            warnings.warn(
                f"Set WorkerManager to use more workers ({self.num_workers}) "
                f"than there are CPU cores ({os.cpu_count()}) on this machine",
                UserWarning,
            )

    @property
    def active_tasks(self) -> List[WorkerTask]:
        """The list of currently active tasks.

        Note that this information might not be up-to-date; a process might
        quit just after the list has been updated.
        """
        return self._active_tasks

    @property
    def num_finished_tasks(self) -> int:
        """The number of finished tasks. Incremented whenever a task leaves
        the active_tasks list, regardless of its exit status.
        """
        return len(self.finished_tasks)

    @property
    def num_free_workers(self) -> int:
        """Returns the number of free workers."""
        return self.num_workers - len(self.active_tasks)

    @property
    def poll_delay(self) -> float:
        """Returns the delay between two polls"""
        return self._poll_delay

    @poll_delay.setter
    def poll_delay(self, val) -> None:
        """Set the poll delay to any positive value. For low values, a warning
        will be emitted.
        """
        if val <= 0.0:
            raise ValueError(f"Poll delay needs to be positive, was {val}s!")
        elif val < POLL_DELAY_WARNING_THRS:
            warnings.warn(
                f"Setting a poll delay of {val}s < {POLL_DELAY_WARNING_THRS}s "
                "can lead to increased CPU load. If you experience issues "
                "with high main thread CPU time, consider choosing a longer "
                "delay time.",
                UserWarning,
            )
        self._poll_delay = val

    @property
    def spawn_rate(self) -> int:
        """Returns the spawn rate"""
        return self._spawn_rate

    @spawn_rate.setter
    def spawn_rate(self, val: int) -> None:
        """Set the spawn rate."""
        if not (val == -1 or val > 0) or not isinstance(val, int):
            raise ValueError(
                f"Spawn rate needs to be a positive integer or -1, was {val}!"
            )
        self._spawn_rate = val

    @property
    def stop_conditions(self) -> Set[StopCondition]:
        """All stop conditions that were ever passed to
        :py:meth:`~utopya.workermanager.WorkerManager.start_working` during the
        life time of this WorkerManager.
        """
        return self._stop_conditions

    @property
    def nonzero_exit_handling(self) -> str:
        """Behavior upon a worker exiting with a non-zero exit code.

        - with ``ignore``, nothing happens
        - with ``warn``, a warning is printed
        - with ``raise``, the log is shown and the WorkerManager exits
          with the same exit code as the corresponding
          :py:class:`~utopya.task.WorkerTask` exited with.
        """
        return self._nonzero_exit_handling

    @nonzero_exit_handling.setter
    def nonzero_exit_handling(self, val: str):
        """Set the ``nonzero_exit_handling`` attribute.

        Args:
            val (str): The value to set it to. Can be: ``ignore``, ``warn``,
                ``raise``.

        Raises:
            ValueError: For invalid value
        """
        allowed_vals = ("ignore", "warn", "warn_all", "raise")
        if val not in allowed_vals:
            raise ValueError(
                f"`nonzero_exit_handling` needs to be one of {allowed_vals}, "
                f"but was '{val}'."
            )

        self._nonzero_exit_handling = val

    @property
    def reporter(self) -> Union[WorkerManagerReporter, None]:
        """The associated :py:class:`~utopya.reporter.WorkerManagerReporter`
        or None, if no reporter is set.
        """
        return self._reporter

    @reporter.setter
    def reporter(self, reporter):
        """Set the Reporter object for this WorkerManager.

        This includes a check for the correct type and whether the reporter was
        already set.
        """
        if not isinstance(reporter, WorkerManagerReporter):
            raise TypeError(
                "Need a WorkerManagerReporter for reporting from "
                f"WorkerManager, got {type(reporter)}."
            )
        elif self.reporter:
            raise RuntimeError("Already set the reporter; cannot change it.")

        self._reporter = reporter

        log.debug("Set reporter of WorkerManager.")

    @property
    def cluster_mode(self) -> bool:
        """Returns whether the WorkerManager is in cluster mode"""
        return self._cluster_mode

    @property
    def resolved_cluster_params(self) -> dict:
        """Returns a copy of the cluster configuration with all parameters
        resolved (thus making some additional keys available on the top level).
        It is returned as a deep copy to avoid mutability issues.
        """
        return copy.deepcopy(self._resolved_cluster_params)

    # Public API ..............................................................

    def add_task(
        self, *, TaskCls: type = WorkerTask, **task_kwargs
    ) -> WorkerTask:
        """Adds a task to the WorkerManager.

        Args:
            TaskCls (type, optional): The WorkerTask-like type to use
            **task_kwargs: All arguments needed for WorkerTask initialization.
                See :py:class:`utopya.task.WorkerTask` for all valid arguments.

        Returns:
            WorkerTask: The created WorkerTask object
        """
        # Evaluate save_stream callbacks
        save_streams = lambda t: t.save_streams(final=False)

        if "monitor_updated" in self.save_streams_on:
            save_streams_on_monitor_update = True

        if "periodic_callback" in self.save_streams_on:
            periodic_callback = save_streams
        else:
            # Do nothing
            periodic_callback = lambda _: None

        # Define the function needed to calculate the task's progress
        def calc_progress(task) -> float:
            """Uses the task's stream objects to calculate the progress.

            If no stream objects are available, returns 0.
            """
            # Check if parsed objects were available
            if not task.outstream_objs:
                return 0.0

            # Extract the `progress` key from the latest entry; if it is not
            # available, use the same behaviour as above and return 0
            return task.outstream_objs[-1].get("progress", 0.0)

        # Prepare the callback functions needed by the reporter . . . . . . . .
        def task_invoked(task):
            """Performs action after a task was grabbed and before anything is
            done, specifically: before invoking the setup function which may
            lead to task skipping.
            """
            self.active_tasks.append(task)
            self.invoked_tasks.append(task)
            self._invoke_report("task_invoked", force=True)

        def task_spawned(task):
            """Performs action after a task was spawned, i.e. if it was not
            skipped.

            - checks if stream-forwarding was activated
            - invokes the 'task_spawned' report specification
            """
            self.spawned_tasks.append(task)

            # As the task might have been configured to forward streams, it
            # needs to be checked whether this would clash with the reporter's
            # output to stdout.
            # First, check if that was already taken care of
            if self.reporter and not self.reporter.suppress_cr:
                # Nope -> need to check if the task will forward streams
                if task.streams.get("out") and task.streams["out"]["forward"]:
                    # Yes -> need to suppress carriage returns by reporter and
                    # reduce report invokations by the WorkerManager main loop
                    self.reporter.suppress_cr = True
                    self._suppress_rf_specs.append("while_working")

            # Invoke the report
            self._invoke_report("task_spawned", force=True)

        def task_finished(task):
            """Performs actions after a task has finished, regardless of
            whether it finished successfully, failed or was stopped.

            - invokes the ``task_finished`` report specification
            - registers the task with the reporter, which extracts information
              on the run time of the task and its exit status
            - in debug mode, performs an action upon non-zero task exit status

            .. note::

                This is NOT invoked for *skipped* tasks.
            """
            self.active_tasks.remove(task)
            self.finished_tasks.append(task)

            if self.reporter is not None:
                self.reporter.register_task(task)

            # If there was a (non-zero) exit and the handling mode is set
            # accordingly, generate an exception and add it to the list of
            # pending exceptions. Handle exit codes that result from a stop
            # condition being fulfilled separately.
            if self.nonzero_exit_handling != "ignore" and task.worker_status:
                if task.worker_status in STOPCOND_EXIT_CODES:
                    # NOTE Not adding to self.stopped_tasks here because this
                    #      is done already in the main loop
                    exc = WorkerTaskStopConditionFulfilled(task)
                else:
                    exc = WorkerTaskNonZeroExit(task)
                self.pending_exceptions.put_nowait(exc)

            # Register whether the task succeeded or not.
            # Note that stopped tasks don't get into this callback and are
            # counted in the `task_skipped` callback instead.
            if task.worker_status == 0:
                self.succeeded_tasks.append(task)

            elif task.worker_status in STOPCOND_EXIT_CODES:
                pass
                # self.stopped_tasks.append(task) … is already called in the
                # main polling loop

            else:
                self.failed_tasks.append(task)

            self._invoke_report("task_finished", force=True)

        def task_skipped(task):
            """Performs actions after a task was skipped, i.e. if it did not
            spawn a process but it was decided *prior to spawning* that the
            task should not be worked on but skipped.
            """
            self.active_tasks.remove(task)
            self.finished_tasks.append(task)
            self.skipped_tasks.append(task)

            if self.reporter is not None:
                self.reporter.register_task(task)

            self._invoke_report("task_skipped")

        def monitor_updated(task):
            """Performs actions when there was a parsed object in the task's
            stream, i.e. when the monitor got an update.
            """
            if save_streams_on_monitor_update:
                save_streams(task)
            self._invoke_report("monitor_updated")

        # Prepare the arguments for the WorkerTask . . . . . . . . . . . . . .

        callbacks = dict(
            # Invoked by task itself
            invoked=task_invoked,
            spawned=task_spawned,
            finished=task_finished,
            skipped=task_skipped,
            parsed_object_in_stream=monitor_updated,
            #
            # Invoked by WorkerManager
            periodic=periodic_callback,
        )

        # Generate the WorkerTask-like object from the given parameters
        task = TaskCls(
            callbacks=callbacks, progress_func=calc_progress, **task_kwargs
        )

        # Append it to the task list and put it into the task queue
        self.tasks.append(task)
        self.task_queue.put_nowait(task)

        log.debug("Task %s (uid: %s) added.", task.name, task.uid)
        return task

    def start_working(
        self,
        *,
        shuffle_tasks: bool = False,
        timeout: Optional[float] = None,
        stop_conditions: Sequence[StopCondition] = None,
        post_poll_func: Callable = None,
    ) -> None:
        """Upon call, all enqueued tasks will be worked on sequentially.

        Args:
            detach (bool, optional): If False (default), the WorkerManager
                will block here, as it continuously polls the workers and
                distributes tasks.
            timeout (float, optional): If given, the number of seconds this
                work session is allowed to take. Workers will be canceled if
                the number is exceeded. Note that this is not measured in CPU
                time, but the host systems wall time.
                If zero, timeout occurs immediately.
                If None or negative, there will be no timeout.
            stop_conditions (Sequence[StopCondition], optional): During the
                run these StopCondition objects will be checked
            post_poll_func (Callable, optional): If given, this is called after
                all workers have been polled. It can be used to perform custom
                actions during a the polling loop.

        Raises:
            ValueError: For invalid (i.e., negative) timeout value
            WorkerManagerTotalTimeout: Upon a total timeout
        """
        self._invoke_report("before_working")

        log.progress("Preparing to work ...")
        self._work_session_status = "preparing"
        was_cancelled = False

        # Set some variables needed during the run
        poll_no = 0
        self.times["start_working"] = dt.now()

        # Prepare timeout and stop conditions
        timeout_time = self._parse_timeout_args(timeout=timeout)
        stop_conditions = self._parse_stop_conditions(stop_conditions)

        # Perhaps shuffle the tasks queue
        log.note("  Shuffled tasks:   %s", shuffle_tasks)
        if shuffle_tasks:
            random.shuffle(self._task_q.queue)

        # Start with the polling loop
        # Basically all working time will be spent in there ...
        log.hilight("Starting to work ...")
        self._work_session_status = "working"

        try:
            while self.active_tasks or self.task_queue.qsize() > 0:
                # Check total timeout; if raised, this is handled via except
                if timeout_time is not None and time.time() > timeout_time:
                    raise WorkerManagerTotalTimeout()

                # Check if there was another reason for exiting
                self._handle_pending_exceptions()

                # Assign tasks to free workers; this creates new processes and
                # will carry out their setup function (in the main thread).
                # Skipped tasks will be added to the active_tasks, but will
                # already invoke their callbacks.
                self._assign_tasks(self.num_free_workers)

                # Poll the workers.
                # This will also remove no longer active workers and trigger
                # their callback functions ...
                self._poll_workers()

                # Call the post-poll function
                if post_poll_func is not None:
                    post_poll_func()

                # Do stream-related actions for each task
                for task in self.active_tasks:
                    # Read the streams and forward them (if the tasks were
                    # configured to do so)
                    task.read_streams(
                        forward_directly=True,
                        max_num_reads=self.lines_per_poll,
                    )
                    task.forward_streams()

                # Invoke a report
                self._invoke_report("while_working")

                # Check stop conditions
                if stop_conditions:
                    # Compile a list of workers where the stop conditions
                    # were fulfilled and keep track of them.
                    fulfilled = self._check_stop_conds(stop_conditions)
                    self.stopped_tasks += fulfilled

                    # Now signal those workers such that they terminate.
                    self._signal_workers(fulfilled, signal=SIG_STOPCOND)

                # Invoke periodic callback for all tasks
                if (
                    self._periodic_callback
                    and poll_no % self._periodic_callback == 0
                ):
                    self._invoke_periodic_callbacks()

                # Done with this poll.
                poll_no += 1
                time.sleep(self.poll_delay)

            else:
                # Finished working
                # Handle any remaining pending exceptions
                self._handle_pending_exceptions()

                # If this succeeded, we can call this work session:
                self._work_session_status = "finished successfully"

        except (KeyboardInterrupt, WorkerManagerTotalTimeout) as exc:
            # Got interrupted or a total timeout.
            # Interrupt the workers, giving them some time to shut down ...
            was_cancelled = self._handle_KeyboardInterrupt_or_TotalTimeout(exc)

        except WorkerManagerError as err:
            # Some error not related to the non-zero exit code occurred.
            # Gracefully terminate remaining tasks before re-raising the
            # exception

            # Suppress reporter to use CR; then inform via log messages
            if self.reporter:
                self.reporter.suppress_cr = True

            log.critical("Work session failed!")
            log.error("See above for error log.")

            # Now terminate the remaining active tasks
            log.hilight("Terminating active tasks ...")
            self._signal_workers(self.active_tasks, signal="SIGTERM")

            # Store end time and invoke a report
            self.times["end_working"] = dt.now()
            self._invoke_report("after_fail", force=True)

            # For some specific error types, do not raise but exit with status
            if isinstance(err, WorkerTaskNonZeroExit):
                log.critical("Exiting now ...\n")
                sys.exit(err.task.worker_status)

            # Some other error occurred; just raise
            log.critical("Re-raising error ...")
            raise

        # Register end time and invoke final report
        self.times["end_working"] = dt.now()
        if not was_cancelled:
            self._invoke_report("after_work", force=True)

        print("\n")
        log.progress("Work session %s.", self._work_session_status)

        duration = self.times["end_working"] - self.times["start_working"]
        c = self.task_counters
        log.note("  Work duration:          %11s", format_time(duration))
        log.note(
            "  Tasks finished:         %6d / %d total",
            c["finished"],
            c["total"],
        )
        log.note("      … worked on:        %6d", c["worked_on"])
        log.note("      … succeeded:        %6d", c["success"])
        log.note("      … skipped:          %6d", c["skipped"])
        log.note("      … stopped:          %6d", c["stopped"])
        log.note("      … failed/cancelled: %6d", c["failed"])

        return self._work_session_status

    # Non-public API ..........................................................

    def _invoke_report(self, rf_spec_name: str, *args, **kwargs):
        """Helper function to invoke the reporter's report function"""
        if self.reporter is None:
            return

        # Check whether to suppress this rf_spec
        if self._suppress_rf_specs and rf_spec_name in self._suppress_rf_specs:
            # Do not report this one
            return

        # Use the report format name as something like a "status indicator"
        self._reporter._latest_wm_report = rf_spec_name

        # Resolve the spec name and invoke the reports
        rfs = self.rf_spec[rf_spec_name]
        if not isinstance(rfs, (list, tuple)):
            rfs = [rfs]

        for rf in rfs:
            self.reporter.report(rf, *args, **kwargs)

    def _parse_timeout_args(
        self, *, timeout: Optional[float]
    ) -> Optional[float]:
        """Parses timeout-related arguments"""
        # Determine timeout arguments
        if timeout is None or timeout < 0:
            log.note("  Timeout:          None")
            return None

        # Calculate the time after which a timeout would be reached
        timeout_time = time.time() + timeout
        self.times["timeout"] = timeout_time

        # Inform about timeout
        _to_fstr = "%X" if timeout < 60 * 60 * 12 else "%X, %d.%m.%y"
        _to_at = dt.fromtimestamp(timeout_time).strftime(_to_fstr)
        log.note(
            "  Timeout:          %s", f"{_to_at} (in {format_time(timeout)})"
        )

        return self.times["timeout"]

    def _parse_stop_conditions(
        self, stop_conditions: Optional[list]
    ) -> Optional[List[StopCondition]]:
        """Prepare stop conditions, creating the corresponding objects if
        needed."""
        if not stop_conditions:
            log.note("  Stop conditions:  None")
            return

        stop_conditions = [
            sc if isinstance(sc, StopCondition) else StopCondition(**sc)
            for sc in stop_conditions
        ]
        self._stop_conditions.update(set(stop_conditions))

        log.note(
            "  Stop conditions:  %s",
            ", ".join([sc.name for sc in stop_conditions]),
        )

        return stop_conditions

    def _grab_task(self) -> WorkerTask:
        """Will initiate that a task is gotten from the queue and that it
        spawns its worker process.

        Returns:
            WorkerTask: The WorkerTask grabbed from the queue.

        Raises:
            queue.Empty: If the task queue was empty
        """
        # Get a task from the queue
        try:
            task = self.task_queue.get_nowait()

        except queue.Empty as err:
            raise queue.Empty(
                "No more tasks available in tasks queue."
            ) from err

        else:
            log.debug("Got %s from queue.", task)

        # Let it spawn its own worker, which will invoke its setup routine and
        # then (typically) create a worker subprocess for this task ...
        # In some cases, the worker may finish directly or the task will be
        # skipped, but this does not need to concern us at this point.
        task.spawn_worker()

        return task

    def _assign_tasks(self, num_free_workers: int) -> Tuple[int, int]:
        """Assigns tasks to (at most) ``num_free_workers`` and returns the
        number of spawned and skipped tasks.

        The ``spawn_rate`` of the WorkerManager will determine how many are
        actually spawned.

        .. note::

            Skipped tasks do not count into the number of spawned tasks.
        """
        if num_free_workers <= 0:
            return (0, 0)

        # How many workers are meant to be spawned?
        if self.spawn_rate == -1:
            num_spawn = num_free_workers
        else:
            num_spawn = min(num_free_workers, self.spawn_rate)

        # Grab the tasks, spawning the corresponding workers
        num_spawned = 0
        num_skipped = 0
        for _ in range(num_spawn):
            # Try to grab a task and start working on it
            try:
                new_task = self._grab_task()

            except queue.Empty:
                # There were no tasks left in the task queue
                break

            except SkipWorkerTask as skip_signal:
                log.debug("Task skipped: %s", skip_signal)
                num_skipped += 1

            else:
                # Task grabbed and spawned
                log.debug("Task spawned: %s", new_task)
                num_spawned += 1

        log.debug(
            "Assigned and spawned %d new tasks, skipping %d.",
            num_spawned,
            num_skipped,
        )
        return num_spawned, num_skipped

    def _poll_workers(self) -> int:
        """Will poll all workers that are in the active tasks list.

        If they have finished, this will effectively invoke their callbacks,
        which will in turn remove them from the active tasks list.
        """
        num_finished = 0
        for i, task in enumerate(self.active_tasks):
            # Poll its worker (by calling the .worker_status property) and thus
            # find out if it may have finished.
            if task.worker_status is not None:
                # This task has finished and, at this point, will have already
                # invoked and concluded with its callback functions.
                num_finished += 1

        return num_finished

    def _check_stop_conds(
        self, stop_conds: Sequence[StopCondition]
    ) -> Set[WorkerTask]:
        """Checks the given stop conditions for the active tasks and compiles
        a list of tasks that needs to be terminated.

        Args:
            stop_conds (Sequence[StopCondition]): The stop conditions that
                are to be checked.

        Returns:
            List[WorkerTask]: The WorkerTasks whose workers need to be
                terminated
        """
        to_terminate = []
        log.debug("Checking %d stop condition(s) ...", len(stop_conds))

        for sc in stop_conds:
            log.debug("Checking stop condition '%s' ...", sc.name)

            # Compile the list of tasks that fulfil a stop condition
            fulfilled = [
                t
                for t in self.active_tasks
                if (t not in self.stopped_tasks and sc.fulfilled(t))
            ]

            if fulfilled:
                log.debug(
                    "Stop condition '%s' fulfilled for %d task(s):  %s",
                    sc.name,
                    len(fulfilled),
                    ", ".join([t.name for t in fulfilled]),
                )
                to_terminate += fulfilled

        # Return as set to be sure that they are unique
        return set(to_terminate)

    def _invoke_periodic_callbacks(self):
        """Invokes the ``periodic`` callback function of each active task."""
        for task in self.active_tasks:
            task._invoke_callback("periodic")

    def _signal_workers(
        self, tasks: Union[str, List[WorkerTask]], *, signal: Union[str, int]
    ) -> None:
        """Send signals to a list of WorkerTasks.

        Args:
            tasks (Union[str, List[WorkerTask]]): strings 'all' or 'active' or
                a list of WorkerTasks to signal
            signal (Union[str, int]): The signal to send
        """
        if isinstance(tasks, str):
            if tasks == "all":
                tasks = self.tasks
            elif tasks == "active":
                tasks = self.active_tasks
            else:
                raise ValueError(
                    f"Tasks cannot be specified by string '{tasks}', "
                    "allowed strings are: 'all', 'active'."
                )

        if not tasks:
            log.debug("No worker tasks to signal.")
            return

        log.debug("Sending signal %s to %d task(s) ...", signal, len(tasks))
        for task in tasks:
            task.signal_worker(signal)

        log.debug(
            "All tasks signalled. Tasks' worker status:\n  %s",
            ", ".join([str(t.worker_status) for t in tasks]),
        )

    def _handle_pending_exceptions(self) -> None:
        """This method handles the list of pending exceptions during working,
        starting from the one added most recently.

        As the WorkerManager occupies the main thread, it is difficult for
        other threads to signal to the WorkerManager that an exception
        occurred.
        The pending_exceptions attribute allows such a handling; child threads
        can just add an exception object to it and they get handled during
        working of the WorkerManager.

        This method handles the following exception types in a specific manner:

            - ``WorkerTaskStopConditionFulfilled``: never raising or logging
            - ``WorkerTaskNonZeroExit``: raising or logging depending on the
              value of the ``nonzero_exit_handling`` property

        Returns:
            None

        Raises:
            Exception: The exception that was added first to the queue of
                pending exceptions
        """

        def log_task_stream(
            task: WorkerTask, *, num_entries: int, stream_name: str = "out"
        ) -> None:
            """Logs the last `num_entries` from the log of the `stream_name`
            of the given WorkerTask object using log.error
            """
            # Get the stream
            stream = task.streams[stream_name]

            # Get lines and print stream using logging module
            lines = stream["log"][-num_entries:]
            log.error(
                "Last ≤%d lines of combined stdout and stderr:\n" "\n  %s\n",
                num_entries,
                "\n  ".join(lines),
            )

        if self.pending_exceptions.empty():
            log.debug("No exceptions pending.")
            return
        # else: there was at least one exception

        # Go over all exceptions
        while not self.pending_exceptions.empty():
            # Get one exception off the queue
            exc = self.pending_exceptions.get_nowait()

            # Currently, only WorkerTaskNonZeroExit exceptions are handled here
            # If the type does not match, can directly raise it
            if not isinstance(exc, WorkerTaskNonZeroExit):
                log.error(
                    "Encountered a pending exception that requires raising!"
                )
                raise exc

            log.debug("Handling %s ...", exc.__class__.__name__)

            # Take care of stop conditions, which do NOT need to be raised
            if isinstance(exc, WorkerTaskStopConditionFulfilled):
                continue

            # Same for skipped tasks
            if isinstance(exc, SkipWorkerTask):
                continue

            # Distinguish different ways of handling these exceptions
            # Ignore all
            if self.nonzero_exit_handling == "ignore":
                # Done here. Continue with the next exception
                continue

            # Ignore terminated tasks for `warn` and `ignore` levels
            elif abs(exc.task.worker_status) == SIGMAP[
                "SIGTERM"
            ] and self.nonzero_exit_handling not in ("warn_all", "raise"):
                continue

            # else: will generate some log output, so need to adjust Reporter
            #       to not use CR characters which would mangle up the output
            if self.reporter:
                self.reporter.suppress_cr = True

            # Provide some info on the exit status

            if self.nonzero_exit_handling in ("warn", "warn_all"):
                # Print the error and the last few lines of the error log
                log.warning(str(exc))
                log_task_stream(exc.task, num_entries=12)

                # Nothing else to do
                continue

            # At this stage, the handling mode is 'raise'. Show more log lines:
            self._work_session_status = "failed"

            log.critical(str(exc))
            log_task_stream(exc.task, num_entries=32)

            # By raising here, the except block in start_working will be
            # invoked and terminate workers before calling sys.exit
            raise exc

        # The pending_exceptions list is now empty
        log.debug("Handled all pending exceptions.")

    def _handle_KeyboardInterrupt_or_TotalTimeout(self, exc: Exception):
        """Used to wind down work in case of KeyboardInterrupt or TotalTimeout.
        All active workers will be stopped, either on their own within a grace
        period or, after that, abruptly via a kill signal.
        """
        # Temporarily suppress reporter CRs to make room for log messages
        if self.reporter:
            self.reporter.suppress_cr = True

        log.warning("Received %s.", type(exc).__name__)
        self._work_session_status = "cancelled"

        # Get interruption parameters and send signal to workers
        signal = self.interrupt_params.get("send_signal", "SIGINT")
        grace_period = self.interrupt_params.get("grace_period", 5.0)

        log.info(
            "Sending signal %s to %d active task(s) ...",
            signal,
            len(self.active_tasks),
        )
        self._signal_workers(self.active_tasks, signal=signal)

        # Continuously poll them for a certain grace period in order to
        # find out if they have shut down.
        log.warning(
            "Allowing %s for %d task(s) to shut down ... ",
            format_time(grace_period, ms_precision=1),
            len(self.active_tasks),
        )
        log.caution("Press Ctrl + C to send SIGKILL.\n")
        grace_period_start = time.time()
        if self.reporter:
            self.reporter.suppress_cr = False

        try:
            while True:
                self._poll_workers()

                # Check whether to leave the loop
                if not self.active_tasks:
                    break
                elif time.time() > grace_period_start + grace_period:
                    raise KeyboardInterrupt

                # Need to continue. Delay polling ...
                time.sleep(self.poll_delay)

        except KeyboardInterrupt:
            log.critical(
                "Now sending SIGKILL to %d task(s) ...",
                len(self.active_tasks),
            )
            self._signal_workers(self.active_tasks, signal="SIGKILL")

            # Wait briefly (killing shouldn't take long), then poll
            # one last time to update all task's status.
            time.sleep(0.5)
            self._poll_workers()

        # Store end time and invoke a report
        self.times["end_working"] = dt.now()
        self._invoke_report("after_cancel", force=True)

        exit = self.interrupt_params.get("exit", True)
        if type(exc) is KeyboardInterrupt and exit:
            # Exit with appropriate exit code (128 + abs(signum))
            log.warning("Exiting after KeyboardInterrupt ...\n")
            sys.exit(128 + abs(SIGMAP[signal]))

        # Otherwise, just return control to the calling scope
        return True
