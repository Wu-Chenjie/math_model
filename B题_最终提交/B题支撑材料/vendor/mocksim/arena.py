# -*- coding: utf-8 -*-
"""mock jammer arena -- core physics, virtual clock and case generation.

This module is a from-scratch implementation of the *documented* behaviour in
2026 CUMCM B 题 附录1/附录2 与 附件1《模拟器使用说明》/ 附件2《模拟器通信接口说明及编程指南》.

It performs no reverse engineering of the official simulator: every constant
below is quoted from the published specification (see CONSTANTS / docstrings).
Purpose: unlimited offline rehearsal of a robot-dog client program.

Unit conventions
----------------
* length : metre
* angle  : degree, 0 = +x (east), counter-clockwise positive, [0, 360)
* time   : second (virtual, internal resolution 1e-6 s)
"""

from __future__ import annotations

import hashlib
import math
import random
import struct
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------
# Constants quoted from the specification
# --------------------------------------------------------------------------

ARENA_RADIUS_M = 1800.0          # 目标区域半径 1800 m (题目正文)
CHANNEL_MIN, CHANNEL_MAX = 1, 20  # 频道 1..20
NEAR_RANGE_M = 5.0               # 近距离阈值 5 m (附件2 §2.4, 附录2(9))
CLEAR_RANGE_M = 20.0             # 清除半径 20 m  (附件2 §2.4, 附录2(8))
SPEED_MPS = 5.0                  # 移动速度 5 m/s (附录2(6))
MEASURE_COST_S = 5.0             # 检测动作 5 s  (附录2(5))
SWITCH_COST_S = 1.0              # 任意两频道切换 1 s (附录2(4))
CLEAR_FOUND_COST_S = 5.0         # 光学定位 3 s + 激光清除 2 s (附录2(8))
CLEAR_MISS_COST_S = 3.0          # 只启用光学探测仪 3 s
SVD_ERROR_LIMIT_DEG = 1.0        # 示向度误差范围 [-1°, 1°] (附录2(1))
DIRECTIONAL_HALF_ANGLE_DEG = 90.0  # 定向源覆盖 = 定向方向两侧各 90° (附录1(3))
EFF_RADIUS_MIN_M, EFF_RADIUS_MAX_M = 1000.0, 1500.0  # 有效接收半径 1000~1500 m
JAMMER_COUNT_MIN, JAMMER_COUNT_MAX = 10, 16          # 干扰源总数 10~16 个

MAX_VIRTUAL_DURATION_S = 360000.0   # 虚拟世界限时 (附件2 §4.5)
MAX_REAL_DURATION_S = 1200.0        # /enter 后程序运行时间上限 20 min
WINDOW_DURATION_S = 1500.0          # 25 分钟测试窗口
ENTRY_GRACE_S = 300.0               # 窗口开启后 5 分钟内 /enter 可用足 20 分钟

COORD_LIMIT_M = 2000000.0           # |坐标分量| <= 2000000 (附件2 §1.1)
ID_BYTE_MIN, ID_BYTE_MAX = 1, 64    # robot_id 1..64 字节
REQ_ID_BYTE_MAX = 128               # request_id 1..128 字节
BODY_LIMIT_BYTES = 65536            # 请求体上限
MAX_JSON_DEPTH = 16                 # JSON 嵌套不超过 16 层

MICRO = 1_000_000  # 模拟器内部按微秒累计 (附件2 §4.1)


def quantise_time(seconds: float) -> float:
    """模拟器内部按微秒累计, 响应最多保留 6 位小数并删除无意义末尾零."""
    return round(seconds * MICRO) / MICRO


# --------------------------------------------------------------------------
# Case (ground truth) generation
# --------------------------------------------------------------------------


