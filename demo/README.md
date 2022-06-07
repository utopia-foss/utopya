# Demo Project

This directory provides an example model implementation and project structure.
Its aim is to show the ways in which utopya can be used with your own project and models.

The demo project showcases the following capabilities of utopya:

- Example implementation for a utopya model
    - `MinimalModel`: using only the minimal amount of utopya features
    - `ExtendedModel` (🚧): showcasing more utopya features
- Providing a `.utopya-project.yml` file for project registration
- Providing a `<model_name>_info.yml` file for model registration
- ... 🚧

The instructions below show how you can adapt the demo project to your own use case.

## Instructions
First, install utopya according to the instructions in the [main README](../README.md#Installation).
If all went well, you should be able to call `utopya --help` in your virtual environment.

Afterwards download this `demo` directory to a place of your choice and rename it; this will be the place where your own project and model will be implemented.
The files in this directory will be adjusted bit by bit to fit your project and model implementation.

## Project setup
A project in utopya denotes an aggregation of model implementations.
These models may be grouped into a project because they use the same infrastructure and dependencies, address similar questions, or for any other reason.
Correspondingly, utopya attaches some functionality to a project that can be shared between models, like default configurations for simulations or data evaluation.

In order to coordinate project-level functionality, utopya needs to know about the structure of a project.
This is achieved via the [`.utopya-project.yml`](.utopya-project.yml) file, which contains project-level information: the project name, local paths, and metadata.

To register your project, follow these steps:

1. Make sure your project directory is in the intended location and named to your liking.
1. Open the `.utopya-project.yml` file and edit the following entries:
    - `project_name`: This should be the name of *your* project
    - `paths`: Make sure the `models_dir` points to the right directory (relative to the info file).
      If you do not intend on using Python model tests and custom plot implementations, delete the corresponding entries.
    - `metadata`: Adjust (or delete) the entries.
1. Enter your project directory and *from that directory* invoke the utopya CLI to register the project:

    ```
    utopya projects register .
    ```

You should get a positive response from the utopya CLI and your project should appear in the project list when calling:

```
utopya projects ls
```

**Note:** Any changes to the project info file need to be communicated to utopya by calling the registration command anew.
You will then have to additionally pass the `--exists-action overwrite` flag, because a project of that name already exists.
See `utopya projects register --help` for more information.


## Model setup
Let's get to the model implementation.

Again, utopya needs to know about the model and the corresponding files.
Like with projects, models can be registered using the CLI and an info file, here the `<model_name>_info.yml` file.

### The `MinimalModel`
As an example, let's register the `MinimalModel`:

1. Enter the `demo/models/MinimalModel` directory
1. Call the registration command:

    ```
    utopya models register from-manifest *_info.yml
    ```

After successful registration, you should be able to run the model:

```
utopya run MinimalModel
```


### Your own model
For your own model, do the following:

1. Create a new directory within the `models` directory (or the corresponding directory defined in the project info file).
1. Add an info file akin to `MinimalModel_info.yml`, changing the following entries:
    - `model_name`: should be the name of *your* model
    - `paths`: adapt the entries here, specifically that for `executable` and `default_cfg`. These can also be paths relative to the info file.
    - `metadata`: update or delete the entries in there.
1. Make sure you are in the correct directory and call the registration command:

    ```
    utopya models register from-manifest *_info.yml
    ```

Your own model should now be registered and invokable via `utopya run`.


#### Requirements for a model executable
The model executable need not be a Python script, it can be *any* executable.
It is a Python script in this example to allow for easy readability, but you can choose any programming language for your model implementation.

In fact, utopya does not pose *any* limitations on the executable: it can essentially do whatever it wants.
Only if you want to use more of utopya's features, complying to a certain behaviour is advantageous – but that is all *optional*.

However, we do suggest that the executable complies to the following:

- It should expect one (and only one) additional argument: the absolute path to the YAML configuration file.
- The executable should then load that configuration file and use some of its information:
    - The `seed` entry to set the initial PRNG state; this is in order to increase reproducibility of model simulations.
    - The `output_dir` entry for the location of any output files; this is in order to have the output files managed by utopya.
    - The model configuration which is available under the `<model_name>` key.

*Optionally*, the following information from the config file can be taken into account to use more features of utopya:

- `log_levels`: provides log levels for the `backend` and `model` loggers, also adjustable via the CLI.
- For step-based models:
    - `num_steps`: the number of iterations, which can then be set directly from the CLI.
    - `write_every` and `write_start`: for controlling the time steps at which data is written.

Also, the model may communicate its progress by emitting lines via STDOUT, which is picked up by utopya and translated into a simulation progress bar.
The output should match the following pattern:

```
!!map {progress: 0.01}
```

Here, `progress` denotes the individual simulation's progress and needs to be a float value between 0 and 1.


#### Data evaluation pipeline
Being aware of where the model outputs its simulation data, utopya can initiate a data processing pipeline.
To that end, the following configuration files need to be added or adapted: ...

🚧


### Remarks
- Strictly speaking, utopya does not require a model to be associated with a project.
  However, this makes many aspects of simulation control more convenient, which is why we recommend registering a project with utopya.
- Across utopya, there can be multiple models with the same name, e.g. if you want to run multiple versions of a model.
  Models can be distinguished via their `label` property, which can also be set via the CLI.
  If there is only one label available, that one will be used automatically; otherwise you might have to choose between "info bundles" using the `--label` CLI option.
