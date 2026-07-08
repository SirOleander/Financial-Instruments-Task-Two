"""DEPRECATED shim — the real module is `fi.config` (+ `fi.concepts`).

Kept only so the not-yet-moved modules (`C_client`, `D_pipeline`, `price_target`,
`K_backtest`, `tools/viewdatabase`) keep importing `A_config` unchanged while the refactor
proceeds one step at a time. Deleted once its last importer has moved.

Re-exports the full public namespace of the old A_config, so `A_config.<ANYTHING>`
resolves exactly as before. `validate_config()` still runs once, at `fi.config` import.
"""
from fi.concepts import *  # noqa: F401,F403
from fi.config import *  # noqa: F401,F403
