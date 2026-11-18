# tests/test_zone.py
# Zone qui rétrécit (phase 2) côté client : outils de GameState et bots.

import pytest

from bots import BOTS
from robby.game_state import GameState, step
from tests.helpers import robot


def state_with_zone(robots, margin, next_margin=None, next_turn=None, turn=50):
    msg = {"type": "game_state", "turn": turn, "phase": 2, "phase_turn": 30,
           "robots": robots, "element": {"x": 0, "y": 7, "carried_by_id": None},
           "zone": {"margin": margin, "next_margin": next_margin,
                    "next_turn": next_turn,
                    "safe": [margin, margin, 14 - margin, 14 - margin]}}
    return GameState(msg, 1, {"map_width": 15, "map_height": 15})


def test_in_zone_now_and_soon():
    state = state_with_zone([], margin=2, next_margin=3, next_turn=52)
    assert state.in_zone((2, 7)) and not state.in_zone((1, 7))
    assert state.in_zone((2, 7), lookahead=1)          # tour 51 : encore marge 2
    assert not state.in_zone((2, 7), lookahead=2)      # tour 52 : marge 3


def test_without_zone_info_everything_is_safe():
    msg = {"turn": 1, "phase": 1, "robots": [],
           "element": {"x": 7, "y": 7, "carried_by_id": None}}
    state = GameState(msg, 1, {})
    assert state.in_zone((0, 0)) and state.zone_margin() == 0


def test_escape_path_brings_robot_back_inside():
    state = state_with_zone([robot(13, 1, "K", 0, 7)], margin=2)
    k = state.get_robot(13)
    path = state.zone_escape_path(k)
    dest = k.pos
    for d in path:
        dest = step(dest, d)
    assert state.in_zone(dest)
    assert state.zone_escape_path(state_with_zone(
        [robot(13, 1, "K", 7, 7)], margin=2).get_robot(13)) == []


@pytest.mark.parametrize("name", BOTS)
def test_bots_leave_the_deadly_zone(name):
    # Tous les robots sur le bord mortel (marge 1) : chaque bot doit les
    # faire rentrer (aucun ne reste immobile hors zone).
    robots = [robot(11, 1, "R", 0, 7), robot(12, 1, "D", 0, 5),
              robot(13, 1, "K", 0, 9)]
    state = state_with_zone(robots, margin=1)
    bot = BOTS[name]()
    commands = {c["robot_id"]: c for c in bot.decide(state)}
    for r in state.my_robots:
        cmd = commands.get(r.id)
        assert cmd and cmd["action"] == "MOVE", (name, r)
        dest = r.pos
        for d in cmd["path"]:
            dest = step(dest, d)
        assert state.in_zone(dest), (name, r, dest)


def test_escape_skips_full_cells_and_cells_taken_by_allies():
    # Radar sur le bord mortel (1, 7) ; la case la plus proche (2, 7) est
    # pleine (2 robots) : il doit viser une autre case libre.
    robots = [robot(11, 1, "R", 1, 7), robot(12, 1, "D", 2, 7),
              robot(13, 1, "K", 2, 7)]
    state = state_with_zone(robots, margin=2)
    radar = state.get_robot(11)
    path = state.zone_escape_path(radar)
    assert path and state.in_zone(state.destination(radar, path))
    assert state.destination(radar, path) != (2, 7)
    # même chose si la case est seulement réservée par un allié
    state2 = state_with_zone([robot(11, 1, "R", 1, 7)], margin=2)
    radar2 = state2.get_robot(11)
    taken = {(2, 7)}
    dest = state2.destination(radar2, state2.zone_escape_path(radar2, taken=taken))
    assert dest not in taken and state2.in_zone(dest)


def test_trim_to_free_avoids_allied_destinations():
    state = state_with_zone([robot(13, 1, "K", 5, 5)], margin=0)
    k = state.get_robot(13)
    assert state.destination(k, ["R", "R"]) == (7, 5)
    assert state.trim_to_free(k, ["R", "R"], {(7, 5)}) == ["R"]


def test_rusher_never_sends_two_robots_to_the_same_cell():
    # D et K côte à côte sur le bord mortel : avant, ils visaient la même
    # case de repli et, d'après les règles, aucun des deux ne bougeait.
    robots = [robot(11, 1, "R", 7, 7), robot(12, 1, "D", 0, 7),
              robot(13, 1, "K", 0, 6)]
    state = state_with_zone(robots, margin=1)
    commands = BOTS["bot2"]().decide(state)
    dests = [state.destination(state.get_robot(c["robot_id"]), c["path"])
             for c in commands if c["action"] == "MOVE"]
    assert len(dests) == len(set(dests))
    assert all(state.in_zone(d) for d in dests)
