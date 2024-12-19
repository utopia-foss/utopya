"""Defines some resources used *internally* throughout the package"""

from typing import Dict, List, Tuple, Union

# -----------------------------------------------------------------------------

SNIPPETS: Dict[str, Union[str, List[str]]] = dict()
"""Message fragments to use in user communication, some of which are lists
of synonymous strings."""

SNIPPETS["yay"] = [
    "Yay! ✨",
    "Ta-daa! 🎉",
    "Hooray! 🙌",
    "Woohoo! 🥳",
    "Yippee! 🚀",
    "Yeah! 😎",
]

SPINNER_WIDE: Tuple[str, ...] = (
    "(●      )",
    "( ●     )",
    "(  ●    )",
    "(   ●   )",
    "(    ●  )",
    "(     ● )",
    "(      ●)",
    "(     ● )",
    "(    ●  )",
    "(   ●   )",
    "(  ●    )",
    "( ●     )",
)
"""A simple ASCII based loading indicator"""
