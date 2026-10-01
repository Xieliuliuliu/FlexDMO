"""Read single-file algorithm signatures without importing user code."""
import ast
import json
import math
from pathlib import Path

RESERVED = {"state", "pip", "mode", "seed"}


def _literal(node, label):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        raise ValueError(f"{label} 请使用字面量默认值，例如 0.2、True 或 [1, 2]，不要调用函数") from None


def _annotation(node):
    if node is None:
        return {}
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        node = ast.parse(node.value, mode="eval").body
    text = ast.unparse(node).replace("typing.", "")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        parts = [_annotation(node.left), _annotation(node.right)]
        typed = [p for p in parts if p.get("type") != "none"]
        if len(typed) == 1 and any(p.get("type") == "none" for p in parts):
            return dict(typed[0], nullable=True)
        raise ValueError(f"暂不支持参数类型 {text}；请使用单一类型或 类型 | None")
    if isinstance(node, ast.Subscript):
        base = ast.unparse(node.value).replace("typing.", "")
        if base == "Optional":
            return dict(_annotation(node.slice), nullable=True)
        if base == "Literal":
            choices = _literal(node.slice, "Literal")
            choices = list(choices) if isinstance(choices, tuple) else [choices]
            if not choices or any(type(v) not in (str, int, float, bool) for v in choices):
                raise ValueError("Literal 选项只支持字符串、数值和布尔值")
            if len({type(v) for v in choices}) != 1:
                raise ValueError("Literal 选项需要使用同一种类型")
            return {"type": type(choices[0]).__name__, "choices": choices}
        text = base
    aliases = {"List": "list", "Dict": "dict", "Tuple": "tuple"}
    text = aliases.get(text, text)
    if text in ("int", "float", "bool", "str", "list", "dict", "tuple"):
        return {"type": text}
    if text in ("None", "NoneType"):
        return {"type": "none", "nullable": True}
    raise ValueError(f"暂不支持参数类型 {text}；可不写注解，直接提供简单默认值")


def _parameters(node, skip):
    positional = node.args.posonlyargs + node.args.args
    aligned = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    pairs = list(zip(positional, aligned)) + list(zip(node.args.kwonlyargs, node.args.kw_defaults))
    result, specs = {}, {}
    for argument, default_node in pairs:
        key = argument.arg
        if key in skip:
            continue
        if argument in node.args.posonlyargs:
            raise ValueError(f"参数 {key} 不能限定为仅位置参数，平台需要按名称传参")
        required = default_node is None
        default = None if required else _literal(default_node, key)
        spec = _annotation(argument.annotation)
        if not spec:
            if default is None:
                if required:
                    raise ValueError(f"必填参数 {key} 需要类型注解，例如 {key}: float")
                spec = {"type": "str", "nullable": True}
            elif type(default) in (str, int, float, bool, list, dict, tuple):
                spec = {"type": type(default).__name__}
            else:
                raise ValueError(f"参数 {key} 的默认值类型不支持")
        if isinstance(default, float) and not math.isfinite(default):
            raise ValueError(f"参数 {key} 的默认值不能为 NaN/Inf")
        if default is None and not required:
            spec["nullable"] = True
        if not required and default is not None:
            expected = spec["type"]
            valid = (type(default) in (int, float) if expected == "float" else
                     type(default).__name__ == expected)
            if not valid or "choices" in spec and default not in spec["choices"]:
                raise ValueError(f"参数 {key} 的默认值与类型/选项注解不一致")
        try:
            json.dumps(default, allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError(f"参数 {key} 的默认值需为可保存的有限数值或 JSON 数据") from None
        spec["required"] = required
        result[key], specs[key] = default, spec
    return result, specs


def _validate_callback(node, names, method=False):
    if isinstance(node, ast.AsyncFunctionDef):
        raise ValueError("算法接口需要普通 def，不支持 async def")
    args = node.args.posonlyargs + node.args.args
    if method:
        if not args or args[0].arg != "self":
            raise ValueError(f"{node.name} 必须是普通实例方法，以 self 开头")
        args = args[1:]
    if len(args) < len(names):
        raise ValueError(f"接口应为 {node.name}({', '.join(['self'] * method + names)}, ...)")
    return [a.arg for a in args[:len(names)]]


def inspect_code(path, kind, source=None):
    """Return a JSON-serializable record; no decorators/defaults/imports execute."""
    path = Path(path)
    if kind not in ("dynamic", "search"):
        raise ValueError("只支持动态响应策略和搜索算法")
    if not path.stem.isidentifier() or path.stem.startswith("_"):
        raise ValueError("文件名需为 Python 标识符，不能以 _ 开头")
    tree = ast.parse(source if source is not None else path.read_text(encoding="utf-8-sig"), filename=str(path))
    hook = "response" if kind == "dynamic" else "step"
    candidates = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == hook:
            candidates.append((node, None, hook))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            methods = {n.name: n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            api = hook if hook in methods else "optimize" if kind == "search" and "optimize" in methods else None
            if api:
                candidates.append((methods[api], node, api))
    metadata = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("NAME", "YEAR", "ALGORITHM"):
                    metadata[target.id] = _literal(node.value, target.id)
    if "ALGORITHM" in metadata:
        candidates = [c for c in candidates if (c[1].name if c[1] else c[0].name) == metadata["ALGORITHM"]]
    if len(candidates) != 1:
        raise ValueError(f"需要唯一的 {hook} 函数/类" + (" 或 optimize 类" if kind == "search" else "") +
                         "；多个入口时可写 ALGORITHM = '类名'")
    callback, cls, api = candidates[0]
    names = ["problem", "response_strategy"] if api == "optimize" else ["population", "problem"]
    if kind == "dynamic":
        # algorithm is optional for the simple response hook.
        args = callback.args.posonlyargs + callback.args.args
        offset = 1 if cls else 0
        if len(args) > offset + 2 and args[offset + 2].arg == "algorithm":
            names.append("algorithm")
    names = _validate_callback(callback, names, bool(cls))
    if cls:
        constructors = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"]
        if constructors:
            params, specs = _parameters(constructors[0], {"self"} | (RESERVED if kind == "search" else set()))
        else:
            params, specs = {}, {}
        extras, _ = _parameters(callback, {"self"} | set(names))
        if extras:
            raise ValueError("类方法的可配置参数请放在 __init__，不要重复放在运行接口中")
    else:
        params, specs = _parameters(callback, set(names))
        if kind == "search" and RESERVED.intersection(params):
            raise ValueError("step 的 seed/state/pip/mode 由平台管理，不要声明为算法参数")
    if kind == "search":
        params = {"seed": 1, **params}
        specs["seed"] = {"type": "int", "required": False}
    name = metadata.get("NAME", cls.name if cls else path.stem)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("NAME 必须是非空字符串")
    return {"folder_name": str(path.resolve()), "source_file": str(path.resolve()),
            "format": "python-file", "kind": kind, "name": name.strip(), "year": metadata.get("YEAR", ""),
            "entry_name": cls.name if cls else callback.name, "class_name": cls.name if cls else path.stem,
            "api": api, "is_class": bool(cls), "callback_args": names, "defaults": params,
            "parameter_specs": specs, "description": ast.get_docstring(cls or callback) or "",
            "parameter_labels": {}, "line": callback.lineno}
