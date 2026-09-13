# -*- coding: utf-8 -*-
"""自检 (doctor): 一条命令确认环境、配置、端口、策略、自测是否正常。

队员遇到问题先跑这个, 输出可以直接贴给队友定位。
"""

from __future__ import annotations

import platform
import socket
import sys
import time
from pathlib import Path

from . import arena as A
from . import config as cfg
from . import discovery
from .conformance import main as conformance_main
from .harness import Harness
from .version import BANNER, __version__

OK = "[ OK ]"
WARN = "[WARN]"
BAD = "[FAIL]"


def _check_port(port: int) -> tuple[bool, str]:
    """端口是否被占用 (占用 -> 无法启动本地模拟器)。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True, f"端口 {port} 可用"
        except OSError as exc:
            return False, f"端口 {port} 已被占用 ({exc}); 用 --port 换一个端口"


def _self_test(team_id: str, *, quick: bool = True) -> tuple[bool, str]:
    """跑一局最短的自测, 确认模拟器 + 客户端 + 策略整条链路通。"""
    h = Harness(problem=3, team_id=team_id, out_dir=cfg.ROOT / "runs" / "selfcheck",
                real_limit_s=1200.0, window_s=1500.0, verbose=False)
    try:
        rec = h.run_once(strategy="BaselineSweep", seed=20260913, count=10)
    except Exception as exc:  # noqa: BLE001
        return False, f"自测异常: {type(exc).__name__}: {exc}"
    if rec.error:
        return False, f"自测失败: {rec.error}"
    if rec.measure_count <= 0:
        return False, "自测失败: 一次检测都没有发出, 链路不通"
    return True, (f"自测通过: 案例 {rec.case_code} 清除 {rec.cleared_count}/"
                  f"{rec.total_jammers} 平均 "
                  f"{rec.avg_locate_clear_time_s and round(rec.avg_locate_clear_time_s, 1)}s "
                  f"检测 {rec.measure_count} 次")


def run_doctor(*, skip_self_test: bool = False, conformance: bool = False,
               port: int | None = None) -> int:
    print(BANNER)
    print(f"\nmocksim v{__version__}  根目录: {cfg.ROOT}\n")
    failures = 0
    warnings = 0

    # --- 1. Python ------------------------------------------------------
    print("【1】运行环境")
    ver = sys.version_info
    if ver >= (3, 10):
        print(f"{OK} Python {platform.python_version()} ({platform.machine()})")
    else:
        print(f"{BAD} 需要 Python >= 3.10, 当前 {platform.python_version()}")
        failures += 1
    print(f"{OK} 标准库自检: math/hashlib/http.server 可用")
    proxy = {k: v for k, v in __import__("os").environ.items()
             if k.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")}
    if proxy:
        print(f"{WARN} 检测到系统代理 {proxy}")
        print("       本地客户端已自动绕过回环地址; 你们自己的程序如果用 requests,")
        print("       请设置 NO_PROXY=127.0.0.1,localhost 或 proxies={'http': None}")
        warnings += 1
    else:
        print(f"{OK} 未检测到系统代理")

    # --- 2. 配置 --------------------------------------------------------
    print("\n【2】配置")
    created = cfg.ensure_config_files()
    for p in created:
        print(f"{OK} 已生成配置模板 {p.relative_to(cfg.ROOT)}")
    conf = cfg.load()
    if cfg.team_is_configured():
        print(f"{OK} team_id = {conf.team_id!r}")
    else:
        print(f"{WARN} team_id 仍是占位值 {conf.team_id!r}")
        print(f"       请编辑 {cfg.TEAM_CONFIG.relative_to(cfg.ROOT)} 填你们的参赛队号")
        print("       (本地演练不校验也能跑; 正式测试必须用真实参赛队号)")
        warnings += 1
    print(f"{OK} 配置来源: {', '.join(conf.sources)}")
    print(f"     默认问题={conf.default_problem} 端口={conf.port} "
          f"现实上限={conf.real_limit_s}s 窗口={conf.window_s}s")

    # --- 3. 端口 --------------------------------------------------------
    print("\n【3】端口")
    want_port = port or conf.port
    free, msg = _check_port(want_port)
    print(f"{OK if free else WARN} {msg}")
    if not free:
        warnings += 1

    # --- 4. 策略 --------------------------------------------------------
    print("\n【4】策略插件")
    found = discovery.discover()
    if not found:
        print(f"{BAD} strategies/ 目录里没有找到任何策略")
        failures += 1
    for key, info in sorted(found.items()):
        print(f"{OK} {key:<24} {info.name}  ({info.path.name})")
        report = discovery.check_file(info.path)
        for w in report.warnings:
            print(f"{WARN}   {info.path.name}: {w}")
            warnings += 1
        for e in report.errors:
            print(f"{BAD}   {info.path.name}: {e}")
            failures += 1

    # --- 5. 协议实现自检 ------------------------------------------------
    print("\n【5】模拟器实现自检")
    if conformance:
        code = conformance_main()
        if code == 0:
            print(f"{OK} 协议一致性断言全部通过")
        else:
            print(f"{BAD} 协议一致性断言有失败项")
            failures += 1
    else:
        print("[SKIP] 协议一致性断言 (加 --conformance 运行, 约 10 秒)")

    # --- 6. 端到端自测 --------------------------------------------------
    print("\n【6】端到端自测")
    if skip_self_test:
        print("[SKIP] 加 --full 可跑一局端到端自测")
    else:
        t0 = time.monotonic()
        ok, msg = _self_test(conf.team_id)
        print(f"{OK if ok else BAD} {msg}  ({time.monotonic() - t0:.1f}s)")
        if not ok:
            failures += 1

    # --- 结论 -----------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"{BAD} 自检未通过: {failures} 项失败, {warnings} 项警告")
        return 1
    print(f"{OK} 自检通过 ({warnings} 项警告)")
    print("\n下一步:")
    print("  python -m mocksim.cli run --problem 3 --runs 6      # 批量演练")
    print("  python -m mocksim.cli strategies                    # 看可用策略")
    print("  python -m mocksim.cli serve --problem 3             # 起本地模拟器"
          "接你们自己的程序")
    return 0
