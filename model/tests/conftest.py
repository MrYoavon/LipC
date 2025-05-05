# tests/conftest.py
import os
import sys

# Insert project root (one level above tests/)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# fmt: off
import pytest
# fmt: on