# -*- coding: utf-8 -*-
"""mock simulator HTTP layer: /enter /measure /clear /exit per 附件2.

Implements, from the published specification only:

* request validation -> HTTP 400/404/405/409/413/415/429 with JSON bodies
* unknown declared-path fields -> HTTP 200 + accepted=false
* per-session request_id idempotency (replay / 409 on differing content)
* virtual clock arithmetic (microsecond based, <=6 decimals in responses)
* real-time watchdog: 25-minute window and 20-minute program run limit

Run:  python -m mocksim.server --problem 3 --practice
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import arena as A

# 本机回环地址必须绕过系统代理 (Windows 上常见的 HTTP_PROXY/HTTPS_PROXY 会把
# 发往 127.0.0.1:2026 的请求转发给代理, 得到 502/407, 与模拟器本身无关).
NO_PROXY = ("127.0.0.1", "localhost", "::1", "[::1]")

# --------------------------------------------------------------------------
# JSON parsing with duplicate-key and depth rejection
# --------------------------------------------------------------------------


class BadJson(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise BadJson(f"duplicate key: {k}")
        out[k] = v
    return out


def _depth(obj: Any, level: int = 1) -> int:
    if isinstance(obj, dict):
        return max([level] + [_depth(v, level + 1) for v in obj.values()])
    if isinstance(obj, list):
        return max([level] + [_depth(v, level + 1) for v in obj])
    return level


def load_strict_json(raw: bytes) -> dict[str, Any]:
    """无 BOM 的 UTF-8 JSON 对象, 不允许重复键, 嵌套不超过 16 层."""
    if raw[:3] == b"\xef\xbb\xbf":
        raise BadJson("UTF-8 BOM is not allowed")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BadJson(f"body is not valid UTF-8: {exc}") from exc
    try:
        obj = json.loads(text, object_pairs_hook=_no_duplicates)
    except BadJson:
        raise
    except json.JSONDecodeError as exc:
        raise BadJson(f"invalid JSON: {exc.msg} at pos {exc.pos}") from exc
    if not isinstance(obj, dict):
        raise BadJson("top level value must be a JSON object")
    if _depth(obj) > A.MAX_JSON_DEPTH:
        raise BadJson(f"JSON nesting exceeds {A.MAX_JSON_DEPTH} levels")
    return obj


# --------------------------------------------------------------------------
# Field validation helpers
# --------------------------------------------------------------------------


class BadField(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


CONTROL_OR_FORMAT = set(range(0x00, 0x21)) | {0x7F} | set(range(0x80, 0xA0))


def _check_id(value: Any, name: str, max_bytes: int) -> str:
    if not isinstance(value, str):
        raise BadField(f"{name} must be a string")
    raw = value.encode("utf-8")
    if not (A.ID_BYTE_MIN <= len(raw) <= max_bytes):
        raise BadField(f"{name} UTF-8 length must be 1..{max_bytes} bytes")
    for ch in value:
        if ord(ch) in CONTROL_OR_FORMAT or ch.isspace():
            raise BadField(f"{name} must not contain control/space/format characters")
    return value


def _check_channel(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BadField("channel must be an integer in 1..20")
    if isinstance(value, float):
        if not value.is_integer():
            raise BadField("channel must be an integer in 1..20")
        value = int(value)
    if not (A.CHANNEL_MIN <= value <= A.CHANNEL_MAX):
        raise BadField("channel must be an integer in 1..20")
    return int(value)


def _check_position(value: Any) -> tuple[float, float]:
    if not isinstance(value, dict):
        raise BadField("position must be an object")
    unknown = set(value) - {"x", "y"}
    if unknown:
        raise BadField(f"unknown position field(s): {sorted(unknown)}")
    for key in ("x", "y"):
        if key not in value:
            raise BadField(f"position.{key} is required")
    coords = []
    for key in ("x", "y"):
        v = value[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise BadField(f"position.{key} must be a finite number")
        fv = float(v)
        if fv != fv or fv in (float("inf"), float("-inf")):
            raise BadField(f"position.{key} must be finite (NaN/Inf rejected)")
        if abs(fv) > A.COORD_LIMIT_M:
            raise BadField(f"position.{key} absolute value must be <= {A.COORD_LIMIT_M}")
        coords.append(fv)
    return coords[0], coords[1]


# Declared field sets per action (附件2 §6..§9).  Any other key -> accepted=false.
FIELDS = {
    "/enter": {"enter": {"arena_id", "robot_id", "request_id"}},
    "/measure": {"measure": {"arena_id", "robot_id", "request_id", "position", "channel"}},
    "/clear": {"clear": {"arena_id", "robot_id", "request_id", "position", "channel"}},
    "/exit": {"exit": {"arena_id", "robot_id", "request_id"}},
}


# --------------------------------------------------------------------------
# Test lifecycle
# --------------------------------------------------------------------------


@dataclass
class IdemRecord:
    body_hash: str
    status: int
    response: dict[str, Any]


@dataclass
class LiveTest:
    """一局正在进行 (接口已开放) 的测试。"""

    session: A.Session
    mode: str                                 # practice | formal
    window_started: float
    real_limit_s: float
    virtual_limit_s: float
    window_duration_s: float = A.WINDOW_DURATION_S

    def __post_init__(self) -> None:
        self.entry_wall: float | None = None
        self.enter_wall: float | None = None
        self.end_wall: float | None = None
        self.end_reason: str | None = None
        self.entered_robot: str | None = None
        self.idem: dict[str, IdemRecord] = {}
        self.busy = False
        self.log: list[dict[str, Any]] = []
        self.request_seq = 0
        self.lock = threading.RLock()

    # -- deadlines -------------------------------------------------------
    @property
    def window_deadline(self) -> float:
        return self.window_started + self.window_duration_s

    def program_deadline(self) -> float | None:
        if self.enter_wall is None:
            return None
        return self.enter_wall + self.real_limit_s

    def remaining_real_s(self) -> int:
        now = time.monotonic()
        deadlines = [self.window_deadline]
        pd = self.program_deadline()
        if pd is not None:
            deadlines.append(pd)
        return max(0, int(min(deadlines) - now))

    def real_expired(self) -> bool:
        now = time.monotonic()
        if now >= self.window_deadline:
            return True
        pd = self.program_deadline()
        return pd is not None and now >= pd

    def program_runtime_s(self) -> float:
        if self.enter_wall is None:
            return 0.0
        end = self.end_wall if self.end_wall is not None else time.monotonic()
        return round(end - self.enter_wall, 6)

    def virtual_expired(self) -> bool:
        return self.session.virtual_time_s >= self.virtual_limit_s

    def finished(self) -> bool:
        return self.end_reason is not None

    def finish(self, reason: str) -> None:
        if self.end_reason is None:
            self.end_reason = reason
            self.end_wall = time.monotonic()

    # -- logging ---------------------------------------------------------
    def record(self, kind: str, request_id: str | None, status: int,
               payload: dict[str, Any] | None, response: dict[str, Any],
               extra: dict[str, Any] | None = None) -> None:
        self.request_seq += 1
        entry = {
            "seq": self.request_seq,
            "wall_ms": int(time.time() * 1000),
            "kind": kind,
            "request_id": request_id,
            "http_status": status,
            "request": payload,
            "response": response,
        }
        if extra:
            entry.update(extra)
        self.log.append(entry)


# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------


class MockSimulator:
    """模拟器状态机 + 请求校验。可独立于 HTTP 层被测试套件直接驱动。"""

    def __init__(self, *, problem: int = 3, mode: str = "practice",
                 seed: int | None = None, count: int | None = None,
                 team_id: str = "TEAM0000", port: int = 2026,
                 svd_salt: str = "", virtual_limit_s: float = A.MAX_VIRTUAL_DURATION_S,
                 real_limit_s: float = A.MAX_REAL_DURATION_S,
                 window_s: float = A.WINDOW_DURATION_S,
                 expose_truth: bool = True, clock_scale: float = 1.0) -> None:
        self.problem = problem
        self.mode = mode
        self.team_id = team_id
        self.port = port
        self.seed = seed
        self.count = count
        self.svd_salt = svd_salt
        self.virtual_limit_s = virtual_limit_s
        self.real_limit_s = real_limit_s
        self.window_s = window_s
        self.expose_truth = expose_truth and mode == "practice"
        self.clock_scale = clock_scale

        self.lock = threading.RLock()
        self.case = A.make_case(problem=problem, seed=seed, count=count)
        self.status = "idle"          # idle | running | finished
        self.live: LiveTest | None = None
        self.last_finished: LiveTest | None = None
        self.finished_tests: list[dict[str, Any]] = []
        self.started_wall: float = 0.0
        self.idem_limit = 200000
        self.verbose = False
        self.enable_debug = False

    # -- lifecycle -------------------------------------------------------
    def start(self) -> None:
        with self.lock:
            if self.status == "running":
                raise RuntimeError("a test is already running")
            session = A.Session(self.case, svd_salt=self.svd_salt)
            self.live = LiveTest(session=session, mode=self.mode,
                                 window_started=time.monotonic(),
                                 real_limit_s=self.real_limit_s,
                                 virtual_limit_s=self.virtual_limit_s)
            self.live.window_duration_s = self.window_s
            self.status = "running"
            self.started_wall = time.monotonic()

    def new_case(self, *, seed: int | None = None, count: int | None = None,
                 problem: int | None = None) -> None:
        with self.lock:
            if problem is not None:
                self.problem = problem
            if seed is not None:
                self.seed = seed
            if count is not None:
                self.count = count
            self.case = A.make_case(problem=self.problem, seed=self.seed,
                                    count=self.count)
            self.status = "idle"
            self.live = None

    def result_summary(self) -> dict[str, Any]:
        with self.lock:
            live = self.live
            if live is None:
                return {"status": self.status}
            session = live.session
            out: dict[str, Any] = {
                "status": "finished" if live.finished() else "running",
                "case_code": self.case.case_code,
                "problem": self.problem,
                "mode": self.mode,
                "end_reason": live.end_reason,
                **session.statistics(live.program_runtime_s()),
            }
            if self.expose_truth:
                out["jammer_total"] = self.case.total
                out["omni_count"] = self.case.omni_count
                out["directional_count"] = self.case.directional_count
            return out

    # -- generic guards --------------------------------------------------
    def _open(self) -> None:
        """接口未开放时连接可能被直接关闭 -> 由 HTTP 层抛 ConnectionClosed。"""
        if self.status != "running" or self.live is None:
            raise ConnectionClosed("robot interface is not open")
        if self.live.finished():
            raise ConnectionClosed("test already finished")

    def _error_body(self, detail: str) -> dict[str, Any]:
        vtime = 0.0
        if self.live is not None:
            vtime = self.live.session.virtual_time_s
        return {
            "accepted": False,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": A.quantise_time(vtime),
            "detail": detail,
        }

    def _guard_common(self, action: str, payload: dict[str, Any],
                      base: dict[str, Any]) -> int | None:
        """通用校验。返回 HTTP 状态码表示应拒绝(200 accepted=false); None 表示通过。

        抛 BadField -> 400。
        """
        declared = FIELDS[action][action.strip("/")]
        unknown = set(payload) - declared
        if unknown:
            base["accepted"] = False
            base["detail"] = f"unknown field(s): {sorted(unknown)}"
            return 200
        for key in ("arena_id", "robot_id", "request_id"):
            if key not in payload:
                raise BadField(f"{key} is required")
        if not isinstance(payload["arena_id"], str):
            raise BadField("arena_id must be a string")
        _check_id(payload["robot_id"], "robot_id", A.ID_BYTE_MAX)
        _check_id(payload["request_id"], "request_id", A.REQ_ID_BYTE_MAX)
        if payload["arena_id"] != "default":
            base["detail"] = "arena_id must be 'default'"
            return 200
        if payload["robot_id"] != self.team_id:
            base["detail"] = "robot_id does not match the logged-in team id"
            return 200
        return None

    # -- dispatch --------------------------------------------------------
    def handle(self, action: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if action not in ("enter", "measure", "clear", "exit"):
            return 404, self._error_body("unknown path")
        with self.lock:
            return self._handle_locked(action, payload)

    def _error_body(self, detail: str) -> dict[str, Any]:
        vtime = 0.0
        if self.live is not None:
            vtime = self.live.session.virtual_time_s
        return {
            "accepted": False,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": A.quantise_time(vtime),
            "detail": detail,
        }

    def _handle_locked(self, action: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        self._open()
        assert self.live is not None
        live = self.live
        path = "/" + action

        # 1) field validation (400 / accepted=false for unknown fields)
        base: dict[str, Any] = {
            "accepted": False,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": A.quantise_time(live.session.virtual_time_s),
        }
        guard = self._guard_common(path, payload, base)
        if guard is not None:
            live.record(action, payload.get("request_id"), guard, payload, base)
            return guard, base

        # 2) idempotency
        request_id = payload["request_id"]
        canon = json.dumps({"action": action, "body": payload},
                           sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        body_hash = hashlib.blake2b(canon.encode("utf-8"), digest_size=16).hexdigest()
        prev = live.idem.get(request_id)
        if prev is not None:
            if prev.body_hash != body_hash:
                body = self._error_body("request_id reused with different action/content")
                body["accepted"] = False
                return 409, body
            return prev.status, prev.response
        if len(live.idem) >= self.idem_limit:
            return 429, self._error_body("idempotency record limit reached")

        # 3) action specific validation
        if action in ("measure", "clear"):
            if "position" not in payload:
                raise BadField("position is required")
            if "channel" not in payload:
                raise BadField("channel is required")
            x, y = _check_position(payload["position"])
            channel = _check_channel(payload["channel"])
        # 4) state machine
        if action == "enter":
            if live.session.entered:
                base["detail"] = "duplicate /enter"
                self._commit(live, action, request_id, body_hash, 200, base, payload)
                return 200, base
            if live.entered_robot is not None:
                base["detail"] = "another robot already entered"
                self._commit(live, action, request_id, body_hash, 200, base, payload)
                return 200, base
            live.enter_wall = time.monotonic()
            live.entered_robot = payload["robot_id"]
            outcome = live.session.enter()
            response = {
                "accepted": True,
                "real_timestamp_ms": int(time.time() * 1000),
                "virtual_time_s": A.quantise_time(outcome.virtual_time_s),
                "max_virtual_duration_s": self.virtual_limit_s,
                "max_real_duration_s": self.real_limit_s,
                "remaining_real_duration_s": live.remaining_real_s(),
            }
            self._commit(live, action, request_id, body_hash, 200, response, payload,
                         extra={"move_s": 0.0, "switch_s": 0.0, "action_s": 0.0})
            return 200, response

        if action == "exit":
            if not live.session.entered:
                base["detail"] = "/enter must succeed before /exit"
                self._commit(live, action, request_id, body_hash, 200, base, payload)
                return 200, base
            outcome = live.session.exit()
            response = {
                "accepted": True,
                "real_timestamp_ms": int(time.time() * 1000),
                "virtual_time_s": A.quantise_time(outcome.virtual_time_s),
                "exit_reason": "user_exit",
            }
            live.finish("user_exit")
            self._commit(live, action, request_id, body_hash, 200, response, payload)
            return 200, response

        # measure / clear need an open session
        if not live.session.entered:
            base["detail"] = "/enter must succeed before this action"
            self._commit(live, action, request_id, body_hash, 200, base, payload)
            return 200, base

        if action == "measure":
            outcome = live.session.measure(x, y, channel)
        else:
            outcome = live.session.clear(x, y, channel)
        response = {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": A.quantise_time(outcome.virtual_time_s),
            **outcome.payload,
        }
        self._commit(live, action, request_id, body_hash, 200, response, payload,
                     extra={"move_s": outcome.move_s, "switch_s": outcome.switch_s,
                            "action_s": outcome.action_s,
                            "elapsed_s": A.quantise_time(outcome.total_s),
                            "position": {"x": x, "y": y}, "channel": channel})
        if live.session.virtual_expired:
            live.finish("virtual_timeout")
        if live.session.remaining_count == 0 and not live.session.exited:
            pass  # 由机器狗主动 /exit; 模拟器不代为结束
        return 200, response

    def _commit(self, live: LiveTest, action: str, request_id: str, body_hash: str,
                status: int, response: dict[str, Any], payload: dict[str, Any],
                extra: dict[str, Any] | None = None) -> None:
        if response.get("accepted") is False and status == 200:
            # 结构错误/未知字段/不匹配不占用 request_id (附件2 §5.3)
            live.record(action, request_id, status, payload, response, extra)
            return
        live.idem[request_id] = IdemRecord(body_hash=body_hash, status=status,
                                          response=response)
        live.record(action, request_id, status, payload, response, extra)

    # -- watchdog --------------------------------------------------------
    def tick(self) -> None:
        with self.lock:
            live = self.live
            if live is None or live.finished():
                return
            if live.real_expired():
                live.finish("window_timeout" if not live.session.entered
                            else "program_timeout")
            elif live.virtual_expired():
                live.finish("virtual_timeout")


class ConnectionClosed(Exception):
    """接口未开放/测试已结束: 直接关闭连接, 没有 JSON 响应 (附件2 §5.3)."""


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "MockJammers/1.0"
    protocol_version = "HTTP/1.1"
    sim: MockSimulator  # injected

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        if self.sim.verbose:
            print(f"[http] {self.address_string()} {fmt % args}")

    # -- helpers ---------------------------------------------------------
    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(raw)

    def _drop(self) -> None:
        """直接关闭 TCP 连接 (接口未开放 / 测试已结束).

        附件2 §5.3: "连接可能被直接关闭，此时没有JSON体"。
        因此不发任何 HTTP 响应, 客户端应把它当作"连不上"而不是错误码。
        """
        self.close_connection = True
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.connection.close()
        except Exception:
            pass

    def do_GET(self) -> None:  # noqa: N802
        if self.sim.enable_debug and self.path.startswith("/debug"):
            return self._debug_get()
        self._send_json(405, self.sim._error_body("only POST is allowed"))

    def do_POST(self) -> None:  # noqa: N802
        sim = self.sim
        # path must be exact: no trailing slash, no query string
        if self.path not in ("/enter", "/measure", "/clear", "/exit"):
            self._send_json(404, sim._error_body(f"unknown or inexact path: {self.path}"))
            return
        ctype = self.headers.get("Content-Type", "")
        parts = [p.strip() for p in ctype.split(";")] if ctype else []
        media = parts[0].lower() if parts else ""
        params = {p.split("=")[0].strip().lower() for p in parts[1:] if p}
        if media != "application/json" or params - {"charset"}:
            self._send_json(415, sim._error_body("unsupported Content-Type"))
            return
        if params == {"charset"}:
            charset = [p for p in parts[1:] if p.lower().startswith("charset")][0]
            if charset.split("=", 1)[1].strip().strip('"').lower() != "utf-8":
                self._send_json(415, sim._error_body("only charset=utf-8 is supported"))
                return
        enc = self.headers.get("Content-Encoding", "identity").strip().lower()
        if enc not in ("", "identity"):
            self._send_json(415, sim._error_body("Content-Encoding must be identity or absent"))
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send_json(400, sim._error_body("bad Content-Length"))
            return
        if length > A.BODY_LIMIT_BYTES:
            self._send_json(413, sim._error_body("body exceeds 65536 bytes"))
            return
        raw = self.rfile.read(length) if length else b""
        try:
            payload = load_strict_json(raw)
        except BadJson as exc:
            self._send_json(400, sim._error_body(exc.message))
            return
        action = self.path[1:]
        try:
            status, body = sim.handle(action, payload)
        except BadField as exc:
            self._send_json(400, sim._error_body(exc.message))
            return
        except ConnectionClosed:
            self._drop()
            return
        except Exception as exc:  # pragma: no cover - defensive
            import traceback
            traceback.print_exc()
            self._send_json(500, sim._error_body(f"internal error: {exc!r}"))
            return
        self._send_json(status, body)

    # -- debug (only with --expose-debug) --------------------------------
    def _debug_get(self) -> None:
        sim = self.sim
        if self.path.startswith("/debug/truth"):
            self._send_json(200, {
                "case_code": sim.case.case_code,
                "problem": sim.problem,
                "total": sim.case.total,
                "omni_count": sim.case.omni_count,
                "directional_count": sim.case.directional_count,
                "jammers": sim.case.truth_table(),
            })
        elif self.path.startswith("/debug/status"):
            self._send_json(200, sim.result_summary())
        elif self.path.startswith("/debug/log"):
            live = sim.live
            self._send_json(200, {"log": live.log if live else []})
        else:
            self._send_json(404, {"detail": "unknown debug path"})


def serve(sim: MockSimulator, *, host: str = "127.0.0.1",
          expose_debug: bool = False, verbose: bool = False) -> ThreadingHTTPServer:
    sim.verbose = verbose
    sim.enable_debug = expose_debug
    handler = type("BoundHandler", (Handler,), {"sim": sim})
    try:
        httpd = ThreadingHTTPServer((host, sim.port), handler)
    except OSError as exc:
        raise SystemExit(
            f"无法监听 {host}:{sim.port} ({exc}).\n"
            f"端口可能已被占用 (例如官方模拟器或上一次未退出的实例), "
            f"请改用 --port 指定其他端口, 或先释放该端口。"
        ) from exc
    httpd.daemon_threads = True
    stop = threading.Event()
    httpd._mock_stop = stop  # type: ignore[attr-defined]

    def watchdog() -> None:
        while not stop.wait(0.02):
            sim.tick()
            if sim.live is not None and sim.live.finished() and sim.status == "running":
                sim.status = "finished"
                sim.last_finished = sim.live
                sim.finished_tests.append(sim.result_summary())

    thread = threading.Thread(target=watchdog, daemon=True, name="mocksim-watchdog")
    thread.start()
    httpd._mock_watchdog = thread  # type: ignore[attr-defined]

    original_close = httpd.server_close

    def server_close() -> None:
        stop.set()
        thread.join(timeout=1.0)
        original_close()

    httpd.server_close = server_close  # type: ignore[method-assign]
    return httpd


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Local mock jammers simulator (CUMCM 2026 B)")
    ap.add_argument("--problem", type=int, default=3, choices=(3, 4))
    ap.add_argument("--mode", default="practice", choices=("practice", "formal"))
    ap.add_argument("--port", type=int, default=2026)
    ap.add_argument("--seed", type=int, default=None, help="fix the case seed for reproducibility")
    ap.add_argument("--count", type=int, default=None, help="jammer count 10..16")
    ap.add_argument("--team", default="TEAM0000", help="robot_id the client must use")
    ap.add_argument("--virtual-limit", type=float, default=A.MAX_VIRTUAL_DURATION_S)
    ap.add_argument("--real-limit", type=float, default=A.MAX_REAL_DURATION_S)
    ap.add_argument("--window", type=float, default=A.WINDOW_DURATION_S)
    ap.add_argument("--expose-debug", action="store_true",
                    help="enable GET /debug/truth|status|log on the same port")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    sim = MockSimulator(problem=args.problem, mode=args.mode, seed=args.seed,
                        count=args.count, team_id=args.team, port=args.port,
                        virtual_limit_s=args.virtual_limit, real_limit_s=args.real_limit,
                        window_s=args.window)
    httpd = serve(sim, expose_debug=args.expose_debug, verbose=args.verbose)
    sim.start()
    print(f"mock simulator listening on http://127.0.0.1:{args.port}")
    print(f"  problem={args.problem} mode={args.mode} case={sim.case.case_code} "
          f"jammers={sim.case.total}")
    print(f"  robot_id must be {args.team!r}; /enter now open")
    if args.expose_debug:
        print(f"  debug: http://127.0.0.1:{args.port}/debug/truth")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("\n--- final summary ---")
        print(json.dumps(sim.result_summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
