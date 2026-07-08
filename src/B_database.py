"""DEPRECATED shim — the real module is `fi.db`.

Kept only so the not-yet-moved pipeline modules keep importing `B_database` unchanged
while the refactor proceeds. Deleted once its last importer has moved.
"""
from fi.db import *  # noqa: F401,F403
