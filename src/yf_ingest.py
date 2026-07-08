"""DEPRECATED shim — the real module is `fi.market` (`main_yf_facts`)."""
import sys

from fi.market import *  # noqa: F401,F403
from fi.market import main_yf_facts as main

if __name__ == "__main__":
    main(write="--write" in sys.argv)
