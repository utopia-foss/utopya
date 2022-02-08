"""Implements signalling-related functionality and globally relevant data"""

import signal as _signal

SIGMAP = {a: int(getattr(_signal, a)) for a in dir(_signal) if a[:3] == "SIG"}
"""A map from signal names to corresponding integer exit codes"""
