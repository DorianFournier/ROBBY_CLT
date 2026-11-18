# robby/protocol.py
# Messages JSON délimités par des retours à la ligne ("\n").

import json
import select
import socket

ENCODING = "utf-8"


class Connection:
    """Connexion TCP au serveur, qui échange des messages JSON (un par ligne)."""

    def __init__(self, host: str, port: int, timeout: float | None = None):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        # Petits messages à chaque tour : pas d'algorithme de Nagle
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
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

    def has_pending(self) -> bool:
        """True si un autre message complet est déjà arrivé (sans bloquer)."""
        while b"\n" not in self._buffer:
            readable, _, _ = select.select([self.sock], [], [], 0)
            if not readable:
                return False
            data = self.sock.recv(4096)
            if not data:
                return True  # connexion fermée : receive() renverra None
            self._buffer += data
        return True

    def close(self) -> None:
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
