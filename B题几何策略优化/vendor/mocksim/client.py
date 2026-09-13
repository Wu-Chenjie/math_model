# -*- coding: utf-8 -*-
"""机器狗客户端与几何工具 (不含具体策略)。

协议规则按 附件2 §5 / §12 实现:

* 每个新动作使用新的 ``request_id``
* 只在"超时 / 连接中断后重发同一动作"时复用原 payload 与原 id
* 严格串行: 同一时刻只有一个在途动作, 必须等完整响应
* 同时检查 HTTP 状态与 ``accepted``
* 连接被直接关闭 (无 JSON 体) 视为可重试, 不当作错误响应
* 使用 /enter 返回的 ``remaining_real_duration_s``, 不假定每次都有 1200 s
* 只在 ``measure_result == "direction"`` 时读取 ``svd_deg``
* ``no_signal`` 不代表附近没有干扰源

具体搜索/清除策略请放在 ``strategies/`` 目录里, 复制 ``strategies/_template.py`` 开始写;
运行入口统一是 ``python -m mocksim.cli``。
"""

from __future__ import annotations

import http.client
import json
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

ARENA_RADIUS_M = 1800.0

#: 回环地址的请求必须直连: 系统代理 (HTTP_PROXY/HTTPS_PROXY) 会把 127.0.0.1
#: 的请求转发出去, 表现为 502 Bad Gateway 或 407, 让人误以为是模拟器故障。
NO_PROXY = ("127.0.0.1", "localhost", "::1", "[::1]")


