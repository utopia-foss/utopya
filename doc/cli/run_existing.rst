
.. _cli_utopya_run_existing:

``utopya run-existing`` [Advanced]
=========================================================

The ``utopya run-existing`` can be helpful to complete interrupted runs, in
particular to complete universes that have not been worked on.
However, the use of ``utopya run`` is always preferential, if possible.

.. note ::
    The ``utopya run-existing`` is an advanced and experimental feature.
    It is not possible to change any (meta-) configuration entries, not even
    those associated with worker and runtime control.


.. click:: utopya_cli.run_existing:run_existing
    :prog: utopya run-existing
    :nested: full


Usecase: Distributed computation
--------------------------------

Another usecase where run-existing can be helpful is on distributed computers,
e.g. clusters. In the slurm cluster this has been tested sucessfully.
The pipeline is the following

#. Perform ``utopya run .. --no-work``, creating all universe configurations without working on them. Best to backup the executable.
#. After completion, gather the paths of the universe output (data) directories in an array.
#. Submit a sbatch array=1-N job, where the ``$SLURM_ARRAY_TASK_ID`` (from 1 to N) can be used as an index on the array of output directories: ``utopya run-existing MODEL_NAME FOLDER --uni UNIVERSES_ARRAY[ $SLURM_ARRAY_TASK_ID ]``.
