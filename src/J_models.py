"""DEPRECATED shim — the real module is `fi.modelling` (train stage)."""
import sys

from fi.modelling import *  # noqa: F401,F403
from fi.modelling import ablation, main_train

if __name__ == "__main__":
    if "--ablation" in sys.argv:
        ablation()
    else:
        main_train()
