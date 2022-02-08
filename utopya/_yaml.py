"""Supplies basic YAML interface, inherited from dantro and paramspace"""

import paramspace
from dantro.tools import load_yml, write_yml, yaml

# Make sure the yaml instances are really shared
assert yaml is paramspace.yaml
