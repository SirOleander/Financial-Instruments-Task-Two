"""DEPRECATED shim — the real module is `fi.modelling` (backtest stage)."""
from fi.modelling import *  # noqa: F401,F403
from fi.modelling import main_backtest as main

if __name__ == "__main__":
    main()
