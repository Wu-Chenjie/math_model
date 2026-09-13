# -*- coding: utf-8 -*-
"""配置加载: 分层合并 CLI 参数 > 环境变量 > 用户配置 > 默认配置。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

def _package_root() -> Path:
    """包根目录 (26B-team/)。

    允许用环境变量 ``MOCKSIM_PKG_ROOT`` 覆盖, 这样打包脚本可以在"暂存目录还没被
    安装/复制成最终位置"时, 直接对这个目录生成配置模板。
    """
    override = os.environ.get("MOCKSIM_PKG_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent


#: 包根目录 (26B-team/)
ROOT = _package_root()
CONFIG_DIR = ROOT / "config"
TEAM_CONFIG = CONFIG_DIR / "team.json"
DEFAULTS_CONFIG = CONFIG_DIR / "defaults.json"

TEAM_CONFIG_TEMPLATE: dict[str, Any] = {
    "_说明": "每位队员把 team_id 改成自己在竞赛系统里的参赛队号；该文件不要提交到公共仓库",
    "team_id": "TEAM0000",
    "team_name": "",
    "member": "",
    "team_check_enabled": True,
}

DEFAULTS_CONFIG_TEMPLATE: dict[str, Any] = {
    "_说明": "通用默认值；命令行参数优先级更高",
    "default_problem": 3,
    "port": 2026,
    "real_limit_s": 1200,
    "window_s": 1500,
    "out_dir": "runs",
    "seed": None,
    "count": None,
    "strategy": "BaselineSweep",
    "verbose": True,
}


def _read_text(path: Path) -> str:
    """读取配置文本; 用 utf-8-sig 兼容带不带 BOM 的文件。

    Windows 上用 PowerShell 的 Set-Content/Out-File 写 JSON 很容易带上 BOM,
    而 JSON 解析器不接受 BOM, 所以这里统一按 utf-8-sig 解码。
    """
    return path.read_text(encoding="utf-8-sig")


def _read_json(path: Path, template: dict[str, Any], *, create: bool) -> dict[str, Any]:
    if not path.exists():
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(template, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        return dict(template)
    try:
        data = json.loads(_read_text(path))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SystemExit(
            f"配置文件格式错误: {path}\n  {exc}\n"
            f"  提示: JSON 文件必须是不带 BOM 的 UTF-8; 删掉这个文件重新运行 doctor "
            f"会自动生成模板。"
        ) from exc
    if not isinstance(data, dict):
        raise SystemExit(f"配置文件必须是 JSON 对象: {path}")
    return {k: v for k, v in data.items() if not k.startswith("_")}


@dataclass
class Config:
    team_id: str = "TEAM0000"
    team_name: str = ""
    member: str = ""
    team_check_enabled: bool = True
    default_problem: int = 3
    port: int = 2026
    real_limit_s: float = 1200.0
    window_s: float = 1500.0
    out_dir: str = "runs"
    seed: int | None = None
    count: int | None = None
    strategy: str = "BaselineSweep"
    verbose: bool = True
    sources: list[str] = field(default_factory=list)

    def resolved_out_dir(self) -> Path:
        p = Path(self.out_dir)
        return p if p.is_absolute() else ROOT / p


def load(*, create_missing: bool = True, overrides: dict[str, Any] | None = None) -> Config:
    """读取配置并合并覆盖值 (通常来自命令行)。"""
    defaults = _read_json(DEFAULTS_CONFIG, DEFAULTS_CONFIG_TEMPLATE, create=create_missing)
    team = _read_json(TEAM_CONFIG, TEAM_CONFIG_TEMPLATE, create=create_missing)

    merged: dict[str, Any] = {}
    sources: list[str] = []
    merged.update(defaults)
    sources.append(str(DEFAULTS_CONFIG))
    # 环境变量可覆盖 (便于 CI / 多队员共用一台机器)
    env_map = {
        "DSH_B_TEAM_ID": "team_id",
        "DSH_B_PROBLEM": "default_problem",
        "DSH_B_PORT": "port",
    }
    for env_key, cfg_key in env_map.items():
        if os.environ.get(env_key):
            merged[cfg_key] = os.environ[env_key]
            sources.append(f"env:{env_key}")
    merged.update(team)
    sources.append(str(TEAM_CONFIG))
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})
        sources.append("command line")

    cfg = Config(**{k: v for k, v in merged.items() if k in Config.__dataclass_fields__})
    cfg.sources = sources
    cfg.port = int(cfg.port)
    cfg.default_problem = int(cfg.default_problem)
    cfg.real_limit_s = float(cfg.real_limit_s)
    cfg.window_s = float(cfg.window_s)
    if cfg.seed is not None:
        cfg.seed = int(cfg.seed)
    if cfg.count is not None:
        cfg.count = int(cfg.count)
    return cfg


def ensure_config_files() -> list[Path]:
    """确保 config/ 下的模板文件存在, 返回新建的文件列表。"""
    created: list[Path] = []
    for path, tpl in ((TEAM_CONFIG, TEAM_CONFIG_TEMPLATE),
                      (DEFAULTS_CONFIG, DEFAULTS_CONFIG_TEMPLATE)):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(tpl, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            created.append(path)
    return created


def team_is_configured() -> bool:
    """team_id 是否已从占位值改成真实参赛队号。"""
    if not TEAM_CONFIG.exists():
        return False
    try:
        data = json.loads(_read_text(TEAM_CONFIG))
    except Exception:
        return False
    tid = str(data.get("team_id", ""))
    return bool(tid) and tid != TEAM_CONFIG_TEMPLATE["team_id"]
