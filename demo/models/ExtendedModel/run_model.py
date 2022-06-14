#!/usr/bin/env python3
"""Imports and runs the selected model"""

import os
import sys

import h5py as h5
import numpy as np
import ruamel.yaml as yaml

# FIXME Should not import from private module!
from utopya._import_tools import import_module_from_path

# Instead of a relative import (which is not available in the __main__ module
# that this executable represents), use an absolute import from a path.
# This makes the model implementation available as a module without requiring
# installation.
# NOTE The `executable_control.run_from_tmpdir` key needs to be set to False
#      in the run config in order for the `__file__` variable to be used for
#      selecting the path to the `impl` module.
impl = import_module_from_path(
    mod_path=os.path.dirname(__file__),
    mod_str="impl",
)
Model = impl.Model

if __name__ == "__main__":
    print("Preparing simulation run ...")

    model = Model(cfg_file_path=sys.argv[1])
    model.run()
    del model

    print("\nAll done.")
