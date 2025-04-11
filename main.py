# main.py
import os

from views.app_view import create_main_window
import sys
sys.path.append(os.path.abspath("./"))  # or os.path.abspath("D:/Project/platform2DMOEAs")


if __name__ == "__main__":
    create_main_window()
