"""Optional, best-effort nonblocking localhost telemetry; independent of simulation dt."""

import json
import socket
from time import monotonic

from ._validation import ConfigurationError, keys, number


class TelemetryPublisher:
    def __init__(self, port=8766, publish_hz=10):
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ConfigurationError("telemetry.port must be an integer in [1,65535]")
        self.address = ("127.0.0.1", port)
        self.interval = 1 / number(publish_hz, "publish_hz", positive=True, maximum=100)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        self.last = float("-inf")
        self.sent = self.dropped = self.sequence = 0
        self.closed = False

    @classmethod
    def from_config(cls, config):
        keys(config, {"enabled", "port", "publish_hz"}, "telemetry")
        return cls(config.get("port", 8766), config.get("publish_hz", 10))

    def _send(self, value):
        if self.closed:
            return
        self.sequence += 1
        try:
            data = json.dumps(
                {"schema_version": 1, "sequence": self.sequence, **value}, allow_nan=False
            ).encode("utf-8")
            if len(data) > 60000:
                self.dropped += 1
                return
            self.socket.sendto(data, self.address)
            self.sent += 1
        except (OSError, ValueError, TypeError):
            self.dropped += 1

    def publish(self, row):
        now = monotonic()
        if now - self.last < self.interval or self.closed:
            return
        self.last = now
        self._send({"event": "sample", "energy": row})

    def event(self, name, **values):
        self._send({"event": name, **values})

    def close(self):
        if not self.closed:
            self.socket.close()
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
