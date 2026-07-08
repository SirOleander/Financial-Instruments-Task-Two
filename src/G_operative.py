"""DEPRECATED shim — the real module is `fi.operative`."""
from fi.operative import *  # noqa: F401,F403
from fi.operative import main

if __name__ == "__main__":
    main()
