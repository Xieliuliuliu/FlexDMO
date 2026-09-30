"""Desktop-only responsive layout verification, optionally with screenshots."""
from pathlib import Path
import sys
import subprocess
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run_smoke():
    import main
    from views.common.GlobalVar import global_vars
    from views.components.scrolled_frame import NativeScrolledFrame

    errors = []
    completed = []
    panel_snapshots = {}
    original = tk.Tk.mainloop
    sizes = [(1600, 900, "wide"), (1300, 760, "standard"),
             (1000, 680, "compact"), (720, 520, "tabs"), (1600, 900, "wide")]

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    def smoke_loop(root, *args, **kwargs):
        def fail(kind, value, traceback):
            errors.append(value)
            root.event_generate('<<CloseApp>>')
        root.report_callback_exception = fail

        def resize(module, index):
            width, height, mode = sizes[index]
            root.geometry(f'{width}x{height}')
            root.after(250, lambda: check(module, index, mode))

        def check(module, index, mode):
            state = global_vars[module]
            workspace = state['workspace']
            assert workspace.mode == mode, (workspace.mode, mode)
            original_panels = tuple(workspace.panels)
            if module not in panel_snapshots:
                panel_snapshots[module] = original_panels
            assert original_panels == panel_snapshots[module], 'resize rebuilt panels'
            assert 'problem_description_label' not in global_vars['test_module']
            for panel_index, panel in enumerate(workspace.panels):
                workspace.show_panel(panel_index)
                root.update_idletasks()
                assert panel.winfo_viewable(), (module, mode, panel_index)
                left = panel.winfo_rootx()
                right = left + panel.winfo_width()
                assert left >= workspace.winfo_rootx()
                assert right <= workspace.winfo_rootx() + workspace.winfo_width()
                for widget in descendants(panel):
                    if isinstance(widget, NativeScrolledFrame):
                        widget.yview('scroll', '3.0', 'units')
                        widget.yview('scroll', '-3.0', 'units')
                    if isinstance(widget, ttk.Entry) and widget.winfo_viewable():
                        assert widget.winfo_rootx() >= left, (mode, widget)
                        assert widget.winfo_rootx() + widget.winfo_width() <= right, (mode, widget)
                        ancestor = widget.master
                        while ancestor is not panel and ancestor is not None:
                            if isinstance(ancestor, NativeScrolledFrame):
                                viewport_right = ancestor.winfo_rootx() + ancestor.winfo_width()
                                assert widget.winfo_rootx() + widget.winfo_width() <= viewport_right, ('entry under scrollbar', mode, widget)
                                break
                            ancestor = ancestor.master
                    if isinstance(widget, ttk.Label) and widget.winfo_viewable() and widget.grid_info():
                        assert widget.winfo_width() >= min(widget.winfo_reqwidth(), 120), (mode, widget.cget('text'))
                    if isinstance(widget, ttk.Button) and module == 'test_module' and widget.cget('text') == '加载并回放':
                        assert widget.winfo_rooty() - panel.winfo_rooty() < 150, 'file controls stretched vertically'
            if module == 'test_module':
                workspace.show_panel(2)
                root.update_idletasks()
                canvas = state['canvas']
                assert canvas.figure.dpi == 100 * canvas.device_pixel_ratio, 'native manager DPI leaked into Tk'
                canvas.draw()
                renderer = canvas.get_renderer()
                for ax in canvas.figure.axes:
                    for label in ax.get_xticklabels() + ax.get_yticklabels():
                        bbox = label.get_window_extent(renderer)
                        assert bbox.x0 >= -1 and bbox.y0 >= -1, ('chart label clipped', mode, bbox)
                        assert bbox.x1 <= canvas.figure.bbox.width + 1 and bbox.y1 <= canvas.figure.bbox.height + 1, ('chart label clipped', mode, bbox)
                if '--charts' in sys.argv and index < 4:
                    output = Path('results/ui-preview')
                    output.mkdir(parents=True, exist_ok=True)
                    canvas.figure.savefig(output / f'chart-{mode}.png')
            assert tuple(workspace.panels) == original_panels
            if '--screenshots' in sys.argv and module == 'test_module' and index < 4:
                workspace.show_panel(1 if mode == 'tabs' else 2)
                if mode != 'wide':
                    workspace.settings_tabs.select(workspace.panels[1]) if mode != 'tabs' else None
                root.update_idletasks()
                from PIL import ImageGrab
                output = Path('results/ui-preview')
                output.mkdir(parents=True, exist_ok=True)
                bbox = (root.winfo_rootx(), root.winfo_rooty(),
                        root.winfo_rootx() + root.winfo_width(),
                        root.winfo_rooty() + root.winfo_height())
                try:
                    ImageGrab.grab(bbox=bbox).save(output / f'{mode}.png')
                except (OSError, subprocess.SubprocessError) as error:
                    print('Screenshot unavailable; geometry checks still ran:', error, flush=True)
            print('LAYOUT_OK', module, sizes[index][:2], mode, flush=True)
            if index + 1 < len(sizes):
                resize(module, index + 1)
            elif module == 'test_module':
                global_vars['test_module']['selected_module'].set('Experiment Module')
                root.after(250, lambda: resize('experiment_module', 0))
            else:
                completed.append(True)
                root.event_generate('<<CloseApp>>')

        root.after(300, lambda: resize('test_module', 0))
        original(root, *args, **kwargs)

    with patch.object(tk.Tk, 'mainloop', smoke_loop):
        main.main()
    if errors:
        raise RuntimeError(errors)
    if not completed:
        raise RuntimeError('layout test did not complete')


if __name__ == '__main__':
    run_smoke()