@dataclass
class Jammer:
    """一个干扰源。位置/频道/有效接收半径/类型对机器狗不可见 (附录3)."""

    channel: int
    x: float
    y: float
    eff_radius: float
    directional: bool
    bearing_deg: float | None = None  # 定向方向, 仅定向源有; 全向源为空

    @property
    def pos(self) -> tuple[float, float]:
        return (self.x, self.y)

    def covered(self, px: float, py: float) -> bool:
        """检测点是否位于该干扰源信号有效覆盖角度范围内."""
        if not self.directional:
            return True
        assert self.bearing_deg is not None
        return angle_in_sector(px, py, self.x, self.y, self.bearing_deg)


@dataclass
class Case:
    """一局测试的案例真值。problem=3 -> 全向; problem=4 -> 全向+定向混合."""

    case_code: str
    problem: int
    seed: int
    jammers: list[Jammer]
    created_ms: int = 0

    @property
    def total(self) -> int:
        return len(self.jammers)

    @property
    def omni_count(self) -> int:
        return sum(1 for j in self.jammers if not j.directional)

    @property
    def directional_count(self) -> int:
        return sum(1 for j in self.jammers if j.directional)

    def by_channel(self, channel: int) -> Jammer | None:
        for j in self.jammers:
            if j.channel == channel:
                return j
        return None

    def truth_table(self) -> list[dict[str, Any]]:
        return [
            {
                "channel": j.channel,
                "x": round(j.x, 6),
                "y": round(j.y, 6),
                "effective_radius_m": round(j.eff_radius, 6),
                "type": "directional" if j.directional else "omni",
                "bearing_deg": None if j.bearing_deg is None else round(j.bearing_deg, 6),
            }
            for j in sorted(self.jammers, key=lambda j: j.channel)
        ]


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def bearing_deg(px: float, py: float, tx: float, ty: float) -> float:
    """从 (px,py) 指向 (tx,ty) 的真实方位角, 正东为 0°, 逆时针为正, [0,360)."""
    return math.degrees(math.atan2(ty - py, tx - px)) % 360.0


def angle_in_sector(px: float, py: float, jx: float, jy: float, bearing: float) -> bool:
    """检测点是否落在以 bearing 为中心、两侧各 90°(含边界) 的覆盖扇区内。

    附件1(3): "定向干扰源具有特定的发射方向(简称定向方向)，有效覆盖角度范围
    为定向方向两侧各 90°(含)"。注意这个角度是从**干扰源**出发量的，
    等价于 (检测点 - 干扰源) 与 bearing 方向的夹角 <= 90°。
    """
    vx, vy = px - jx, py - jy      # 从干扰源指向检测点
    if vx == 0.0 and vy == 0.0:
        return True                # 与干扰源重合, 视为在覆盖范围内
    rad = math.radians(bearing)
    bx, by = math.cos(rad), math.sin(rad)
    # 夹角 |Δ| <= 90°  <=>  v · b >= 0
    return vx * bx + vy * by >= -1e-9


def svd_error_deg(px: float, py: float, salt: str = "") -> float:
    """给定地点的固定示向度误差, 落在 [-1°, 1°] (附录2(1)).

    "在一段时间内，同一地点的电磁环境干扰是固定的，所以重复检测不会改变
     检测误差。只有在不同地点、不同电磁环境下，误差才会呈现统计规律。
     从目标区域全局来看，所有这些误差在 [-1°, 1°] 范围内"

    实现: 以 1 cm 网格量化位置, blake2b 摘要 -> uint64 -> U(-1, 1)。
    因此同点恒定、异点近似独立均匀分布于 [-1°,1°], 且不依赖调用顺序。
    """
    key = f"{salt}|{round(px * 100)}|{round(py * 100)}".encode("utf-8")
    digest = hashlib.blake2b(key, digest_size=8).digest()
    u = struct.unpack("<Q", digest)[0] / float(1 << 64)   # [0,1)
    return (u * 2.0 - 1.0) * SVD_ERROR_LIMIT_DEG


def norm360(deg: float) -> float:
    return deg % 360.0


def round2(deg: float) -> float:
    """svd_deg 保留两位小数 (附件2 §2.3)."""
    return round(deg, 2)


