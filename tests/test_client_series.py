# tests/test_client_series.py
# Le client enchaîne plusieurs parties sur une connexion (série) :
# nouvelle stratégie à chaque partie, random initialisé avec la graine.

import json
import random
import socket
import threading

from robby.client import run
from robby.strategy import Strategy
from tests.helpers import robot


def fake_server(listener, received):
    conn, _ = listener.accept()
    f = conn.makefile("rwb")

    def send(msg):
        f.write((json.dumps(msg) + "\n").encode())
        f.flush()

    def recv():
        return json.loads(f.readline())

    received.append(recv())  # register
    send({"type": "register_ack", "status": "ok", "team_id": 1})
    for game, (team_id, seed) in enumerate([(1, 7), (2, 7)], start=1):
        send({"type": "game_start", "team_id": team_id, "seed": seed,
              "game": game, "games": 2, "config": {}})
        send({"type": "game_state", "turn": 1, "phase": 1, "phase_turn": 1,
              "robots": [robot(team_id * 10 + 1, team_id, "R", 3, 7)],
              "element": {"x": 7, "y": 7, "carried_by_id": None}})
        received.append(recv())  # commandes
        send({"type": "game_over", "winner": team_id, "scores": {}})
    send({"type": "series_over", "games": 2, "ranking": []})
    conn.close()


class Recorder(Strategy):
    instances = []

    def __init__(self):
        Recorder.instances.append(self)
        self.team_id = None
        self.draw = None

    def on_game_start(self, team_id, config):
        self.team_id = team_id
        self.draw = random.random()

    def decide(self, state):
        return []


def test_client_plays_a_series_with_fresh_seeded_strategies():
    Recorder.instances = []
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    received = []
    server = threading.Thread(target=fake_server, args=(listener, received))
    server.start()

    run(Recorder, "127.0.0.1", listener.getsockname()[1], "Moi")  # doit se terminer
    server.join(5)
    listener.close()

    assert received[0]["placement"] == {"R": "avant", "D": "droite", "K": "gauche"}
    a, b = Recorder.instances
    assert a is not b                                # une instance par partie
    assert (a.team_id, b.team_id) == (1, 2)          # la place peut changer
    random.seed("7:1")
    assert a.draw == random.random()                 # graine "seed:team_id"
    assert received[1]["turn"] == 1 and received[1]["type"] == "commands"
