"""DEPRECATED shim — the real module is `fi.modelling` (eda stage)."""
from fi.modelling import *  # noqa: F401,F403
from fi.modelling import main_eda as main

if __name__ == "__main__":
    main()