def make_case(
    *,
    problem: int,
    seed: int | None = None,
    count: int | None = None,
    case_code: str | None = None,
    min_speedup_margin: float = 0.0,
) -> Case:
    """随机生成一局案例。

    problem=3: 全部为全向干扰源。
    problem=4: 全向与定向混合, 定向源个数未知 (这里取 1..count-1 的随机值)。
    count 缺省时在 10..16 之间随机。
    """
    if problem not in (3, 4):
        raise ValueError("problem must be 3 or 4")
    if seed is None:
        seed = random.SystemRandom().randrange(1 << 63)
    rng = random.Random(seed)

    if count is None:
        count = rng.randint(JAMMER_COUNT_MIN, JAMMER_COUNT_MAX)
    if not (JAMMER_COUNT_MIN <= count <= JAMMER_COUNT_MAX):
        raise ValueError(f"count must be in {JAMMER_COUNT_MIN}..{JAMMER_COUNT_MAX}")

    channels = rng.sample(range(CHANNEL_MIN, CHANNEL_MAX + 1), count)

    # 位置采样: 圆域内均匀分布, 但避免与其他干扰源重合(否则频道无法区分),
    # 也避免贴边导致定位区域退化。
    jammers: list[Jammer] = []
    for ch in sorted(channels):
        while True:
            r = ARENA_RADIUS_M * math.sqrt(rng.random())
            th = rng.uniform(0.0, 2.0 * math.pi)
            x, y = r * math.cos(th), r * math.sin(th)
            if all(dist(x, y, j.x, j.y) > 40.0 for j in jammers):
                break
        eff = rng.uniform(EFF_RADIUS_MIN_M, EFF_RADIUS_MAX_M)
        jammers.append(Jammer(channel=ch, x=x, y=y, eff_radius=eff,
                              directional=False, bearing_deg=None))

    if problem == 4:
        # 定向源个数未知: 至少 1 个、至多 count-1 个, 保证两类都存在
        n_dir = rng.randint(1, count - 1) if count > 1 else 0
        for j in rng.sample(jammers, n_dir):
            j.directional = True
            j.bearing_deg = rng.uniform(0.0, 360.0)

    if case_code is None:
        case_code = f"P{problem}-{seed:016X}"

    return Case(case_code=case_code, problem=problem, seed=seed, jammers=jammers)


# --------------------------------------------------------------------------
# Session: virtual clock + robot state machine
# --------------------------------------------------------------------------


@dataclass
class ActionOutcome:
    """一次合法动作的结果。delta_* 为该动作消耗的虚拟时间 (秒)。"""

    virtual_time_s: float
    move_s: float = 0.0
    switch_s: float = 0.0
    action_s: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def total_s(self) -> float:
        return self.move_s + self.switch_s + self.action_s


