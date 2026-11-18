# robby/protocol.py
# Messages JSON délimités par des retours à la ligne ("\n").

import json
import socket

ENCODING = "utf-8"


class Connection:
    """Connexion TCP au serveur, qui échange des messages JSON (un par ligne)."""

    def __init__(self, host: str, port: int, timeout: float | None = None):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(None)
        self._buffer = b""

    def send(self, data: dict) -> None:
        self.sock.sendall((json.dumps(data) + "\n").encode(ENCODING))

    def receive(self) -> dict | None:
        """Lit UN message. Retourne None si le serveur a fermé la connexion."""
        while b"\n" not in self._buffer:
            data = self.sock.recv(4096)
            if not data:
                return None
            self._buffer += data
        line, _, self._buffer = self._buffer.partition(b"\n")
        return json.loads(line.decode(ENCODING))

    def close(self) -> None:
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
