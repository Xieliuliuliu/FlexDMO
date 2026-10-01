"""Native single-file plugin UI verification; temporary code is self-cleaning."""
import argparse
from pathlib import Path
import unittest


def main():
    import main_qt
    from flexdmo_app.tests.test_code_ui import CodeUiTests
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", help="Optional existing directory for QA screenshots")
    options = parser.parse_args()
    if options.capture:
        folder = Path(options.capture)
        if not folder.is_dir():
            parser.error("--capture must name an existing QA directory")
        CodeUiTests.capture_directory = folder
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CodeUiTests))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
