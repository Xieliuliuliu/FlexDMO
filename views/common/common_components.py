import ttkbootstrap as ttk


def create_column(frame_main, pos):
    """根据位置创建列"""
    frame = ttk.Frame(frame_main)
    frame.grid(row=0, column=pos, sticky="nsew", padx=10)  # Use grid instead of pack
    return frame


def create_separator(frame, pos):
    """Create a vertical separator between columns."""
    separator = ttk.Separator(frame, orient="vertical")
    separator.grid(row=0, column=pos, sticky="nsew", padx=0, pady=0)  # No padding added
    return separator