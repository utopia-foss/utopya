#!/usr/bin/env python3
"""Imports and runs the selected model"""

import os
import sys

from utopya_backend import backend_logger, import_package_from_dir

# Instead of a relative import (which is not available in the __main__ module
# that this executable represents), use an absolute import from a path.
# This makes the model implementation available as a module without requiring
# installation.
# NOTE The `executable_control.run_from_tmpdir` key in the Multiverse config
#      needs to be set to False (default). Otherwise, this file will be
#      executed from a *temporary* directory, not allowing to perform this
#      relative import.
# NOTE If your local model implementation package has a different name than
#      `impl`, adjust the following lines accordingly.
impl = import_package_from_dir(
    os.path.join(os.path.dirname(__file__), "impl"),
)
Model = impl.Model

if __name__ == "__main__":
    model = Model(cfg_file_path=sys.argv[1])
    model.run()
    del model

    backend_logger.info("All done.")
