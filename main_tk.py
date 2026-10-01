import os
import sys
import multiprocessing

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    os.chdir(PROJECT_ROOT)
    from views.app_view import create_main_window

    create_main_window()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    multiprocessing.set_start_method("spawn")
    main()
