# -*- coding: utf-8 -*-
"""策略插件发现与合规检查。

队员只需要把策略文件放进 ``strategies/`` 目录 (或在 config 里指定路径),
本模块负责加载、实例化、以及做一次"是否偷看真值"的静态检查。
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import ROOT

STRATEGY_DIR = ROOT / "strategies"

#: 策略只应该使用接口返回的信息。以下模式说明程序在偷看真值或在绕过接口,
#: 本地演练会因此失真, 到官方模拟器上必然失效。
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"/debug/", "访问模拟器调试接口 (官方模拟器没有该接口)"),
    (r"mocksim\.arena", "直接导入仿真内核读取真值"),
    (r"mocksim\.server", "直接导入模拟器内部状态读取真值"),
    (r"\bcase\.jammers\b", "直接读取案例真值"),
    (r"\btruth_table\b", "直接读取案例真值"),
]

#: 这些名字出现在策略文件里通常是"把真值硬编码进去"的迹象
SUSPICIOUS_HARDCODE = re.compile(
    r"(?<![A-Za-z0-9_])(?:x|y|x_true|y_true|true_x|true_y)\s*=\s*[-+]?\d{3,}",
    re.IGNORECASE,
)


@dataclass
class StrategyInfo:
    key: str
    name: str
    cls: type
    path: Path
    description: str = ""
    warnings: list[str] = field(default_factory=list)

    def factory(self) -> Callable[[], Any]:
        return lambda: self.cls()


@dataclass
class CheckReport:
    path: Path
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _module_name_for(path: Path) -> str:
    return "team_strategy_" + re.sub(r"\W+", "_", path.stem)


def _load_module(path: Path) -> Any:
    name = _module_name_for(path)
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载策略文件: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # 让策略文件可以直接 import 到包内的 client/harness
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(module)
    return module


def check_file(path: Path) -> CheckReport:
    """静态检查: 是否偷看真值、是否有可疑硬编码、是否能被导入。"""
    report = CheckReport(path=path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.errors.append(f"无法读取文件: {exc}")
        return report

    for pattern, why in FORBIDDEN_PATTERNS:
        for m in re.finditer(pattern, source):
            line = source[:m.start()].count("\n") + 1
            report.errors.append(f"第 {line} 行: {why} —— 策略只能使用接口返回的信息")
    for m in SUSPICIOUS_HARDCODE.finditer(source):
        line = source[:m.start()].count("\n") + 1
        report.warnings.append(
            f"第 {line} 行: 疑似硬编码坐标 `{m.group(0).strip()}`; "
            f"如果这是写死的干扰源位置, 正式测试必然失效"
        )

    try:
        module = _load_module(path)
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"导入失败: {type(exc).__name__}: {exc}")
        return report
    if not find_strategies(module):
        report.errors.append(
            "没有找到任何策略类。策略类需要提供 run(self, client, "
            "deadline_real_s=None, verbose=True) 方法"
        )
    return report


def find_strategies(module: Any) -> list[type]:
    """在模块中寻找符合约定的策略类。"""
    out: list[type] = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue                      # 排除 import 进来的类
        if obj.__name__.startswith("_"):
            continue
        run = getattr(obj, "run", None)
        if callable(run) and "client" in inspect.signature(run).parameters:
            out.append(obj)
    return out


def discover(*, extra_paths: list[Path] | None = None) -> dict[str, StrategyInfo]:
    """扫描 strategies/ 目录, 返回 {key: StrategyInfo}。"""
    paths: list[Path] = []
    if STRATEGY_DIR.exists():
        paths.extend(sorted(p for p in STRATEGY_DIR.glob("*.py")
                            if not p.name.startswith("_")))
    for p in extra_paths or []:
        p = Path(p)
        if p.is_dir():
            paths.extend(sorted(x for x in p.glob("*.py") if not x.name.startswith("_")))
        elif p.exists():
            paths.append(p)

    found: dict[str, StrategyInfo] = {}
    for path in paths:
        try:
            module = _load_module(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] 跳过 {path.name}: {type(exc).__name__}: {exc}")
            continue
        # 允许策略文件用模块级 display_name 给整个文件起中文名
        module_display = getattr(module, "display_name", None)
        for cls in find_strategies(module):
            key = cls.__name__
            found[key] = StrategyInfo(
                key=key,
                name=getattr(cls, "display_name", None) or module_display or key,
                cls=cls,
                path=path,
                description=(inspect.getdoc(cls) or "").strip().split("\n")[0],
            )
    return found


def resolve(key: str, *, extra_paths: list[Path] | None = None) -> StrategyInfo:
    """按名字取策略; 支持 ``文件名.py`` 或 ``文件名`` 兜底。"""
    found = discover(extra_paths=extra_paths)
    if key in found:
        return found[key]
    # 允许 "my_strategy.py" 或 "my_strategy" 这种写法: 取该文件里的第一个策略
    for info in found.values():
        if info.path.stem == key or info.path.name == key:
            return info
    available = ", ".join(sorted(found)) or "(strategies/ 目录为空)"
    raise SystemExit(f"找不到策略 {key!r}。可用策略: {available}")
