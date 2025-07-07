"""Legacy setup.py for backwards compatibility.

This file is kept for compatibility with older installation methods.
The project now uses pyproject.toml for configuration.
"""

from setuptools import setup

# The actual configuration is in pyproject.toml
# This file just calls setup() to maintain compatibility
setup()
