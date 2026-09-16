"""Bounded HTTP demo service: ``python -m nl2opt.api``.

For public hosting, put a TLS reverse proxy in front of this private service.
No user-supplied code, ProblemSpec, file path, or model endpoint is accepted.
"""
from __future__ import annotations

import hmac
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from nl2opt.api_contract import MAX_BODY_BYTES, ApiError, envelope, fail, validate_request


@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = ""
    public_demo: bool = False
    allowed_origins: tuple[str, ...] = ()
    concurrency: int = 2
    deadline_sec: float = 30
    solver_timeout_sec: float = 10
    model_timeout_sec: float = 18
    requests_per_minute: int = 12
    global_per_minute: int = 40
    text_per_day: int = 50
    revision: str = "unversioned"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            host=os.environ.get("NL2OPT_HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", os.environ.get("NL2OPT_PORT", "8765"))),
            token=os.environ.get("NL2OPT_API_TOKEN", "").strip(),
            public_demo=os.environ.get("NL2OPT_PUBLIC_DEMO", "") == "1",
            allowed_origins=tuple(filter(None, (s.strip() for s in os.environ.get("NL2OPT_ALLOWED_ORIGINS", "").split(",")))),
            revision=os.environ.get("NL2OPT_REVISION", "unversioned")[:80],
            text_per_day=int(os.environ.get("NL2OPT_TEXT_REQUESTS_PER_DAY", "50")),
        )

    @property
    def local_only(self) -> bool:
        return self.host == "localhost" or self.host == "::1" or self.host.startswith("127.")

    def validate(self) -> None:
        if not self.local_only and not self.token and not self.public_demo:
            raise ValueError("Remote binding requires NL2OPT_API_TOKEN or NL2OPT_PUBLIC_DEMO=1.")
        if self.token and len(self.token) < 24:
            raise ValueError("NL2OPT_API_TOKEN must contain at least 24 characters.")
        if not 0 <= self.text_per_day <= 1000:
            raise ValueError("NL2OPT_TEXT_REQUESTS_PER_DAY must be between 0 and 1000.")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
                raise ValueError("Allowed origins must be explicit HTTP(S) origins, without paths.")


class RateLimiter:
    """Bounded in-memory counters. Persistent spending limits belong at the gateway."""
    def __init__(self, config: Config):
        self.config, self.lock = config, threading.Lock()
        self.clients: dict[str, deque[float]] = defaultdict(deque)
        self.global_requests: deque[float] = deque()
        self.text_requests: deque[float] = deque()

    def allow(self, address: str, text_mode: bool, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self.lock:
            for queue, interval in [(self.global_requests, 60), (self.text_requests, 86400)]:
                while queue and now - queue[0] >= interval:
                    queue.popleft()
            for key in list(self.clients):
                queue = self.clients[key]
                while queue and now - queue[0] >= 60:
                    queue.popleft()
                if not queue:
                    del self.clients[key]
            queue = self.clients[address]
            if (len(queue) >= self.config.requests_per_minute
                    or len(self.global_requests) >= self.config.global_per_minute
                    or (text_mode and len(self.text_requests) >= self.config.text_per_day)):
                if not queue:
                    del self.clients[address]
                return False
            queue.append(now)
            self.global_requests.append(now)
            if text_mode:
                self.text_requests.append(now)
            return True


def model_configured() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def run_isolated(config: Config, operation: str, data: dict[str, Any], payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    request = {"operation": operation, "data": data, "envelope": payload,
               "solver_timeout_sec": config.solver_timeout_sec, "model_timeout_sec": config.model_timeout_sec}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="nl2opt-api-") as directory:
        process = subprocess.Popen(
            [sys.executable, "-m", "nl2opt.api_worker", directory],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, start_new_session=True,
        )
        try:
            stdout, _ = process.communicate(json.dumps(request, allow_nan=False), timeout=config.deadline_sec)
        except subprocess.TimeoutExpired:
            # The worker and generated solver share a fresh process group. Stop
            # both, so a request timeout cannot leave expensive solver work alive.
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.communicate()
            payload["diagnostics"].update(elapsed_ms=round((time.monotonic() - started) * 1000), timed_out=True)
            return fail(payload, ApiError("REQUEST_TIMEOUT", "请求超过整体时限，运行已终止。", "deadline", 504))
        try:
            result = json.loads(stdout)
            if process.returncode or not isinstance(result["payload"], dict):
                raise ValueError("invalid worker output")
            result["payload"]["diagnostics"]["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            return result["http_status"], result["payload"]
        except (ValueError, KeyError, TypeError):
            return fail(payload, ApiError("WORKER_FAILED", "隔离进程未返回有效结果。", "internal", 500))


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, config: Config):
        config.validate()
        self.config = config
        self.limiter = RateLimiter(config)
        self.workers = threading.BoundedSemaphore(config.concurrency)
        self.connections = threading.BoundedSemaphore(8)
        super().__init__((config.host, config.port), Handler)

    def process_request(self, request: socket.socket, client_address: Any) -> None:
        if not self.connections.acquire(blocking=False):
            request.settimeout(1)
            body = json.dumps(fail(envelope("unknown", "rejected_request", self.config.revision),
                              ApiError("SERVER_BUSY", "服务器正在处理其他请求，请稍后重试。", "admission", 503))[1]).encode()
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: "
                                + str(len(body)).encode() + b"\r\n\r\n" + body)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.connections.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()


