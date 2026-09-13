# -*- coding: utf-8 -*-
"""演练框架: 批量跑策略、统计、出表1、明文日志、真值诊断、策略对比。"""

from __future__ import annotations

import json
import statistics
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import arena as A
from .client import Rejected, RobotClient, TransportFailure
from .discovery import StrategyInfo, resolve
from .server import MockSimulator, serve
from .version import __version__

FORMAL_WINDOW_S = A.WINDOW_DURATION_S
FORMAL_PROGRAM_LIMIT_S = A.MAX_REAL_DURATION_S


@dataclass
class RunRecord:
    index: int
    strategy: str
    case_code: str
    problem: int
    mode: str
    seed: int | None
    total_jammers: int | None
    omni_count: int | None
    directional_count: int | None
    cleared_count: int
    cleared_ratio: float
    total_locate_clear_time_s: float
    avg_locate_clear_time_s: float | None
    program_runtime_s: float
    measure_count: int
    clear_count: int
    clear_miss_count: int
    end_reason: str | None
    strategy_note: str = ""
    error: str | None = None
    log_path: str | None = None
    truth: list[dict[str, Any]] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


class Harness:
    """在进程内起 mock 模拟器, 驱动策略跑一局或一批。"""

    def __init__(self, *, problem: int = 3, team_id: str = "TEAM0000",
                 out_dir: str | Path = "runs", svd_salt: str = "",
                 real_limit_s: float = FORMAL_PROGRAM_LIMIT_S,
                 window_s: float = FORMAL_WINDOW_S,
                 verbose: bool = True) -> None:
        self.problem = problem
        self.team_id = team_id
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.svd_salt = svd_salt
        self.real_limit_s = real_limit_s
        self.window_s = window_s
        self.verbose = verbose
        self.records: list[RunRecord] = []

    # ------------------------------------------------------------------
    def _say(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    # ------------------------------------------------------------------
    def run_once(self, *, strategy: str | StrategyInfo = "BaselineSweep",
                 seed: int | None = None, count: int | None = None,
                 mode: str = "practice",
                 strategy_kwargs: dict[str, Any] | None = None) -> RunRecord:
        info = strategy if isinstance(strategy, StrategyInfo) else resolve(strategy)
        sim = MockSimulator(problem=self.problem, mode=mode, seed=seed, count=count,
                            team_id=self.team_id, port=0, svd_salt=self.svd_salt,
                            real_limit_s=self.real_limit_s, window_s=self.window_s)
        httpd = serve(sim)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        sim.start()

        index = len(self.records) + 1
        log_path = self.out_dir / f"{info.key}-{mode}-{index:03d}-{sim.case.case_code}.jsonl"
        fh = log_path.open("w", encoding="utf-8")
        stats: dict[str, int] = {"requests": 0, "retries": 0, "http_errors": 0,
                                 "rejected": 0, "transport_failures": 0}

        def sink(entry: dict[str, Any]) -> None:
            stats["requests"] = stats.get("requests", 0) + 1
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            fh.flush()

        client = RobotClient(base_url=f"http://127.0.0.1:{port}", robot_id=self.team_id,
                             log_sink=sink)
        note = ""
        error: str | None = None
        started = time.monotonic()
        try:
            enter = client.enter()
            if enter.get("accepted") is not True:
                raise Rejected(enter)
            remaining = int(enter["remaining_real_duration_s"])
            budget = max(0.0, remaining - 10.0)      # 给 /exit 与网络留余量
            try:
                instance = info.cls(**(strategy_kwargs or {}))
            except TypeError as exc:
                raise SystemExit(
                    f"策略 {info.key} 的构造函数不接受这些参数 "
                    f"({strategy_kwargs}): {exc}") from exc
            try:
                result = instance.run(client, deadline_real_s=budget, verbose=False)
                note = getattr(result, "note", "") or ""
            except (TransportFailure, Rejected) as exc:
                note = f"strategy aborted: {type(exc).__name__}: {exc}"
            try:
                client.exit()
            except Exception:  # noqa: BLE001 - 接口可能已关闭
                pass
        except BaseException as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            self._say(f"    [error] {error}")
            traceback.print_exc()
        finally:
            fh.close()
            sim.tick()
            httpd.shutdown()
            httpd.server_close()

        stats["retries"] = client.stats.retries
        stats["http_errors"] = client.stats.http_errors
        stats["rejected"] = client.stats.rejected
        stats["transport_failures"] = client.stats.transport_failures
        _ = started

        total = sim.case.total
        cleared = len(sim.live.session.cleared) if sim.live else 0
        vt = sim.live.session.virtual_time_s if sim.live else 0.0
        rec = RunRecord(
            index=index,
            strategy=info.key,
            case_code=sim.case.case_code,
            problem=self.problem,
            mode=mode,
            seed=sim.case.seed,
            total_jammers=total if mode == "practice" else None,
            omni_count=sim.case.omni_count if mode == "practice" else None,
            directional_count=sim.case.directional_count if mode == "practice" else None,
            cleared_count=cleared,
            cleared_ratio=(cleared / total) if total else 0.0,
            total_locate_clear_time_s=vt,
            avg_locate_clear_time_s=(vt / cleared) if cleared else None,
            program_runtime_s=sim.live.program_runtime_s() if sim.live else 0.0,
            measure_count=sim.live.session.measure_count if sim.live else 0,
            clear_count=sim.live.session.clear_count if sim.live else 0,
            clear_miss_count=((sim.live.session.clear_count - sim.live.session.clear_success)
                              if sim.live else 0),
            end_reason=sim.live.end_reason if sim.live else None,
            strategy_note=note,
            error=error,
            log_path=str(log_path),
            truth=sim.case.truth_table() if mode == "practice" else [],
        )
        rec.strategy = info.key
        self.records.append(rec)
        avg_txt = (f"{rec.avg_locate_clear_time_s:.1f}"
                   if rec.avg_locate_clear_time_s else "—")
        self._say(
            f"  [{index:>3}] {rec.case_code} seed={rec.seed} "
            f"清除 {cleared}/{total} 平均 {avg_txt}s "
            f"虚拟总耗时 {rec.total_locate_clear_time_s:.0f}s "
            f"检测{rec.measure_count} 清除{rec.clear_count} "
            f"结束={rec.end_reason}"
            + (f" 错误={rec.error}" if rec.error else "")
        )
        return rec

    # ------------------------------------------------------------------
    def run_batch(self, n: int, *, strategy: str | StrategyInfo = "BaselineSweep",
                  mode: str = "practice", seeds: list[int] | None = None,
                  counts: list[int] | None = None,
                  strategy_kwargs: dict[str, Any] | None = None) -> list[RunRecord]:
        info = strategy if isinstance(strategy, StrategyInfo) else resolve(strategy)
        self._say(f"\n策略 {info.key} | 问题 {self.problem} | {mode} | {n} 局")
        out = []
        for i in range(n):
            seed = seeds[i] if seeds and i < len(seeds) else None
            count = counts[i] if counts and i < len(counts) else None
            out.append(self.run_once(strategy=info, seed=seed, count=count, mode=mode,
                                     strategy_kwargs=strategy_kwargs))
        return out

    # ------------------------------------------------------------------
    def aggregate(self) -> dict[str, Any]:
        recs = self.records
        if not recs:
            return {}
        known = [r for r in recs if r.total_jammers]
        ratios = [r.cleared_ratio for r in known]
        avgs = [r.avg_locate_clear_time_s for r in recs if r.avg_locate_clear_time_s]
        return {
            "runs": len(recs),
            "problems": sorted({r.problem for r in recs}),
            "strategies": sorted({r.strategy for r in recs}),
            "mean_cleared_ratio": statistics.fmean(ratios) if ratios else None,
            "worst_cleared_ratio": min(ratios) if ratios else None,
            "mean_avg_locate_clear_time_s": statistics.fmean(avgs) if avgs else None,
            "mean_program_runtime_s": statistics.fmean([r.program_runtime_s for r in recs]),
            "full_clear_runs": sum(1 for r in known if r.cleared_count == r.total_jammers),
            "known_runs": len(known),
            "mean_measure_count": statistics.fmean([r.measure_count for r in recs]),
            "mean_clear_count": statistics.fmean([r.clear_count for r in recs]),
            "mean_clear_miss_count": statistics.fmean([r.clear_miss_count for r in recs]),
            "runs_with_error": sum(1 for r in recs if r.error),
            "end_reasons": _tally(r.end_reason or "unknown" for r in recs),
        }

    # ------------------------------------------------------------------
    def export_results_table(self, path: str | Path | None = None, *,
                             tests: int = 3, mode: str = "formal") -> Path:
        """导出题目表1 格式的结果表 (Markdown + CSV)。"""
        path = Path(path) if path else self.out_dir / "table1-results.md"
        rows = [r for r in self.records if r.mode == mode][:tests]
        if not rows:
            rows = self.records[-tests:]
        lines = [
            f"| 测试 | 测试案例编码 | 清除干扰源个数 | 平均定位清除时间(s) | 程序运行时间(s) |",
            "|---|---|---|---|---|",
        ]
        csv_lines = ["test,case_code,cleared_count,avg_locate_clear_time_s,program_runtime_s"]
        for i, r in enumerate(rows, 1):
            avg_txt = f"{r.avg_locate_clear_time_s:.2f}" if r.avg_locate_clear_time_s else "—"
            avg_csv = (f"{r.avg_locate_clear_time_s:.6f}"
                       if r.avg_locate_clear_time_s else "")
            lines.append(f"| 测试{i} | {r.case_code} | {r.cleared_count} | "
                         f"{avg_txt} | {r.program_runtime_s:.2f} |")
            csv_lines.append(f"{i},{r.case_code},{r.cleared_count},{avg_csv},"
                             f"{r.program_runtime_s:.6f}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path.with_suffix(".csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")
        return path

    def export_json(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path else self.out_dir / "summary.json"
        payload = {
            "environment": "26B local mock simulator",
            "version": __version__,
            "team_id": self.team_id,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "problem": self.problem,
            "limits": {"real_limit_s": self.real_limit_s, "window_s": self.window_s},
            "aggregate": self.aggregate(),
            "runs": [r.as_row() for r in self.records],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path

    def diagnosis(self) -> str:
        """对照真值诊断: 哪些频道没清掉、真值在哪、交会环节是否够用。"""
        out: list[str] = []
        for r in self.records:
            if not r.truth:
                continue
            miss = (r.total_jammers or 0) - r.cleared_count
            flag = "OK " if miss == 0 else "MISS"
            out.append(
                f"[{flag}] {r.case_code} seed={r.seed} 干扰源 {r.total_jammers} "
                f"(全向 {r.omni_count}/定向 {r.directional_count}) 清除 {r.cleared_count} "
                f"平均 {r.avg_locate_clear_time_s and round(r.avg_locate_clear_time_s, 1)}s "
                f"检测 {r.measure_count} 清除 {r.clear_count}(落空 {r.clear_miss_count}) "
                f"结束 {r.end_reason}"
            )
            if r.error:
                out.append(f"      错误: {r.error}")
            if miss and r.strategy_note:
                out.append(f"      {r.strategy_note}")
            if miss:
                for t in r.truth:
                    out.append(f"      ch{t['channel']:>2} ({t['x']:>9.1f},{t['y']:>9.1f}) "
                               f"r={t['effective_radius_m']:.0f} {t['type']}"
                               + (f" bearing={t['bearing_deg']:.1f}"
                                  if t["bearing_deg"] is not None else ""))
        return "\n".join(out)


def _tally(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


# ----------------------------------------------------------------------
# 策略对比: 同一批 seed 下比较两个策略, 便于 A/B 调参
# ----------------------------------------------------------------------


def compare(seeds: list[int], *, problem: int = 3, team_id: str = "TEAM0000",
            left: str = "BaselineSweep", right: str | None = None,
            out_dir: str | Path = "runs/compare", verbose: bool = True,
            left_kwargs: dict[str, Any] | None = None,
            right_kwargs: dict[str, Any] | None = None) -> str:
    results: dict[str, list[RunRecord]] = {}
    for key, kwargs in ((left, left_kwargs), (right, right_kwargs)):
        if key is None:
            continue
        h = Harness(problem=problem, team_id=team_id,
                    out_dir=Path(out_dir) / key, verbose=verbose)
        results[key] = h.run_batch(len(seeds), strategy=key, seeds=seeds,
                                   strategy_kwargs=kwargs)

    lines = ["| seed | 案例编码 | " + " | ".join(
        f"{k} 清除/总数 | {k} 平均时间(s)" for k in results) + " |",
        "|---|---|" + "---|" * (2 * len(results))]
    for i, seed in enumerate(seeds):
        row = [str(seed)]
        code = ""
        for key, recs in results.items():
            if i < len(recs):
                r = recs[i]
                code = r.case_code
                avg = f"{r.avg_locate_clear_time_s:.1f}" if r.avg_locate_clear_time_s else "—"
                row.append(f"{r.cleared_count}/{r.total_jammers}")
                row.append(avg)
            else:
                row.extend(["—", "—"])
        lines.append("| " + " | ".join([row[0], code] + row[1:]) + " |")

    lines.append("")
    for key, recs in results.items():
        known = [r for r in recs if r.total_jammers]
        ratios = [r.cleared_ratio for r in known] or [0.0]
        avgs = [r.avg_locate_clear_time_s for r in recs if r.avg_locate_clear_time_s]
        full = sum(1 for r in known if r.cleared_count == r.total_jammers)
        if avgs:
            lines.append(
                f"- **{key}**: 平均清除比例 {statistics.fmean(ratios):.3f}, "
                f"最差 {min(ratios):.3f}, 满分 {full}/{len(known)}, "
                f"平均定位清除时间 {statistics.fmean(avgs):.0f}s"
            )
        else:
            lines.append(f"- **{key}**: 无成功清除记录 (平均清除比例 "
                         f"{statistics.fmean(ratios):.3f})")
    report = "\n".join(lines)
    out = Path(out_dir) / "compare.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report + "\n", encoding="utf-8")
    return report


def euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    import math
    return math.hypot(a[0] - b[0], a[1] - b[1])


# --------------------------------------------------------------------------
# 命令行: 统一入口在 mocksim/cli.py, 这里只转发, 避免出现两套参数
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    print("提示: 演练入口已统一到 mocksim.cli (写法见 QUICKSTART.md):")
    print("  python -m mocksim.cli run --problem 3 --runs 6\n")
    from .cli import main as cli_main
    args = list(argv if argv is not None else [])
    if not args or args[0].startswith("-"):
        args = ["run", *args]
    return cli_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
