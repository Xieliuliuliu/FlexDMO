"""Compatibility entry point. Prefer python main.py."""
import multiprocessing
from main import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
