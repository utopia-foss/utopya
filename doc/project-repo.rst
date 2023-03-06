.. _project_repo:

Set up your own models repository
=================================

To work with your own models, it often makes sense to have dedicated project repositories.
This page gives instructions on how to set up such a project.

.. hint::

    The :ref:`utopya_demo` is one example of how such a project may look like.


What is a project?
------------------
With utopya, it is possible to run and evaluate many different models on your machine.
To make this process a bit smoother, utopya allows to group certain models into so-called *projects*.
Typically, these projects reflect individual version-controlled repositories.

In the end, a utopya project is simply a directory with a ``.utopya-project.yml`` file, which denotes it as being a utopya project (and which contains a bunch of metadata to describe the project).
Inside the project directory, a models directory holds the model implementations.


.. _template_project:

The Models Template
-------------------
To quickly set up a utopya-based simulation environment, we provide the `Models Template for Python models <https://gitlab.com/utopia-project/models_template_py>`_.
It provides an easy way to create your own utopya project and kick-start your model development.

In broad strokes, the process is as follows:

#. Install `cookiecutter <https://cookiecutter.readthedocs.io>`_, which will take care of downloading and adjusting the template.
#. Create your own project from the template by customizing the template's parameters.
#. Make adjustments to the newly-created repository.
#. Start implementing your models.

The most up-to-date instructions will always be in the template project's `README <https://gitlab.com/utopia-project/models_template_py/-/blob/main/README.md>`_ itself.
See there for more detailed instructions.
