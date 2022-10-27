.. _shell_completion:

Shell Completion
================
The utopya CLI supports completion of parts of its CLI like model names, project names, or run directories.
For instance, the following will list all registered models:

.. code-block:: text

    utopya run <tab>


.. contents::
    :local:


Enable shell completion
-----------------------
To enable shell completion, **follow the steps described in the** `click documentation <https://click.palletsprojects.com/en/8.1.x/shell-completion/#enabling-completion>`_ 📚.

Make sure to select the appropriate shell and replace the ``foo-bar`` placeholder with ``utopya``.
We recommend to install shell-completion to a file to not reduce shell responsiveness.

.. hint::

    To find out which shell you are using, run *any* of the following commands:

    .. code-block:: bash

        echo $0
        echo $SHELL
        ps -p "$$"

.. hint::

    If you are a `Utopia <https://gitlab.com/utopia-project/utopia>`_ user, repeat the process using ``utopia`` instead of ``utopya``.

.. admonition:: Why do I have to do this manually?

    Basically, we think that changes to your shell configuration should not be automated — this should be a deliberate decision on your side.
    Click, the framework used to implement the utopya CLI, does not do this automatically, either.

    But: The setup is not difficult, it's well-documented by click, and there is an example here as well.


Example: zsh
^^^^^^^^^^^^
Say your shell is ``zsh``, then the commands to install the utopya CLI shell completion (via the file-based approach) are:

.. code-block:: bash

    _UTOPYA_COMPLETE=zsh_source utopya > ~/.utopya-complete.zsh

After that, source the file in your ``~/.zshrc`` by adding the following line:

.. code-block:: bash

    source ~/.utopya-complete.zsh

You will need to restart your shell for the changes to take effect.



Remarks
-------
Complete run directories for ``utopya eval`` command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When calling ``utopya eval MODEL_NAME [RUN_DIR] …``, the run directory can be auto-completed.
However, the following remarks need to be taken into account.

As run directories (where the output of a simulation is written to) can be configured individually for *each* and every run, there is no *single* place in which to search for completion suggestions of run directories.
Thus, the completion only looks at a (configurable) list of search directories, which include the canonical ``~/utopya_output``.

.. hint::

    You can still specify absolute or relative paths for the ``RUN_DIR`` argument, but they will not be auto-completed.

.. admonition:: Run directories not shown correctly?

    If suggestions for run directories are not correct, they may be missing from the search paths.
    See below on how to configure which paths are being searched to generate the suggestions.


Configure run directory search paths
""""""""""""""""""""""""""""""""""""
To configure this list, run:

.. code-block:: bash

    utopya config utopya --edit

and adjust the ``cli.run_dir_search_paths`` entry.
For example:

.. code-block:: yaml

    # ~/.config/utopya/utopya_cfg.yml
    ---
    cli:
      run_dir_search_paths:
        # Canonical locations:
        - ~/utopya_output
        - ~/utopia_output
        #
        # Custom locations
        - ~/my/custom/output/directory
        # ... can add more here ...

.. hint::

    If you don't want to use the CLI for editing the entry, manually open the ``~/.config/utopya/utopya_cfg.yml`` or create it, if it does not exist.
