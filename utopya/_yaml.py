"""Supplies basic YAML interface, inherited from :py:mod:`yayaml`"""

from yayaml import load_yml, write_yml, yaml

# Set the flow style
yaml.default_flow_style = False
