
.. _param_validation:

Parameter Validation
====================

With utopya's parameter validation framework, model parameters can be validated before a simulation is started, which helps to avoid misconfigurations early on: before a simulation is even started.
In addition, it offers an alternative to parameter checks in the model implementation.

Unlike many validation frameworks out there, :py:mod:`utopya.parameter` allows to **define parameter properties alongside their defaults** and is optimized for use with YAML configuration files.

How to use
----------
Let's start with an example, assuming that your model's default configuration looks something like this, containing parameters of different

.. code-block:: yaml

    enable_fleeing: true
    p_flee: 0.1
    flee_distance: 3
    flee_mode: random

To use parameter validation, the parameters' allowed values need to be specified.
This can be done directly in the default model configuration using YAML tags (``!<tag>``):

.. code-block:: yaml

    enable_fleeing: !is-bool          true
    p_flee:         !is-probability   0.1
    flee_distance:  !is-unsigned      3
    flee_mode: !param
      default: random
      is_any_of: [random, intelligent]

As you can see, the parameter specification uses YAML tags (``!<tag>``) and aims to be as descriptive as possible:
``p_flee`` is meant to control a probability, ``flee_mode`` can either be ``random`` or ``intelligent`` and so on.
In the example, we have made use of both the :ref:`shorthand syntax <param_shorthand>` (starting with ``!is-``) and the *full form* (``!param``), each constructing a :py:class:`~utopya.parameter.Parameter` object from the given arguments which can then be validated.

**To use parameter validation**, simply set these tags in your model's *default* configuration.
They work with any kind of scalar parameters.
When the :py:class:`~utopya.multiverse.Multiverse` assembles the configuration for the model run, it will automatically validate the given values against these parameters.

.. hint::

    To *disable* parameter validation, set the ``perform_validation`` parameter in the :py:class:`~utopya.multiverse.Multiverse` meta-configuration to ``False``, e.g. from your run configuration.

    In the :ref:`command line interface <cli_utopya_run>`, ``--no-validate`` will deactivate parameter validation.

.. note::

    It is `not yet <https://gitlab.com/utopia-project/utopya/-/issues/63>`_ possible to validate sequences or mappings.
    Parameter values need to be scalar (numerical, string, boolean etc).



.. _param_shorthand:

Shorthand Syntax
----------------
As seen above, the shorthand modes are meant to directly describe which parameter values are valid.
The following shorthand modes are available:

.. ipython:: parameter_shorthands

    In [1]: from utopya.parameter import Parameter

    In [2]: print("\n".join(Parameter.SHORTHAND_MODES))

.. hint::

    Typically, you will use these from within a YAML configuration file, without needing an import.
    Don't forget that the corresponding YAML tag has a leading exclamation mark: ``!<mode>``.

    Alternatively, these modes can also be used for the :py:meth:`~utopya.parameter.Parameter.from_shorthand` class method; this is what happens under the hood.

.. admonition:: Exact definition of shorthand parameters
    :class: dropdown

    .. ipython:: parameter_shorthands

        @suppress
        In [3]: def format_shorthand_defaults(mode, param_defs) -> str:
           ...:     d = {k: v for k, v in param_defs(None).items() if k not in ("default",)}
           ...:     return f"\n{mode:20s}\n" + "\n".join(f"  {k:12s}: {repr(v)}" for k, v in d.items())

        @suppress
        In [4]: def print_shorthand_defaults():
           ...:     print("\n".join(format_shorthand_defaults(m, c) for m, c in Parameter.SHORTHAND_MODES.items()))

        In [5]: print_shorthand_defaults()