class Session:
    """一局测试的可变状态: 虚拟时钟、机器狗位置、测向机频道、已清除集合。"""

    def __init__(self, case: Case, *, svd_salt: str = "") -> None:
        self.case = case
        self.svd_salt = svd_salt
        self.case_salt = f"{case.case_code}:{case.seed}"

        self.virtual_time_s = 0.0
        self.entered = False
        self.exited = False
        self.pos: tuple[float, float] = (0.0, 0.0)
        self.current_channel = 1           # 测向机初始频道 1
        self.cleared: set[int] = set()     # 已清除的频道
        self.measure_count = 0
        self.clear_count = 0
        self.clear_success = 0
        self.actions = 0

    # -- helpers ---------------------------------------------------------
    @property
    def alive(self) -> bool:
        return self.entered and not self.exited

    @property
    def remaining_count(self) -> int:
        return self.case.total - len(self.cleared)

    def pending(self, channel: int) -> Jammer | None:
        j = self.case.by_channel(channel)
        if j is None or j.channel in self.cleared:
            return None
        return j

    # -- /enter /exit ----------------------------------------------------
    def enter(self) -> ActionOutcome:
        self.entered = True
        self.pos = (0.0, 0.0)
        self.current_channel = 1
        return ActionOutcome(virtual_time_s=self.virtual_time_s)

    def exit(self) -> ActionOutcome:
        self.exited = True
        return ActionOutcome(virtual_time_s=self.virtual_time_s)

    # -- /measure --------------------------------------------------------
    def measure(self, x: float, y: float, channel: int) -> ActionOutcome:
        move_s = dist(*self.pos, x, y) / SPEED_MPS
        switch_s = 0.0 if channel == self.current_channel else SWITCH_COST_S
        self._advance(move_s + switch_s + MEASURE_COST_S)
        self.pos = (x, y)
        self.current_channel = channel
        self.measure_count += 1

        payload: dict[str, Any] = {"measure_result": "no_signal"}
        jammer = self.pending(channel)
        if jammer is not None:
            d = dist(x, y, jammer.x, jammer.y)
            in_range = d <= jammer.eff_radius
            in_sector = jammer.covered(x, y)
            if in_range and in_sector:
                if d <= NEAR_RANGE_M:
                    payload = {"measure_result": "near"}
                else:
                    true_brg = bearing_deg(x, y, jammer.x, jammer.y)
                    err = svd_error_deg(x, y, salt=self.case_salt + "|" + self.svd_salt)
                    payload = {
                        "measure_result": "direction",
                        "svd_deg": round2(norm360(true_brg + err)),
                    }
        return ActionOutcome(
            virtual_time_s=self.virtual_time_s,
            move_s=quantise_time(move_s),
            switch_s=switch_s,
            action_s=MEASURE_COST_S,
            payload=payload,
        )

    # -- /clear ----------------------------------------------------------
    def clear(self, x: float, y: float, channel: int) -> ActionOutcome:
        move_s = dist(*self.pos, x, y) / SPEED_MPS
        self._advance(move_s + CLEAR_MISS_COST_S)  # 先按"未发现"推进
        self.pos = (x, y)
        self.clear_count += 1

        jammer = self.pending(channel)
        hit = jammer is not None and dist(x, y, jammer.x, jammer.y) <= CLEAR_RANGE_M
        if hit:
            # 已按 3 s 推进, 命中时补足到 5 s
            self._advance(CLEAR_FOUND_COST_S - CLEAR_MISS_COST_S)
            self.cleared.add(channel)
            self.clear_success += 1
            return ActionOutcome(
                virtual_time_s=self.virtual_time_s,
                move_s=quantise_time(move_s),
                action_s=CLEAR_FOUND_COST_S,
                payload={"clear_result": "success"},
            )
        return ActionOutcome(
            virtual_time_s=self.virtual_time_s,
            move_s=quantise_time(move_s),
            action_s=CLEAR_MISS_COST_S,
            payload={"clear_result": "no_target_in_range"},
        )

    # -- clock -----------------------------------------------------------
    def _advance(self, seconds: float) -> None:
        self.virtual_time_s = quantise_time(self.virtual_time_s + seconds)
        self.actions += 1

    @property
    def virtual_expired(self) -> bool:
        return self.virtual_time_s >= MAX_VIRTUAL_DURATION_S

    # -- 统计量 (题目问题3/问题4 要求) ------------------------------------
    def statistics(self, program_runtime_s: float) -> dict[str, Any]:
        cleared = len(self.cleared)
        ratio = (cleared / self.case.total) if self.case.total else 0.0
        avg = (self.virtual_time_s / cleared) if cleared else None
        return {
            "case_code": self.case.case_code,
            "jammer_total": self.case.total,
            "cleared_count": cleared,
            "cleared_ratio": ratio,
            "total_locate_clear_time_s": self.virtual_time_s,
            "avg_locate_clear_time_s": avg,
            "program_runtime_s": program_runtime_s,
            "measure_count": self.measure_count,
            "clear_count": self.clear_count,
            "clear_miss_count": self.clear_count - self.clear_success,
        }
