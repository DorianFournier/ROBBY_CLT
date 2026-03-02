import json
import socket

HEADER_SIZE = 4

def send_json(sock: socket.socket, data: dict):
    payload = json.dumps(data).encode("utf-8")
    length = len(payload).to_bytes(HEADER_SIZE, byteorder="big")
    sock.sendall(length + payload)

def receive_json(sock: socket.socket) -> dict | None:
    try:
        raw_length = _recv_exactly(sock, HEADER_SIZE)
        if not raw_length:
            return None
        length = int.from_bytes(raw_length, byteorder="big")
        raw_data = _recv_exactly(sock, length)
        if not raw_data:
            return None
        return json.loads(raw_data.decode("utf-8"))
    except (ConnectionResetError, OSError):
        return None

def _recv_exactly(sock: socket.socket, n: int) -> bytes | None:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data