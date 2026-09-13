# -*- coding: utf-8 -*-
"""统一命令行入口。

    python -m mocksim.cli doctor                  # 环境自检
    python -m mocksim.cli strategies              # 列出可用策略
    python -m mocksim.cli run --problem 3 --runs 6
    python -m mocksim.cli serve --problem 3
    python -m mocksim.cli compare --left BaselineSweep --right MyStrategy
    python -m mocksim.cli conformance             # 协议一致性断言
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as cfg
from . import discovery
from .harness import Harness, compare
from .version import BANNER, FORMAL_TEST_ADVICE, FORMAL_TEST_DEADLINE, __version__


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--problem", type=int, choices=(3, 4),
                   help="题目编号: 3=全向源, 4=全向+定向混合")
    p.add_argument("--team", dest="team_id", help="robot_id (默认取 config/team.json)")
    p.add_argument("--real-limit", type=float, dest="real_limit_s",
                   help="/enter 后的现实时间上限秒数 (默认 1200)")
    p.add_argument("--window", type=float, dest="window_s",
                   help="测试窗口秒数 (默认 1500=25 分钟)")


def _parse_kwargs(text: str | None) -> dict:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--strategy-kwargs 必须是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("--strategy-kwargs 必须是 JSON 对象, 例如 '{\"coarse_points\":18}'")
    return data


def _fmt_strategy_table(found: dict) -> str:
    if not found:
        return "（strategies/ 目录里没有找到策略, 参考 strategies/_template.py）"
    width = max(len(k) for k in found)
    lines = []
    for key, info in sorted(found.items()):
        lines.append(f"  {key:<{width}}  {info.name:<18} {info.description}")
        lines.append(f"  {'':<{width}}  文件: {info.path.name}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m mocksim.cli",
        description="26B 本地测试环境 (mock 模拟器, 不消耗官方正式测试机会)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"提示: 官方模拟器 {FORMAL_TEST_DEADLINE} (北京时间) 后无法新开测试, "
               f"建议 {FORMAL_TEST_ADVICE} 前完成正式测试。",
    )
    ap.add_argument("--version", action="version", version=f"mocksim {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # doctor
    d = sub.add_parser("doctor", help="环境自检 (先跑这个)")
    d.add_argument("--full", action="store_true", help="包含端到端自测")
    d.add_argument("--conformance", action="store_true", help="包含协议一致性断言")
    d.add_argument("--port", type=int)

    # strategies
    sub.add_parser("strategies", help="列出 strategies/ 里的策略")

    # conformance
    sub.add_parser("conformance", help="协议一致性断言 (对标附件2)")

    # run
    r = sub.add_parser("run", help="批量演练并出统计/表1/日志")
    _add_common(r)
    r.add_argument("--strategy", default=None, help="策略名 (默认取 config/defaults.json)")
    r.add_argument("--runs", type=int, default=6, help="跑几局 (默认 6)")
    r.add_argument("--mode", default="practice", choices=("practice", "formal"),
                   help="practice=演练(显示真值), formal=模拟正式测试(不显示真值)")
    r.add_argument("--seeds", type=int, nargs="*", help="指定案例 seed, 可复现")
    r.add_argument("--counts", type=int, nargs="*", help="指定干扰源个数 10..16")
    r.add_argument("--strategy-kwargs", default=None,
                   help="策略构造参数 JSON, 例如 '{\"coarse_points\":20}'")
    r.add_argument("--out", default=None, help="输出目录 (默认 runs/<问题>)")
    r.add_argument("--quiet", action="store_true")
    r.add_argument("--json", dest="json_out", action="store_true",
                   help="最后打印机器可读的汇总 JSON")

    # compare
    c = sub.add_parser("compare", help="同一批 seed 下对比两个策略")
    _add_common(c)
    c.add_argument("--left", default="BaselineSweep")
    c.add_argument("--right", required=True)
    c.add_argument("--seeds", type=int, nargs="+", required=True)
    c.add_argument("--left-kwargs", default=None)
    c.add_argument("--right-kwargs", default=None)
    c.add_argument("--out", default=None)

    # serve
    s = sub.add_parser("serve", help="起本地模拟器, 接你们自己的机器狗程序")
    _add_common(s)
    s.add_argument("--port", type=int, help="监听端口 (默认 2026)")
    s.add_argument("--seed", type=int, help="固定案例 seed")
    s.add_argument("--count", type=int, help="干扰源个数 10..16")
    s.add_argument("--mode", default="practice", choices=("practice", "formal"))
    s.add_argument("--expose-debug", action="store_true",
                   help="开放 GET /debug/truth|status|log (仅供人工查看)")
    s.add_argument("--verbose", action="store_true", help="打印每个 HTTP 请求")

    args = ap.parse_args(argv)

    if args.cmd == "doctor":
        from .doctor import run_doctor
        return run_doctor(skip_self_test=not args.full, conformance=args.conformance,
                          port=args.port)

    if args.cmd == "conformance":
        from .conformance import main as conf_main
        return conf_main()

    if args.cmd == "strategies":
        print(BANNER)
        print("\n可用策略:\n")
        print(_fmt_strategy_table(discovery.discover()))
        print(f"\n策略目录: {discovery.STRATEGY_DIR}")
        print("新增策略: 复制 strategies/_template.py 改名并在 run() 里实现")
        return 0

    overrides = {
        "default_problem": args.problem,
        "team_id": args.team_id,
        "real_limit_s": args.real_limit_s,
        "window_s": args.window_s,
    }
    conf = cfg.load(overrides=overrides)

    if args.cmd == "run":
        out_dir = Path(args.out) if args.out else (conf.resolved_out_dir()
                                                   / f"p{conf.default_problem}")
        strategy = args.strategy or conf.strategy
        kwargs = _parse_kwargs(args.strategy_kwargs)
        print(BANNER)
        print(f"\nteam_id={conf.team_id!r}  问题={conf.default_problem}  "
              f"模式={args.mode}  策略={strategy}")
        if args.mode == "formal":
            print("注意: formal 模式不显示干扰源真值, 统计口径与官方正式测试一致")
        h = Harness(problem=conf.default_problem, team_id=conf.team_id, out_dir=out_dir,
                    real_limit_s=conf.real_limit_s, window_s=conf.window_s,
                    verbose=not args.quiet)
        try:
            h.run_batch(args.runs, strategy=strategy, mode=args.mode,
                        seeds=args.seeds, counts=args.counts, strategy_kwargs=kwargs)
        except SystemExit:
            raise
        table = h.export_results_table(out_dir / "table1-results.md", mode=args.mode)
        h.export_json(out_dir / "summary.json")

        agg = h.aggregate()
        print("\n--- 汇总 ---")
        if args.mode == "formal":
            # 正式口径: 真值不可见, 只报接口能观测到的量
            for r in h.records:
                avg = f"{r.avg_locate_clear_time_s:.2f}" if r.avg_locate_clear_time_s else "—"
                print(f"  测试{r.index}: 案例 {r.case_code} | 清除 {r.cleared_count} 个 | "
                      f"平均定位清除时间 {avg}s | 程序运行时间 {r.program_runtime_s:.2f}s")
            avgs = [r.avg_locate_clear_time_s for r in h.records if r.avg_locate_clear_time_s]
            if avgs:
                print(f"  平均: 清除 {agg['mean_clear_count']:.1f} 个 | "
                      f"平均定位清除时间 {sum(avgs) / len(avgs):.2f}s | "
                      f"平均程序运行时间 {agg['mean_program_runtime_s']:.2f}s")
            print("  (formal 模式按官方口径不显示干扰源总数, 因此无法给出清除比例)")
        elif agg.get("mean_cleared_ratio") is not None:
            print(f"  局数 {agg['runs']} | 平均清除比例 {agg['mean_cleared_ratio']:.3f} "
                  f"| 最差 {agg['worst_cleared_ratio']:.3f} "
                  f"| 满分 {agg['full_clear_runs']}/{agg['known_runs']}")
            print(f"  平均定位清除时间 {agg['mean_avg_locate_clear_time_s']:.1f}s "
                  f"| 平均检测 {agg['mean_measure_count']:.0f} 次 "
                  f"| 平均清除 {agg['mean_clear_count']:.1f} 次 "
                  f"(落空 {agg['mean_clear_miss_count']:.1f})")
        print(f"  结束原因分布: {agg.get('end_reasons')}")
        if agg.get("runs_with_error"):
            print(f"  [WARN] {agg['runs_with_error']} 局出现异常, 见下方诊断")

        print("\n--- 诊断 ---")
        print(h.diagnosis() or "(无诊断信息)")
        print(f"\n结果表: {table}")
        print(f"汇总:   {h.export_json(out_dir / 'summary.json')}")
        print(f"日志:   {out_dir}\\*.jsonl")
        if args.json_out:
            print("\n--- JSON ---")
            print(json.dumps(agg, ensure_ascii=False, indent=2))
        return 1 if agg.get("runs_with_error") else 0

    if args.cmd == "compare":
        report = compare(args.seeds, problem=conf.default_problem, team_id=conf.team_id,
                         left=args.left, right=args.right,
                         left_kwargs=_parse_kwargs(args.left_kwargs),
                         right_kwargs=_parse_kwargs(args.right_kwargs),
                         out_dir=Path(args.out) if args.out else conf.resolved_out_dir() / "compare")
        print(BANNER)
        print()
        print(report)
        return 0

    if args.cmd == "serve":
        port = args.port if args.port is not None else conf.port
        from .server import MockSimulator, serve as serve_http
        sim = MockSimulator(problem=conf.default_problem, mode=args.mode, seed=args.seed,
                            count=args.count, team_id=conf.team_id, port=port,
                            real_limit_s=conf.real_limit_s, window_s=conf.window_s)
        httpd = serve_http(sim, expose_debug=args.expose_debug, verbose=args.verbose)
        sim.start()
        print(BANNER)
        print(f"\nmock 模拟器已启动: http://127.0.0.1:{port}")
        print(f"  team_id (robot_id) = {conf.team_id!r}")
        print(f"  问题={conf.default_problem}  模式={args.mode}  案例={sim.case.case_code}")
        print(f"  接口已开放, 等机器狗调用 /enter")
        if args.expose_debug:
            print(f"  调试: http://127.0.0.1:{port}/debug/truth")
        print("  停止: Ctrl+C")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n收到 Ctrl+C, 正在退出…")
        finally:
            sim.tick()
            httpd.shutdown()
            httpd.server_close()
            print("\n--- 本局结果 ---")
            print(json.dumps(sim.result_summary(), ensure_ascii=False, indent=2))
        return 0

    ap.error("未知命令")
    return 2


if __name__ == "__main__":
    sys.exit(main())
