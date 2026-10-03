"""Shared ordering and labels for test and batch component selection."""


def component_year(record):
    value = record.get("year")
    if record.get("publication_type") == "baseline" or isinstance(value, bool):
        return None
    text = str(value or "").strip()
    return int(text) if text.isdigit() and len(text) == 4 else None


def component_sort_key(record):
    year = component_year(record)
    return (year is None, -(year or 0), record["name"].casefold())


def ordered_registry(registry):
    return {kind: sorted(rows, key=component_sort_key) if kind in ("dynamic", "search") else rows
            for kind, rows in registry.items()}


def choice_label(kind, record):
    if kind == "problem":
        suffix = "有约束" if record["constraints"] else "无约束"
    else:
        year = component_year(record)
        suffix = str(year) if year else "基线" if record.get("publication_type") == "baseline" else "年份未注明"
    return record["name"] + " · " + suffix + (" · 起步模板" if record.get("template") else "")
