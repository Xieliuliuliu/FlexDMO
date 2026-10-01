"""Test-only access to Qt's native Cocoa accessibility bridge.

No OS permission changes and no external app inspection. Never cache a borrowed
QAccessibleInterface across events: model/lifetime changes may invalidate it.
"""
import ctypes

from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication
from shiboken6 import getCppPointer


class CocoaProbe:
    def __init__(self):
        if QApplication.instance().platformName() != "cocoa":
            raise RuntimeError("原生 Cocoa 检查必须使用 macOS 窗口，不能设置 offscreen")
        self.objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        self.objc.objc_getClass.argtypes = [ctypes.c_char_p]
        self.objc.objc_getClass.restype = ctypes.c_void_p
        self.objc.sel_registerName.argtypes = [ctypes.c_char_p]
        self.objc.sel_registerName.restype = ctypes.c_void_p
        address = ctypes.cast(self.objc.objc_msgSend, ctypes.c_void_p).value
        self.send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
        self.send_arg = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
        self.element_class = self.objc.objc_getClass(b"QMacAccessibilityElement")
        if not self.element_class:
            raise RuntimeError("未找到 Qt Cocoa 无障碍桥接类")
        self.create = self.objc.sel_registerName(b"elementWithInterface:")
        self.selected = self.objc.sel_registerName(b"accessibilitySelectedChildren")
        self.title = self.objc.sel_registerName(b"accessibilityTitle")
        self.label = self.objc.sel_registerName(b"accessibilityLabel")
        self.calls = 0

    def check_history_widget(self, widget):
        # Query afresh, use immediately on the UI thread, then release Python's
        # wrapper. Holding an interface over app.processEvents() is unsafe.
        interface = QAccessible.queryAccessibleInterface(widget)
        assert interface is not None and interface.isValid()
        assert interface.selectionInterface() is None
        assert interface.role() not in (QAccessible.Role.Tree, QAccessible.Role.Table, QAccessible.Role.List)
        element = self.send_arg(self.element_class, self.create, getCppPointer(interface)[0])
        assert element
        # This is the actual libqcocoa selector from the user's crash stack,
        # not merely a Python mock or an offscreen selection check.
        assert not self.send(element, self.selected)
        self.send(element, self.title)
        self.send(element, self.label)
        self.calls += 1
