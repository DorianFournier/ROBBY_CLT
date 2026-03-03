# protocol.py

import json

def send_json(sock, data: dict):
    message = json.dumps(data) + "\n"
    sock.sendall(message.encode("utf-8"))


def receive_json(sock):
    buffer = ""
    while "\n" not in buffer:
        data = sock.recv(4096)
        if not data:
            return None
        buffer += data.decode("utf-8")

    line, _, _ = buffer.partition("\n")
    return json.loads(line)
