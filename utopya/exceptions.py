"""utopya-specific exception types"""


class UtopyaException(BaseException):
    """Base class for utopya-specific exceptions"""


# -- Parameter validation -----------------------------------------------------


class ValidationError(UtopyaException, ValueError):
    """Raised upon failure to validate a parameter"""


# -- WorkerManager ------------------------------------------------------------


class WorkerManagerError(UtopyaException):
    """The base exception class for WorkerManager errors"""


class WorkerManagerTotalTimeout(WorkerManagerError):
    """Raised when a total timeout occurred"""


class WorkerTaskError(WorkerManagerError):
    """Raised when there was an error in a WorkerTask"""


class WorkerTaskNonZeroExit(WorkerTaskError):
    """Can be raised when a WorkerTask exited with a non-zero exit code."""

    def __init__(self, task: "utopya.task.WorkerTask", *args, **kwargs):
        """Initialize an error handling non-zero exit codes from workers"""
        self.task = task
        super().__init__(*args, **kwargs)

    def __str__(self) -> str:
        """Returns information on the error"""
        from ._signal import SIGMAP

        signals = [
            signal
            for signal, signum in SIGMAP.items()
            if signum == abs(self.task.worker_status)
        ]

        return (
            f"Task '{self.task.name}' exited with non-zero exit "
            f"status: {self.task.worker_status}.\nThis may originate from "
            f"the following signals:  {', '.join(signals)}.\n"
            "Googling these might help with identifying the error. "
            "Also, inspect the log and the log file for further error "
            "messages. To increase verbosity, run in debug mode, e.g. by "
            "passing the --debug flag to the CLI."
        )


class WorkerTaskStopConditionFulfilled(WorkerTaskNonZeroExit):
    """An exception that is raised when a worker-specific stop condition was
    fulfilled. This allows being handled separately to other non-zero exits.
    """


# -----------------------------------------------------------------------------


class YAMLRegistryError(UtopyaException, ValueError):
    """Base class for errors in YAMLRegistry"""


class EntryExistsError(YAMLRegistryError):
    """Raised if an entry already exists"""


class MissingEntryError(YAMLRegistryError):
    """Raised if an entry is missing"""


class MissingRegistryError(YAMLRegistryError):
    """Raised if a registry is missing"""


class EntryValidationError(YAMLRegistryError):
    """Raised upon failed validation of a registry entry"""


class SchemaValidationError(YAMLRegistryError):
    """If schema validation failed"""


# -----------------------------------------------------------------------------


class ModelRegistryError(UtopyaException, ValueError):
    """Raised on errors with model registry"""


class MissingModelError(ModelRegistryError):
    """Raised when a model is missing"""


class BundleExistsError(ModelRegistryError):
    """Raised when a bundle that compared equal already exists"""


class MissingBundleError(ModelRegistryError):
    """Raised when a bundle is missing"""


class BundleValidationError(ModelRegistryError):
    """Raised when the result of validating the existence of a bundle fails"""


class ProjectRegistryError(UtopyaException, ValueError):
    """Raised on errors with project registry"""


class MissingProjectError(ProjectRegistryError):
    """Raised on a missing project"""


class ProjectExistsError(ProjectRegistryError):
    """Raised if a project or project file of that name already exists"""
