# -*- coding: utf-8 -*-
"""Protocol conformance suite -- checks the *mock simulator* against 附件2.

Every assertion quotes the specification clause it enforces, so this file doubles
as an executable reading of the contract.  It validates the harness itself:
if the mock disagrees with the written protocol, a robot tuned here would
misbehave on the real simulator.

Usage:  python -m mocksim.conformance
"""

from __future__ import annotations

import http.client
import json
import math
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from . import arena as A
from .server import MockSimulator, serve

TEAM = "2026TEST0001"

#: 回环地址必须绕过系统代理, 否则 HTTP_PROXY 会把请求转出去 (502/407)。
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_ID_SEQ = 0


def _next_request_id() -> str:
    global _ID_SEQ
    _ID_SEQ += 1
    return f"auto-{_ID_SEQ}"


class Runner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[str] = []
        self.notes: list[str] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed.append(f"{name} {detail}".strip())
            print(f"  [FAIL] {name} {detail}")

    def eq(self, name: str, got: Any, want: Any) -> None:
        self.check(name, got == want, f"(got {got!r}, want {want!r})")

    def close(self, name: str, got: float, want: float, tol: float = 1e-6) -> None:
        self.check(name, abs(got - want) <= tol, f"(got {got!r}, want {want!r})")


def raw_post(url: str, path: str, body: bytes, *, ctype: str = "application/json",
             extra_headers: dict[str, str] | None = None) -> tuple[int, str]:
    """返回 (http_status, body_text); 连接被直接关闭时返回 (-1, '')."""
    headers = {"Content-Type": ctype}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url + path, data=body, method="POST", headers=headers)
    try:
        with OPENER.open(req, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, ConnectionError, OSError, http.client.HTTPException):
        # 接口未开放 / 测试已结束: 连接被直接关闭, 没有 JSON 体
        return -1, ""