class Handler(BaseHTTPRequestHandler):
    server: Server
    server_version = "NL2OPT"
    sys_version = ""

    def setup(self) -> None:
        self.request.settimeout(5)
        super().setup()

    def log_message(self, *_args: Any) -> None:
        # Do not put question text, request paths, credentials, or errors in logs.
        pass

    def _send(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        origin = self.headers.get("Origin")
        if origin in self.server.config.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if status in {429, 503}:
            self.send_header("Retry-After", "60")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _boundary(self) -> None:
        config = self.server.config
        origin = self.headers.get("Origin")
        if origin and origin not in config.allowed_origins:
            raise ApiError("ORIGIN_NOT_ALLOWED", "此来源未获准访问演示服务。", "admission", 403)
        if config.local_only:
            host = urlsplit("//" + self.headers.get("Host", "")).hostname
            try:
                local = host == "localhost" or bool(host and ipaddress.ip_address(host).is_loopback)
            except ValueError:
                local = False
            if not local:
                raise ApiError("HOST_NOT_ALLOWED", "本地服务仅接受本机地址。", "admission", 403)

    def _authenticated(self) -> bool:
        config = self.server.config
        expected = "Bearer " + config.token
        actual = self.headers.get("Authorization", "")
        return bool(config.token) and hmac.compare_digest(actual.encode(), expected.encode())

    def _require_auth(self, text_mode: bool = False) -> None:
        config = self.server.config
        if text_mode or (not config.local_only and not config.public_demo):
            if not self._authenticated():
                raise ApiError("AUTH_REQUIRED", "此接口需要服务器访问凭据。", "admission", 401)

    def do_OPTIONS(self) -> None:
        try:
            self._boundary()
            if self.path not in {"/api/v1/nl2opt/health", "/api/v1/nl2opt/solve", "/api/v1/nl2opt/check"}:
                raise ApiError("NOT_FOUND", "接口不存在。", "admission", 404)
            self._send(200, {"status": "ok"})
        except ApiError as exc:
            self._send(*fail(envelope("unknown", "rejected_request", self.server.config.revision), exc))

    def do_GET(self) -> None:
        try:
            self._boundary()
            if self.path != "/api/v1/nl2opt/health":
                raise ApiError("NOT_FOUND", "接口不存在；运行记录仅在本次响应中返回。", "admission", 404)
            self._require_auth()
            configured = model_configured()
            self._send(200, {
                "status": "ok", "service": "nl2opt", "api_version": "v1",
                "deepseek_configured": configured,
                "capabilities": {"production": True, "check": True,
                                 "text": configured and self._authenticated() and self.server.config.text_per_day > 0},
                "text_requires_authorization": True,
                "limits": {"max_text_length": 2000, "max_body_bytes": MAX_BODY_BYTES,
                           "capacity_range": [1, 200], "deadline_sec": self.server.config.deadline_sec,
                           "solver_timeout_sec": self.server.config.solver_timeout_sec,
                           "concurrency": self.server.config.concurrency},
                "revision": self.server.config.revision,
            })
        except (ApiError, ValueError) as exc:
            if not isinstance(exc, ApiError):
                exc = ApiError("INVALID_HOST", "无效的服务地址。", "admission", 400)
            self._send(*fail(envelope("unknown", "rejected_request", self.server.config.revision), exc))

    def do_POST(self) -> None:
        payload = envelope("unknown", "rejected_request", self.server.config.revision)
        try:
            self._boundary()
            paths = {"/api/v1/nl2opt/solve": "solve", "/api/v1/nl2opt/check": "check"}
            operation = paths.get(self.path)
            if operation is None:
                raise ApiError("NOT_FOUND", "接口不存在。", "admission", 404)
            self._require_auth()
            if self.headers.get("Transfer-Encoding"):
                raise ApiError("INVALID_BODY", "不支持流式请求体。")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not lengths[0].isdigit():
                raise ApiError("LENGTH_REQUIRED", "必须提供单一有效 Content-Length。", http_status=411)
            size = int(lengths[0])
            if not 0 < size <= MAX_BODY_BYTES:
                raise ApiError("BODY_TOO_LARGE", "请求体必须在 1 至 16384 字节之间。", http_status=413)
            if self.headers.get_content_type() != "application/json":
                raise ApiError("UNSUPPORTED_MEDIA_TYPE", "请求必须使用 application/json。", http_status=415)
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ApiError("INVALID_BODY", "请求体不完整。")

            def reject_constant(_value: str) -> None:
                raise ValueError("non-finite JSON")
            data = json.loads(raw, parse_constant=reject_constant)
            validate_request(data, operation)
            mode = "production" if operation == "check" else data["mode"]
            payload = envelope(mode, "injected_check" if operation == "check" else "live_solver", self.server.config.revision)
            text_mode = mode == "text"
            if text_mode:
                # Missing key is a capability failure, never a mock fallback.
                if not model_configured():
                    raise ApiError("MODEL_NOT_CONFIGURED", "服务器尚未配置真实模型，未执行模型调用。", "extraction", 503)
                self._require_auth(text_mode=True)
            if not self.server.limiter.allow(self.client_address[0], text_mode):
                raise ApiError("RATE_LIMITED", "演示调用额度已达上限，请稍后重试。", "admission", 429)
            if not self.server.workers.acquire(blocking=False):
                raise ApiError("SERVER_BUSY", "服务器正在处理其他请求，请稍后重试。", "admission", 503)
            try:
                status, payload = run_isolated(self.server.config, operation, data, payload)
            finally:
                self.server.workers.release()
            self._send(status, payload)
        except ApiError as exc:
            self._send(*fail(payload, exc))
        except (ValueError, UnicodeError, RecursionError):
            self._send(*fail(payload, ApiError("INVALID_JSON", "请求不是有效 JSON。")))
        except (TimeoutError, socket.timeout):
            self._send(*fail(payload, ApiError("BODY_TIMEOUT", "读取请求体超时。", "input", 408)))
        except Exception:
            self._send(*fail(payload, ApiError("INTERNAL_ERROR", "服务未完成请求，请稍后重试。", "internal", 500)))


def main() -> None:
    server = Server(Config.from_env())
    print(f"NL2OPT API listening on {server.server_address[0]}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
