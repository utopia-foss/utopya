(backend-model)=
# Model base classes


(backend-basemodel)=
## `BaseModel` class
The {py:class}`~utopya_backend.model.base.BaseModel` implements basic simulation infrastructure like a shared logger, RNG, config file reading, signal handling and abstract methods that provide a blue print for model implementation.

### Relevant properties



(backend-stepwisemodel)=
## `StepwiseModel` class
The {py:class}`~utopya_backend.model.step.StepwiseModel` specializes the {py:class}`~utopya_backend.model.base.BaseModel` for models that abstract model iteration to step-wise integration with integer time steps.

An example for a model based on `StepwiseModel` can be found in the {ref}`utopya demo project <utopya-demo>`:


### Example implementation

The following is the full implementation of `ExtendedModel`, one of the {ref}`utopya demo models <utopya-demo>`.
It inherits from {py:class}`~utopya_backend.model.step.StepwiseModel` and implements the following methods:

- `setup`: Reads configuration entries and sets up output datasets
- `perform_step`: Iterates the state
- `monitor`: Provides monitoring information to utopya
- `write_data`: Writes data

````{toggle}
```{literalinclude} ../../demo/models/ExtendedModel/impl/model.py
---
language: python
---
```
````

See [the `demo` directory in the repository](https://gitlab.com/utopia-project/utopya/-/tree/main/demo) for the context in which this model is implemented.
Alternatively, have a look at the {ref}`utopya-demo` page.