def make_opener() -> urllib.request.OpenerDirector:
    """返回一个明确绕过系统代理的 opener。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


# --------------------------------------------------------------------------
# 异常
# --------------------------------------------------------------------------


class ProtocolError(RuntimeError):
    """模拟器返回 HTTP 400/409/413/415/429/500 等硬错误。"""

    def __init__(self, status: int, body: Any) -> None:
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


class TransportFailure(RuntimeError):
    """连不上, 或连接被直接关闭 (接口未开放 / 测试已结束)。"""


class Rejected(RuntimeError):
    """HTTP 200 但 accepted=false: 动作没有生效, virtual_time_s 不可信。"""

    def __init__(self, response: dict[str, Any]) -> None:
        super().__init__(f"accepted=false: {response}")
        self.response = response


@dataclass
class ClientStats:
    requests: int = 0
    retries: int = 0
    http_errors: int = 0
    rejected: int = 0
    transport_failures: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "requests": self.requests,
            "retries": self.retries,
            "http_errors": self.http_errors,
            "rejected": self.rejected,
            "transport_failures": self.transport_failures,
        }


# --------------------------------------------------------------------------
# 客户端
# --------------------------------------------------------------------------


class RobotClient:
    """逐次等待响应的 HTTP+JSON 客户端。"""

    def __init__(self, *, base_url: str = "http://127.0.0.1:2026",
                 robot_id: str = "TEAM0000", timeout_s: float = 5.0,
                 retries: int = 5, retry_backoff_s: float = 0.05,
                 log_sink: Callable[[dict[str, Any]], None] | None = None,
                 use_system_proxy: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.robot_id = robot_id
        self.timeout_s = timeout_s
        self.retries = retries
        self.retry_backoff_s = retry_backoff_s
        self.stats = ClientStats()
        self.counter = 0
        self.log_sink = log_sink
        self.log: list[dict[str, Any]] = []
        self.opener = (urllib.request.build_opener() if use_system_proxy
                       else make_opener())

    # -- transport -------------------------------------------------------
    def _next_id(self, kind: str) -> str:
        self.counter += 1
        return f"{kind}-{self.counter}"

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """发送一个动作并等待完整响应; 相同内容与 id 会按需重试。"""
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path, data=raw, method="POST",
            headers={"Content-Type": "application/json"},
        )
        attempt = 0
        while True:
            attempt += 1
            self.stats.requests += 1
            try:
                with self.opener.open(request, timeout=self.timeout_s) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    status = resp.status
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")
                try:
                    body = json.loads(detail)
                except json.JSONDecodeError:
                    body = {"detail": detail}
                self.stats.http_errors += 1
                self._log(path, payload, exc.code, body)
                raise ProtocolError(exc.code, body) from None
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError,
                    http.client.HTTPException, ValueError) as exc:
                # 接口未开放 / 测试已结束 / 网络抖动: 连接被直接关闭, 没有 JSON 体。
                # 复用完全相同的 payload 与 request_id 重试 (附件2 §5.3)。
                self.stats.transport_failures += 1
                if attempt > self.retries:
                    raise TransportFailure(f"{type(exc).__name__}: {exc}") from exc
                self.stats.retries += 1
                time.sleep(self.retry_backoff_s * attempt)
                continue
            self._log(path, payload, status, body)
            if body.get("accepted") is not True:
                self.stats.rejected += 1
            return body

    def _log(self, path: str, payload: dict[str, Any], status: int,
             body: dict[str, Any]) -> None:
        entry = {
            "wall_ms": int(time.time() * 1000),
            "path": path,
            "http_status": status,
            "request": payload,
            "response": body,
        }
        self.log.append(entry)
        if self.log_sink is not None:
            self.log_sink(entry)

    # -- actions ---------------------------------------------------------
    def _base(self, kind: str) -> dict[str, Any]:
        return {"arena_id": "default", "robot_id": self.robot_id,
                "request_id": self._next_id(kind)}

    def enter(self) -> dict[str, Any]:
        return self.post("/enter", self._base("enter"))

    def exit(self) -> dict[str, Any]:
        return self.post("/exit", self._base("exit"))

    def measure(self, x: float, y: float, channel: int) -> dict[str, Any]:
        p = self._base("measure")
        p["position"] = {"x": _num(x), "y": _num(y)}
        p["channel"] = int(channel)
        return self.post("/measure", p)

    def clear(self, x: float, y: float, channel: int) -> dict[str, Any]:
        p = self._base("clear")
        p["position"] = {"x": _num(x), "y": _num(y)}
        p["channel"] = int(channel)
        return self.post("/clear", p)

    # -- 断言 accepted 的包装 --------------------------------------------
    def measure_checked(self, x: float, y: float, channel: int) -> dict[str, Any]:
        r = self.measure(x, y, channel)
        if r.get("accepted") is not True:
            raise Rejected(r)
        return r

    def clear_checked(self, x: float, y: float, channel: int) -> dict[str, Any]:
        r = self.clear(x, y, channel)
        if r.get("accepted") is not True:
            raise Rejected(r)
        return r

    # -- 便捷读取 --------------------------------------------------------
    @staticmethod
    def virtual_time(resp: dict[str, Any], fallback: float = 0.0) -> float:
        """只在 accepted=true 时可信; 否则返回 fallback。"""
        if resp.get("accepted") is True:
            return float(resp.get("virtual_time_s", fallback))
        return fallback

    @staticmethod
    def svd(resp: dict[str, Any]) -> float | None:
        """只有 measure_result == "direction" 时才有示向度。"""
        if resp.get("measure_result") == "direction":
            return float(resp["svd_deg"])
        return None


def _num(v: float) -> float | int:
    """JSON 里整数坐标更好读, 但必须是有限数值。"""
    if float(v).is_integer():
        return int(v)
    return round(float(v), 6)


# --------------------------------------------------------------------------
# 方位几何工具
# --------------------------------------------------------------------------


def norm360(d: float) -> float:
    return d % 360.0


def angular_diff(a: float, b: float) -> float:
    """两个方位角的最小夹角, 单位度, 范围 [0,180]。"""
    d = abs(norm360(a) - norm360(b)) % 360.0
    return d if d <= 180.0 else 360.0 - d


@dataclass
class Bearing:
    x: float
    y: float
    deg: float
    virtual_time_s: float = 0.0

    def as_line(self) -> tuple[float, float, float]:
        """返回 (n_x, n_y, c) 使 n·p = c 表示这条方位线 (n 为单位法向)。"""
        rad = math.radians(self.deg)
        nx, ny = -math.sin(rad), math.cos(rad)
        return nx, ny, nx * self.x + ny * self.y


class Estimator:
    """由若干条示向度直线做最小二乘交会, 得到干扰源位置估计。

    ±1° 的示向度误差下, 交会精度取决于基线与交角: 基线越长、交角越接近 90°,
    估计越准。``estimate`` 默认只用最后两条 (帮助策略快速逼近),
    ``estimate_all`` 用全部观测 (帮助收敛到更精确的位置)。
    """

    def __init__(self) -> None:
        self.bearings: dict[int, list[Bearing]] = {}

    def add(self, channel: int, x: float, y: float, deg: float,
            virtual_time_s: float = 0.0) -> None:
        self.bearings.setdefault(channel, []).append(Bearing(x, y, deg, virtual_time_s))

    def latest(self, channel: int) -> Bearing | None:
        lst = self.bearings.get(channel)
        return lst[-1] if lst else None

    def count(self, channel: int) -> int:
        return len(self.bearings.get(channel) or [])

    def channels(self) -> list[int]:
        return sorted(self.bearings)

    @staticmethod
    def _solve(pts: list[Bearing]) -> tuple[float, float, float] | None:
        a11 = a12 = a22 = b1 = b2 = 0.0
        for p in pts:
            nx, ny, c = p.as_line()
            a11 += nx * nx
            a12 += nx * ny
            a22 += ny * ny
            b1 += nx * c
            b2 += ny * c
        det = a11 * a22 - a12 * a12
        if abs(det) < 1e-12:
            return None
        x = (b1 * a22 - b2 * a12) / det
        y = (a11 * b2 - a12 * b1) / det
        acc = 0.0
        for p in pts:
            nx, ny, c = p.as_line()
            acc += (nx * x + ny * y - c) ** 2
        return x, y, math.sqrt(acc / len(pts))

    def estimate(self, channel: int) -> tuple[float, float, float] | None:
        """用最后两条方位线交会; 不足两条返回 None。"""
        pts = self.bearings.get(channel) or []
        return self._solve(pts[-2:]) if len(pts) >= 2 else None

    def estimate_all(self, channel: int) -> tuple[float, float, float] | None:
        """用该频道全部方位线交会。"""
        pts = self.bearings.get(channel) or []
        return self._solve(pts) if len(pts) >= 2 else None

    def baseline(self, channel: int) -> float:
        """最长观测基线长度 (米)。"""
        pts = self.bearings.get(channel) or []
        best = 0.0
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                best = max(best, math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y))
        return best


# --------------------------------------------------------------------------
# 策略运行结果
# --------------------------------------------------------------------------


@dataclass
class StrategyResult:
    """策略自报的结果 (框架只用 note 做诊断, 真实统计以模拟器为准)。"""

    cleared: int = 0
    attempts: int = 0
    channels_seen: list[int] | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.channels_seen is None:
            self.channels_seen = []
