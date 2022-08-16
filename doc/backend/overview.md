(backend-overview)=

# Overview

The {py:mod}`utopya_backend` package is a standalone package that provides
tools for implementation of Python-based models that use {py:mod}`utopya` as a
simulation management frontend:

- A set of {ref}`model base classes <backend-model>` that provide a scaffolding for implementing your own models:
    - The {ref}`backend-basemodel` implements basic simulation infrastructure like a shared logger, RNG, config file reading, signal handling and abstract methods that provide a blue print for model implementation.
    - The {ref}`backend-stepwisemodel` specializes this for models that abstract iteration to step-wise integration with integer time steps.
- Functions for {ref}`data writing and reading <backend-io>`.
- General {py:mod}`tools <utopya_backend.tools>` that can be useful in this process.



```{admonition} Feedback, ideas, bugs?
If you have ideas how to improve or expand the {py:mod}`utopya_backend` package or in case you found a bug:
Please let us know by opening an issue [in the GitLab project](https://gitlab.com/utopia-project/utopya/-/issues/new).
```
