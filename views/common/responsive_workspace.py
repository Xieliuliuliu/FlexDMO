"""Reflow existing panels without rebuilding widgets or losing run state."""
from tkinter import ttk

from views.components.scrolled_frame import NativeScrolledFrame as ScrolledFrame


def workspace_mode(width):
    if width >= 1550:
        return "wide"
    if width >= 1250:
        return "standard"
    if width >= 900:
        return "compact"
    return "tabs"


def scrollable_content(panel):
    scroll = ScrolledFrame(panel, autohide=True, width=280, height=100)
    scroll.pack(fill="both", expand=True)
    content = ttk.Frame(scroll, padding=(6, 0))
    content.pack(fill="both", expand=True)
    return content


class ResponsiveWorkspace(ttk.Frame):
    def __init__(self, parent, titles):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        self.panels = [ttk.Frame(self, width=280, height=100) for _ in titles]
        for panel in self.panels:
            panel.pack_propagate(False)
        self.titles = titles
        self.settings_tabs = ttk.Notebook(self)
        self.output_tabs = ttk.Notebook(self)
        self.all_tabs = ttk.Notebook(self)
        self.mode = None
        self._resize_job = None
        self._selected = 0
        for notebook in (self.settings_tabs, self.output_tabs, self.all_tabs):
            notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed, add='+')
        self.bind("<Configure>", self._on_resize, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _on_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(60, self.reflow)

    def _on_destroy(self, event):
        if event.widget is self and self._resize_job is not None:
            self.after_cancel(self._resize_job)
            self._resize_job = None

    def _on_tab_changed(self, event):
        if event.widget.winfo_ismapped():
            pane = event.widget.select()
            for index, panel in enumerate(self.panels):
                if str(panel) == pane:
                    self._selected = index
                    break

    def reflow(self, width=None):
        self._resize_job = None
        mode = workspace_mode(self.winfo_width() if width is None else width)
        if mode == self.mode:
            return
        selected_panes = [notebook.select() for notebook in
                          (self.settings_tabs, self.output_tabs, self.all_tabs)
                          if notebook.tabs()]
        for notebook in (self.settings_tabs, self.output_tabs, self.all_tabs):
            for pane in notebook.tabs():
                notebook.forget(pane)
            notebook.grid_forget()
        for panel in self.panels:
            panel.grid_forget()
        for column in range(4):
            self.columnconfigure(column, weight=0, minsize=0)
        self.rowconfigure(0, weight=1)

        def place(widget, column, weight, minimum=0):
            self.columnconfigure(column, weight=weight, minsize=minimum)
            widget.grid(row=0, column=column, sticky="nsew", padx=4)

        def tabs(notebook, indexes):
            for index in indexes:
                notebook.add(self.panels[index], text=self.titles[index])

        if mode == "wide":
            for index, (weight, minimum) in enumerate(((0, 300), (0, 270), (1, 480), (0, 280))):
                place(self.panels[index], index, weight, minimum)
        elif mode == "standard":
            tabs(self.settings_tabs, (0, 1))
            place(self.settings_tabs, 0, 0, 320)
            place(self.panels[2], 1, 1, 480)
            place(self.panels[3], 2, 0, 280)
        elif mode == "compact":
            tabs(self.settings_tabs, (0, 1))
            tabs(self.output_tabs, (2, 3))
            place(self.settings_tabs, 0, 0, 320)
            place(self.output_tabs, 1, 1, 480)
        else:
            tabs(self.all_tabs, range(4))
            place(self.all_tabs, 0, 1)
        self.mode = mode
        for notebook in (self.settings_tabs, self.output_tabs, self.all_tabs):
            for pane in selected_panes:
                if pane in notebook.tabs():
                    notebook.select(pane)
        self.show_panel(self._selected)

    def show_panel(self, index):
        self._selected = index
        for notebook in (self.settings_tabs, self.output_tabs, self.all_tabs):
            if str(self.panels[index]) in notebook.tabs():
                notebook.select(self.panels[index])
