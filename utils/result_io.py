"""Headless result loading for statistical reports.

Desktop replay and statistics use the same validated snapshot reader.
No application window, global UI state, or optional algorithm library is loaded.
"""
import os
from pathlib import Path
import warnings

from flexdmo_app.core import load_frames


def load_result_from_files(input_paths, *, on_error=None):
    """Yield validated results from JSON files or recursively scanned directories.

    Inputs may be one path or an iterable of paths. Overlapping inputs are
    deduplicated, and directory contents are processed in deterministic order.
    Invalid files are skipped with a warning, or reported through
    on_error(path, exception). Errors raised by that callback propagate.
    """
    if isinstance(input_paths, (str, os.PathLike)):
        input_paths = [input_paths]
    seen = set()

    def report(path, error):
        if on_error is None:
            warnings.warn(f"无法读取结果 {path}：{error}", RuntimeWarning, stacklevel=3)
        else:
            on_error(path, error)

    for raw_path in input_paths:
        path = Path(raw_path)
        try:
            if path.is_dir():
                paths = sorted(p for p in path.rglob("*")
                               if p.is_file() and p.suffix.lower() == ".json")
            elif path.is_file():
                paths = [path] if path.suffix.lower() == ".json" else []
            else:
                raise FileNotFoundError(f"结果路径不存在：{path}")
        except OSError as error:
            report(path, error)
            continue
        for candidate in paths:
            try:
                canonical = candidate.resolve()
                if canonical in seen:
                    continue
                seen.add(canonical)
                frames = load_frames(candidate)
            except (OSError, ValueError, TypeError, KeyError, ImportError) as error:
                report(candidate, error)
                continue
            runtime = {}
            for frame in frames:
                runtime.setdefault(frame["t"], {})[frame["evaluate_times"]] = frame
            yield {"settings": frames[0]["settings"],
                   "runtime_populations": runtime, "file_path": str(candidate)}
