from ttkbootstrap.scrolled import ScrolledFrame


class NativeScrolledFrame(ScrolledFrame):
    """Tk 9 / macOS scrollbars can send decimal scroll amounts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ttkbootstrap places content across the full container width, under
        # its packed scrollbar. Reserve a gutter even when it is auto-hidden.
        self.content_place_configure(width=-self.vscroll.winfo_reqwidth())

    def yview(self, *args):
        if args and args[0] == 'scroll':
            self.yview_scroll(number=float(args[1]), what=args[2])
            return
        return super().yview(*args)