def jpost(url: str, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    status, text = raw_post(url, path, json.dumps(payload).encode("utf-8"))
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {}


def body(**over: Any) -> dict[str, Any]:
    """请求体模板。默认给一个全新的 request_id: 规范要求每个新动作用新的 id,
    重复使用会被幂等规则判为 409, 从而掩盖真正要测的校验分支。"""
    base = {"arena_id": "default", "robot_id": TEAM,
            "request_id": _next_request_id()}
    base.update(over)
    return base


def ride(**over: Any) -> dict[str, Any]:
    """measure/clear 请求体。"""
    b = body()
    b.update({"position": {"x": 0, "y": 0}, "channel": 1})
    b.update(over)
    return b


def main() -> int:
    r = Runner()
    sim = MockSimulator(problem=3, mode="practice", seed=20260913, count=12,
                        team_id=TEAM, port=0, svd_salt="conformance")
    httpd = serve(sim)
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}"
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    try:
        # ==============================================================
        print("\n[1] 接口未开放 / 测试未开始 (附件2 §5.3: 连接可能直接关闭)")
        st, _ = jpost(url, "/measure", ride())
        r.eq("/measure before /enter closes the connection", st, -1)

        # 从第 2 节起接口必须已经开放, 否则所有请求都会因接口未开放而失败。
        sim.start()
        st, resp = jpost(url, "/enter", body(request_id="boot"))
        r.eq("interface opens and /enter succeeds", resp.get("accepted"), True)

        # ==============================================================
        print("\n[2] HTTP 方法 / 路径 (附件2 §5.3: 404, 405)")
        st, text = raw_post(url, "/enter/", json.dumps(body()).encode("utf-8"))
        r.eq("trailing slash -> 404", st, 404)
        st, text = raw_post(url, "/enter?x=1", json.dumps(body()).encode("utf-8"))
        r.eq("query string -> 404", st, 404)
        st, text = raw_post(url, "/nope", json.dumps(body()).encode("utf-8"))
        r.eq("unknown path -> 404", st, 404)
        req = urllib.request.Request(url + "/enter", method="GET")
        try:
            with OPENER.open(req, timeout=5) as resp:
                st = resp.status
        except urllib.error.HTTPError as exc:
            st = exc.code
        r.eq("GET on known path -> 405", st, 405)

        # ==============================================================
        print("\n[3] Content-Type / Content-Encoding (附件2 §5.1: 415)")
        st, _ = raw_post(url, "/enter", b"{}", ctype="text/plain")
        r.eq("wrong media type -> 415", st, 415)
        st, _ = raw_post(url, "/enter", b"{}", ctype="application/json; charset=gbk")
        r.eq("charset=gbk -> 415", st, 415)
        st, _ = raw_post(url, "/enter", b"{}",
                         ctype="application/json; charset=utf-8; foo=1")
        r.eq("extra contentType param -> 415", st, 415)
        st, _ = raw_post(url, "/enter", b"{}", extra_headers={"Content-Encoding": "gzip"})
        r.eq("Content-Encoding: gzip -> 415", st, 415)

        # ==============================================================
        print("\n[4] JSON 语法 / 重复键 / 深度 (附件2 §5.1: 400)")
        st, _ = raw_post(url, "/enter", b"{not json")
        r.eq("invalid JSON -> 400", st, 400)
        st, _ = raw_post(url, "/enter", b'{"arena_id":"default","arena_id":"default"}')
        r.eq("duplicate key -> 400", st, 400)
        st, _ = raw_post(url, "/enter", "\ufeff".encode("utf-8") + b"{}")
        r.eq("UTF-8 BOM -> 400", st, 400)
        deep = b'{"a":' * 20 + b'1' + b'}' * 20
        st, _ = raw_post(url, "/enter", deep)
        r.eq("nesting > 16 -> 400", st, 400)
        st, _ = raw_post(url, "/enter", b'["array"]')
        r.eq("non-object top level -> 400", st, 400)

        # ==============================================================
        print("\n[5] /enter 成功路径 (附件2 §6.2)")
        # 重新开一局, 使 /enter 处于"尚未进入"的状态
        sim.new_case(seed=20260913, count=12)
        sim.start()
        st, resp = jpost(url, "/enter", body(request_id="enter-a"))
        r.eq("/enter -> 200", st, 200)
        r.eq("accepted true", resp.get("accepted"), True)
        r.eq("max_virtual_duration_s default", resp.get("max_virtual_duration_s"), 360000)
        r.eq("max_real_duration_s default", resp.get("max_real_duration_s"), 1200)
        r.check("remaining_real_duration_s in 0..1200",
                0 <= resp.get("remaining_real_duration_s", -1) <= 1200,
                f"(got {resp.get('remaining_real_duration_s')})")
        r.eq("virtual_time_s unchanged by /enter", resp.get("virtual_time_s"), 0)
        r.check("real_timestamp_ms looks like epoch ms",
                resp.get("real_timestamp_ms", 0) > 1_700_000_000_000)

        # ==============================================================
        print("\n[6] 未知字段 -> 200 accepted=false (附件2 §5.1/§5.3)")
        st, resp = jpost(url, "/measure", ride(chennel=3))
        r.eq("typo field -> HTTP 200", st, 200)
        r.eq("typo field -> accepted false", resp.get("accepted"), False)
        r.eq("accepted=false -> virtual_time_s 0", resp.get("virtual_time_s"), 0)
        r.check("accepted=false body has only the 3 base fields",
                set(resp) <= {"accepted", "real_timestamp_ms", "virtual_time_s", "detail"},
                f"(got {sorted(resp)})")
        st, resp = jpost(url, "/measure", ride(position={"x": 0, "y": 0, "z": 0}))
        r.eq("unknown position field -> accepted false", resp.get("accepted"), False)

        # ==============================================================
        print("\n[7] arena_id / robot_id 不匹配 -> 200 accepted=false (附件2 §5.1)")
        st, resp = jpost(url, "/measure", ride(arena_id="other"))
        r.eq("arena_id != default -> accepted false", resp.get("accepted"), False)
        st, resp = jpost(url, "/measure", ride(robot_id="SOMEONEELSE"))
        r.eq("robot_id mismatch -> accepted false", resp.get("accepted"), False)

        # ==============================================================
        print("\n[8] 字段类型 / 取值 -> 400 (附件2 §5.1, §7.1)")
        # 每个新动作都必须用新的 request_id, 否则会先触发 409 幂等冲突
        r.eq("channel 0 -> 400",
             jpost(url, "/measure", ride(request_id="v-ch0", channel=0))[0], 400)
        r.eq("channel 21 -> 400",
             jpost(url, "/measure", ride(request_id="v-ch21", channel=21))[0], 400)
        r.eq("channel 1.5 -> 400",
             jpost(url, "/measure", ride(request_id="v-ch15", channel=1.5))[0], 400)
        r.eq("channel 1.0 -> accepted",
             jpost(url, "/measure", ride(request_id="v-ch10", channel=1.0))[1].get("accepted"),
             True)
        r.eq("missing channel -> 400",
             jpost(url, "/measure", body(request_id="v-noch"))[0], 400)
        r.eq("x over 2e6 -> 400",
             jpost(url, "/measure", ride(request_id="v-xbig",
                                        position={"x": 2_000_001, "y": 0}))[0], 400)
        r.eq("x == 2e6 accepted",
             jpost(url, "/measure", ride(request_id="v-xlim",
                                        position={"x": 2_000_000, "y": 0}))[1].get("accepted"),
             True)
        # 这一步移动 2e6 米 = 4e5 秒虚拟时间, 超过 360000 秒上限, 会把本局结束
        # (附件2 §4.5)。后续校验需要一局新的测试。
        print("    (x == 2e6 消耗 4e5 s 虚拟时间并触发虚拟超时, 属预期行为)")
        r.eq("virtual-time cap ends the run",
             sim.live.end_reason if sim.live else None, "virtual_timeout")
        sim.new_case(seed=20260914, count=12)
        sim.start()

        print("\n[8b] 标识符与坐标合法性 -> 400 (附件2 §5.1)")
        st, _ = raw_post(url, "/measure",
                         b'{"arena_id":"default","robot_id":"2026TEST0001",'
                         b'"request_id":"r-nan","position":{"x":NaN,"y":0},"channel":1}')
        r.eq("NaN coordinate -> 400", st, 400)
        st, _ = raw_post(url, "/measure",
                         b'{"arena_id":"default","robot_id":"2026TEST0001",'
                         b'"request_id":"r-inf","position":{"x":1e999,"y":0},"channel":1}')
        r.eq("Infinity coordinate -> 400", st, 400)
        r.eq("empty robot_id -> 400",
             jpost(url, "/enter", body(request_id="v-rid0", robot_id=""))[0], 400)
        r.eq("robot_id with control char -> 400",
             jpost(url, "/enter", body(request_id="v-rid1", robot_id="ab\u0001cd"))[0], 400)
        r.eq("request_id of 129 bytes -> 400",
             jpost(url, "/enter", body(request_id="x" * 129))[0], 400)
        r.eq("request_id of 128 bytes is within the limit",
             jpost(url, "/enter", body(request_id="y" * 128))[0], 200)
        r.eq("int position accepted",
             jpost(url, "/measure", ride(request_id="v-int",
                                        position={"x": 1, "y": 2}))[1].get("accepted"),
             True)

        # ==============================================================
        print("\n[9] 请求体大小 -> 413 (附件2 §5.1)")
        big = json.dumps({"arena_id": "default", "robot_id": TEAM,
                          "request_id": "big", "pad": "z" * 70000}).encode()
        r.eq("body > 65536 bytes -> 413", raw_post(url, "/enter", big)[0], 413)

        # ==============================================================
        print("\n[10] 虚拟计时 (附件2 §10 完整计时示例)")
        # 重开一局, 使用规范示例的动作序列
        sim2 = MockSimulator(problem=3, mode="practice", seed=7, count=10, team_id=TEAM)
        sim2.start()
        s = sim2.live.session
        # 用与规范相同的四个动作, 直接驱动状态机以便精确比对
        calls = [("measure", 300, 400, 1, 105.0, 100.0, 0.0, 5.0),
                 ("measure", 300, 400, 2, 111.0, 0.0, 1.0, 5.0),
                 ("clear", 300, 0, 3, 194.0, 80.0, 0.0, 3.0),
                 ("measure", 300, 0, 2, 199.0, 0.0, 0.0, 5.0)]
        s.enter()
        for kind, x, y, ch, vt, mv, sw, act in calls:
            o = s.measure(x, y, ch) if kind == "measure" else s.clear(x, y, ch)
            r.close(f"{kind} ch{ch} virtual_time_s", o.virtual_time_s, vt)
            r.close(f"{kind} ch{ch} move_s", o.move_s, mv)
            r.close(f"{kind} ch{ch} switch_s", o.switch_s, sw)
            r.close(f"{kind} ch{ch} action_s", o.action_s, act)

        # ==============================================================
        print("\n[11] 幂等规则 (附件2 §5.3)")
        sim3 = MockSimulator(problem=3, mode="practice", seed=11, count=10, team_id=TEAM,
                             port=0)
        httpd3 = serve(sim3)
        url3 = f"http://127.0.0.1:{httpd3.server_address[1]}"
        threading.Thread(target=httpd3.serve_forever, daemon=True).start()
        sim3.start()
        jpost(url3, "/enter", body(request_id="e1"))
        p = ride(request_id="m1", position={"x": 500, "y": 0}, channel=1)
        st1, resp1 = jpost(url3, "/measure", p)
        st2, resp2 = jpost(url3, "/measure", p)          # 完全相同的重试
        r.eq("retry of identical action -> 200", st2, 200)
        r.eq("retry replays the first response", resp2, resp1)
        st3, resp3 = jpost(url3, "/measure", ride(request_id="m1",
                                                 position={"x": 600, "y": 0}, channel=1))
        r.eq("same request_id, different content -> 409", st3, 409)
        # 结构错误不占用 request_id
        jpost(url3, "/measure", ride(request_id="m2", channel=99))
        st4, resp4 = jpost(url3, "/measure", ride(request_id="m2",
                                                 position={"x": 800, "y": 0}, channel=2))
        r.eq("400 does not consume request_id (reusable)", resp4.get("accepted"), True)
        # accepted=false 也不占用
        jpost(url3, "/measure", ride(request_id="m3", arena_id="bad"))
        st5, resp5 = jpost(url3, "/measure", ride(request_id="m3",
                                                 position={"x": 900, "y": 0}, channel=3))
        r.eq("accepted=false does not consume request_id", resp5.get("accepted"), True)
        st6, resp6 = jpost(url3, "/exit", body(request_id="x1"))
        r.eq("/exit -> exit_reason user_exit", resp6.get("exit_reason"), "user_exit")
        st7, resp7 = jpost(url3, "/measure", ride(request_id="m9"))
        r.eq("after /exit the interface is closed", st7, -1)
        httpd3.shutdown()

        # ==============================================================
        print("\n[12] 物理与统计规则 (附录1/附录2)")
        sim4 = MockSimulator(problem=4, mode="practice", seed=4242, count=10,
                             team_id=TEAM)
        sim4.start()
        s4 = sim4.live.session
        s4.enter()
        j0 = sim4.case.jammers[0]
        # 从干扰源正东侧 300 m 处检测: 真实方位角应为 180°(从检测点指向干扰源)
        bx, by = j0.x + 300.0, j0.y
        o = s4.measure(bx, by, j0.channel)
        if o.payload.get("measure_result") == "direction":
            true_deg = A.bearing_deg(bx, by, j0.x, j0.y)
            got = o.payload["svd_deg"]
            r.check("svd_deg within +/-1 deg of true bearing",
                    abs((got - true_deg + 180) % 360 - 180) <= 1.0 + 1e-9,
                    f"(true {true_deg:.4f}, got {got})")
            r.eq("svd_deg has 2 decimals", round(got, 2), got)
            r.check("svd_deg in [0,360)", 0.0 <= got < 360.0)
        else:
            r.notes.append("first jammer not detectable at +300 m east (directional); "
                           "bearing check skipped")
        # 同点重复测量误差恒定
        o1 = s4.measure(bx, by, j0.channel)
        s4b = A.Session(sim4.case)
        s4b.enter()
        o2 = s4b.measure(bx, by, j0.channel)
        r.eq("same location -> identical svd_deg", o1.payload.get("svd_deg"),
             o2.payload.get("svd_deg"))
        # 覆盖角: 全向源在任意方向都可测到
        omni = next((j for j in sim4.case.jammers if not j.directional), None)
        if omni is not None:
            angs = [0, 90, 180, 270]
            hits = 0
            for a in angs:
                rad = math.radians(a)
                s4c = A.Session(sim4.case)
                s4c.enter()
                res = s4c.measure(omni.x + 200 * math.cos(rad),
                                  omni.y + 200 * math.sin(rad), omni.channel)
                if res.payload.get("measure_result") in ("direction", "near"):
                    hits += 1
            r.eq("omni jammer detectable from all 4 sides", hits, 4)
        direc = next((j for j in sim4.case.jammers if j.directional), None)
        if direc is not None:
            # 定向源只朝 bearing_deg 一侧辐射: 站在它背后则收不到信号。
            # 注意 covered() 判据是"检测点指向干扰源的方向与定向方向夹角 <= 90°",
            # 因此"背后"= 检测点位于 jammer 沿定向方向的反方向一侧。
            rad = math.radians(direc.bearing_deg)
            px = direc.x + 200.0 * math.cos(rad)   # 正对波束
            py = direc.y + 200.0 * math.sin(rad)
            bx = direc.x - 200.0 * math.cos(rad)   # 波束背后
            by = direc.y - 200.0 * math.sin(rad)
            r.check("point in front of the beam is covered",
                    direc.covered(px, py), f"(bearing {direc.bearing_deg:.2f})")
            r.check("point behind the beam is not covered",
                    not direc.covered(bx, by),
                    f"(bearing {direc.bearing_deg:.2f}, point ({bx:.1f},{by:.1f}))")
            s4d = A.Session(sim4.case)
            s4d.enter()
            res = s4d.measure(bx, by, direc.channel)
            r.eq("directional jammer behind its beam -> no_signal",
                 res.payload.get("measure_result"), "no_signal")
            s4d2 = A.Session(sim4.case)
            s4d2.enter()
            res2 = s4d2.measure(px, py, direc.channel)
            r.eq("directional jammer inside its beam -> direction",
                 res2.payload.get("measure_result"), "direction")
        # 有效半径: 距离 > 1500 m 时任何源都收不到
        s4e = A.Session(sim4.case)
        s4e.enter()
        res = s4e.measure(j0.x + 1600.0, j0.y, j0.channel)
        r.eq("beyond 1500 m -> no_signal", res.payload.get("measure_result"), "no_signal")
        # near 阈值 5 m
        s4f = A.Session(sim4.case)
        s4f.enter()
        res = s4f.measure(j0.x + 4.0, j0.y, j0.channel)
        if j0.directional and not j0.covered(j0.x + 4.0, j0.y):
            r.notes.append("near-threshold check skipped (jammer faces away)")
        else:
            r.eq("distance <= 5 m -> near", res.payload.get("measure_result"), "near")
        # 清除半径 20 m 与单次性
        s4g = A.Session(sim4.case)
        s4g.enter()
        r.eq("clear at 20 m -> success",
             s4g.clear(j0.x + 20.0, j0.y, j0.channel).payload["clear_result"], "success")
        r.eq("clearing the same jammer twice -> no_target_in_range",
             s4g.clear(j0.x + 20.0, j0.y, j0.channel).payload["clear_result"],
             "no_target_in_range")
        s4h = A.Session(sim4.case)
        s4h.enter()
        r.eq("clear at 20.01 m -> no_target_in_range",
             s4h.clear(j0.x + 20.01, j0.y, j0.channel).payload["clear_result"],
             "no_target_in_range")
        # /clear 不改当前频道
        s4i = A.Session(sim4.case)
        s4i.enter()
        s4i.measure(0, 0, 5)
        before = s4i.current_channel
        s4i.clear(0, 0, 9)
        r.eq("/clear does not change the receiver channel", s4i.current_channel, before)
        # 案例合法性
        r.check("jammer count within 10..16",
                A.JAMMER_COUNT_MIN <= sim4.case.total <= A.JAMMER_COUNT_MAX)
        r.check("channels unique and within 1..20",
                len({j.channel for j in sim4.case.jammers}) == sim4.case.total
                and all(1 <= j.channel <= 20 for j in sim4.case.jammers))
        r.check("effective radius within 1000..1500 m",
                all(1000.0 <= j.eff_radius <= 1500.0 for j in sim4.case.jammers))
        r.check("all jammers inside the 1800 m arena",
                all(math.hypot(j.x, j.y) <= 1800.0 for j in sim4.case.jammers))
        r.check("problem 4 case contains both omni and directional jammers",
                sim4.case.omni_count >= 1 and sim4.case.directional_count >= 1)
        p3 = A.make_case(problem=3, seed=5, count=10)
        r.eq("problem 3 case is all-omni", p3.directional_count, 0)
        # 误差在全局范围内统计上覆盖 [-1,1]
        samples = [A.svd_error_deg(i * 13.7, i * 7.3, "s") for i in range(4000)]
        r.check("svd error inside [-1,1]",
                all(-1.0 <= v <= 1.0 for v in samples))
        r.check("svd error spans most of [-1,1]",
                min(samples) < -0.95 and max(samples) > 0.95,
                f"(min {min(samples):.3f}, max {max(samples):.3f})")
        mean = sum(samples) / len(samples)
        r.check("svd error mean near 0", abs(mean) < 0.05, f"(mean {mean:.4f})")

        # ==============================================================
        print("\n[13] 现实时间约束 (附件2 §4.5, §6.2)")
        time.sleep(0.3)   # 让前面的服务器线程完全退出
        sim5 = MockSimulator(problem=3, mode="practice", seed=99, count=10, team_id=TEAM,
                             port=0, real_limit_s=2.0, window_s=30.0)
        httpd5 = serve(sim5)
        url5 = f"http://127.0.0.1:{httpd5.server_address[1]}"
        threading.Thread(target=httpd5.serve_forever, daemon=True).start()
        sim5.start()
        st, resp = jpost(url5, "/enter", body(request_id="real-enter"))
        r.eq("/enter accepted under a short real limit", resp.get("accepted"), True)
        r.check("remaining_real_duration_s <= 1200 and >= 0",
                0 <= resp.get("remaining_real_duration_s", -1) <= 1200,
                f"(got {resp.get('remaining_real_duration_s')})")
        r.check("remaining respects the configured 2 s program limit",
                resp.get("remaining_real_duration_s", 99) <= 2,
                f"(got {resp.get('remaining_real_duration_s')})")
        time.sleep(2.4)
        sim5.tick()
        st, resp = jpost(url5, "/measure", ride(position={"x": 10, "y": 0}, channel=1))
        r.eq("after the real deadline the interface closes", st, -1)
        r.eq("end reason recorded as program_timeout",
             sim5.live.end_reason if sim5.live else None, "program_timeout")
        r.eq("completion summary reports the reason",
             sim5.result_summary().get("end_reason"), "program_timeout")
        httpd5.shutdown()

    finally:
        httpd.shutdown()

    print("\n" + "=" * 62)
    print(f"conformance: {r.passed} passed, {len(r.failed)} failed")
    for f in r.failed:
        print(f"  FAILED: {f}")
    for n in r.notes:
        print(f"  note: {n}")
    return 1 if r.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
