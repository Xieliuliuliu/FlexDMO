import unittest
from unittest.mock import Mock

from views.common.responsive_workspace import workspace_mode
from views.test_module.test_module_handler import format_parameter_label
from views.components.scrolled_frame import NativeScrolledFrame


class ResponsiveWorkspaceTests(unittest.TestCase):
    def test_layout_breakpoints(self):
        for width, expected in ((640, "tabs"), (899, "tabs"),
                                (900, "compact"), (1249, "compact"),
                                (1250, "standard"), (1549, "standard"),
                                (1550, "wide"), (2200, "wide")):
            with self.subTest(width=width):
                self.assertEqual(workspace_mode(width), expected)

    def test_algorithm_parameters_have_readable_labels(self):
        for key in ("seed", "delta", "proM", "disM", "proC", "disC",
                    "K", "u", "hidden_size", "dropout", "lr"):
            self.assertNotEqual(format_parameter_label(key), key)

    def test_macos_decimal_scroll_amounts_are_supported(self):
        for value in ('3.0', '-3.0', '0.5', '3'):
            with self.subTest(value=value):
                scroll = Mock()
                NativeScrolledFrame.yview(scroll, 'scroll', value, 'units')
                scroll.yview_scroll.assert_called_once_with(number=float(value), what='units')


if __name__ == "__main__":
    unittest.main()
