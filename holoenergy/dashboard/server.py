"""Local read-only HTTP dashboard and UDP receiver, using only Python's standard library."""

import argparse
import json
import socket
import threading
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from time import monotonic


def compare_reports(directory):
    """Side-by-side rows of saved EnergyReport JSON files (read-only, for 'Compare runs')."""
    if directory is None or not Path(directory).is_dir():
        return {"directory": None if directory is None else str(directory), "runs": []}
    runs = []
    for path in sorted(Path(directory).glob("*.json"))[:50]:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(report, dict) or "terminal_energy_Wh" not in report:
            continue
        evidence = report.get("evidence") or {}
        runs.append(
            {
                "file": path.name,
                "run_id": report.get("run_id"),
                "duration_s": report.get("duration_s"),
                "terminal_energy_Wh": report.get("terminal_energy_Wh"),
                "soc_loss": report.get("soc_loss"),
                "peak_current_A": report.get("peak_current_A"),
                "minimum_voltage_V": report.get("minimum_voltage_V"),
                "category_energy_Wh": report.get("category_energy_Wh"),
                "evidence_share_percent": evidence.get("share_percent"),
                "upper_bound_share_percent": evidence.get("upper_bound_share_percent"),
            }
        )
    return {"directory": str(directory), "runs": runs}


class DashboardStore:
    @staticmethod
    def _plot_row(row):
        return {
            key: row.get(key)
            for key in (
                "time_s",
                "soc",
                "voltage_V",
                "current_A",
                "power_total_W",
                "battery_temperature_C",
                "power_propulsion_W",
                "power_payload_W",
                "actuator_power_W",
                "power_communications_W",
            )
        }

    def __init__(self, history_s=120, max_samples=2400, stale_after_s=3):
        if history_s <= 0 or max_samples <= 0 or stale_after_s <= 0:
            raise ValueError(
                "Dashboard history, maximum samples and stale timeout must be positive"
            )
        self.history_s = history_s
        self.stale_after = stale_after_s
        self.history = deque(maxlen=max_samples)
        self.latest = None
        self.last_received = None
        self.status = "waiting"
        self.summary = None
        self.evidence = None
        self.warnings = []
        self.lock = threading.Lock()

    def accept(self, message):
        if not isinstance(message, dict) or message.get("schema_version") != 1:
            return
        event = message.get("event")
        with self.lock:
            if event == "sample" and isinstance(message.get("energy"), dict):
                row = message["energy"]
                time = row.get("time_s")
                if not isinstance(time, (int, float)) or isinstance(time, bool):
                    return
                if self.latest and (row.get("run_id"), row.get("episode")) != (
                    self.latest.get("run_id"),
                    self.latest.get("episode"),
                ):
                    self.history.clear()
                self.latest = row
                if isinstance(message.get("evidence"), dict):
                    self.evidence = message["evidence"]
                if isinstance(message.get("warnings"), list):
                    self.warnings = [str(w) for w in message["warnings"]]
                self.history.append(self._plot_row(row))
                while self.history and self.history[0]["time_s"] < time - self.history_s:
                    self.history.popleft()
                self.status = "live"
                self.summary = None
            elif event == "reset":
                self.history.clear()
                self.latest = None
                self.summary = None
                self.status = "reset"
            elif event == "end_mission":
                if isinstance(message.get("energy"), dict):
                    self.latest = message["energy"]
                    if not self.history or self.history[-1].get("time_s") != self.latest.get(
                        "time_s"
                    ):
                        self.history.append(self._plot_row(self.latest))
                self.summary = message.get("summary")
                if isinstance(self.summary, dict) and isinstance(
                    self.summary.get("evidence"), dict
                ):
                    self.evidence = self.summary["evidence"]
                self.status = "ended"
            else:
                return
            self.last_received = monotonic()

    def snapshot(self):
        with self.lock:
            age = None if self.last_received is None else monotonic() - self.last_received
            status = (
                "disconnected" if self.status == "live" and age > self.stale_after else self.status
            )
            return {
                "status": status,
                "age_s": age,
                "latest": self.latest,
                "history": list(self.history),
                "summary": self.summary,
                "evidence": self.evidence,
                "warnings": list(self.warnings),
                "history_s": self.history_s,
            }


class DashboardServer:
    def __init__(self, http_port=8765, telemetry_port=8766, *, history_s=120, reports_dir=None):
        self.store = DashboardStore(history_s)
        self.reports_dir = None if reports_dir is None else Path(reports_dir)
        reports_dir_ = self.reports_dir
        self.stop = threading.Event()
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.http = None
        self.threads = []
        try:
            self.udp.bind(("127.0.0.1", telemetry_port))
            self.udp.settimeout(0.2)
            store = self.store
            html = files("holoenergy.dashboard").joinpath("index.html").read_bytes()

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path in ("/", "/index.html"):
                        content, kind = html, "text/html; charset=utf-8"
                    elif self.path == "/api/state":
                        content, kind = (
                            json.dumps(store.snapshot(), allow_nan=False).encode(),
                            "application/json",
                        )
                    elif self.path == "/api/reports":
                        content, kind = (
                            json.dumps(compare_reports(reports_dir_), default=str).encode(),
                            "application/json",
                        )
                    else:
                        self.send_error(404)
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", kind)
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    try:
                        self.wfile.write(content)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

                def log_message(self, *args):
                    pass

            self.http = ThreadingHTTPServer(("127.0.0.1", http_port), Handler)
            self.http.daemon_threads = True
        except Exception:
            self.udp.close()
            if self.http:
                self.http.server_close()
            raise

    @property
    def url(self):
        return f"http://127.0.0.1:{self.http.server_address[1]}/"

    @property
    def telemetry_port(self):
        return self.udp.getsockname()[1]

    def _receive(self):
        while not self.stop.is_set():
            try:
                data, _ = self.udp.recvfrom(65535)
                self.store.accept(json.loads(data))
            except (socket.timeout, ValueError, UnicodeError):
                continue
            except OSError:
                break

    def start(self):
        if self.threads:
            return self
        for target in (self._receive, self.http.serve_forever):
            thread = threading.Thread(target=target, daemon=True)
            self.threads.append(thread)
            thread.start()
        return self

    def close(self):
        self.stop.set()
        if self.threads:
            self.http.shutdown()
        self.http.server_close()
        self.udp.close()
        for thread in self.threads:
            thread.join(timeout=2)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--telemetry-port", type=int, default=8766)
    parser.add_argument("--history-seconds", type=float, default=120)
    parser.add_argument(
        "--reports", type=Path, help="Directory of EnergyReport JSON files for 'Compare runs'"
    )
    parser.add_argument(
        "--open", action="store_true", help="Open the local dashboard in your browser"
    )
    args = parser.parse_args()
    with DashboardServer(
        args.port, args.telemetry_port, history_s=args.history_seconds, reports_dir=args.reports
    ) as server:
        print(
            f"HoloEnergy dashboard: {server.url}; telemetry UDP {server.telemetry_port}", flush=True
        )
        if args.open:
            webbrowser.open(server.url)
        try:
            while not server.stop.wait(0.5):
                pass
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
