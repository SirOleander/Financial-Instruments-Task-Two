"""DEPRECATED shim — the real module is `fi.modelling` (analysis stage)."""
from fi.modelling import *  # noqa: F401,F403
from fi.modelling import main_analysis as main

if __name__ == "__main__":
    main()
