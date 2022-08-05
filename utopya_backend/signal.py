"""Signal handling when using the utopya backend, e.g. for catching stop
conditions and handling them gracefully."""

import signal
import time

SIG_STOPCOND = signal.SIGUSR1
"""Which signal to look out for if a stop condition was fulfilled. This should
match :py:data:`utopya.stop_conditions.SIG_STOPCOND`."""

SIGNAL_INFO = dict(got_signal=False, signum=None, frame=None, at_time=None)
"""A dict that holds information on whether any kind of signal was received
and at which time. This can be analysed by other modules to determine which
action to take."""


def _handle_signal(signum, frame):
    """A signal handler function that writes information into the
    ``SIGNAL_INFO`` dict."""
    SIGNAL_INFO["got_signal"] = True
    SIGNAL_INFO["signum"] = signum
    SIGNAL_INFO["frame"] = frame
    SIGNAL_INFO["at_time"] = time.time()


def attach_signal_handlers(
    *, for_stop_conds: bool = True, for_interrupts: bool = True
):
    """A function that can be invoked to attach signal handlers for use within
    utopya. There are two kinds of signals:

    - stop conditions, as implemented in :py:mod:`utopya.stop_conditions`
    - interrupt signals ``SIGTERM`` and ``SIGINT``

    Args:
        for_stop_conds (bool, optional): Whether to attach signal handlers for
            stop conditions.
        for_interrupts (bool, optional): Whether to attach signal handlers for
            interrupts.
    """
    if for_stop_conds:
        signal.signal(SIG_STOPCOND, _handle_signal)

    if for_interrupts:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
