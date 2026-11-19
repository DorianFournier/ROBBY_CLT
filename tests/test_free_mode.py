# tests/test_free_mode.py
# Mode libre (V2) côté client : commandes en angle, FreeGameState, bots.

import math
import random

import pytest

from bots import BOTS
from bots.free_random import FreeRandomBot
from bots.free_rusher import FreeRusherBot
from bots.free_simulator import FreeSimulatorBot
from bots.free_tactician import FreeTacticianBot
from robby import FreeGameState, GameState, move, shield, shoot
from robby.client import check_commands, state_class
from robby.geometry import angle_to, direction
from strategy.my_free_strategy import MyFreeStrategy
from tests.helpers import make_free_state, robot

FREE_BOTS = [FreeRandomBot, FreeRusherBot, FreeTacticianBot, FreeSimulatorBot,
             MyFreeStrategy]


def test_free_command_factories():
    assert move(13, angle=90, speed=2500) == {
        "robot_id": 13, "action": "MOVE", "angle": 90.0, "speed": 2500.0}
    assert move(13, angle=-90, speed=0)["angle"] == 270.0
    assert shoot(13, angle=45) == {"robot_id": 13, "action": "SHOOT", "angle": 45.0}
    assert shield(12, angle=180) == {"robot_id": 12, "action": "SHIELD",
                                     "angle": 180.0}
    with pytest.raises(ValueError):
        move(13, "U", angle=90, speed=10)
    with pytest.raises(ValueError):
        move(13, angle=90)                     # vitesse manquante
    with pytest.raises(ValueError):
        shoot(13, angle="nord")


def test_angles_are_a_compass():
    assert direction(90) == pytest.approx((1, 0))
    assert angle_to((0, 0), (0, -10)) == pytest.approx(0)
    assert angle_to((0, 0), (-10, 0)) == pytest.approx(270)


def test_client_picks_the_state_class_from_the_server_mode():
    assert state_class({"mode": "libre"}) is FreeGameState
    assert state_class({}) is GameState
    assert GameState.mode == "grille" and FreeGameState.mode == "libre"


def test_move_towards_stops_on_target_and_respects_max_speed():
    state = make_free_state([robot(11, 1, "R", 1000, 7500),
                             robot(13, 1, "K", 1000, 1000)])
    r, k = state.get_robot(11), state.get_robot(13)
    cmd = state.move_towards(r, (1600, 7500))
    assert cmd["angle"] == pytest.approx(90) and cmd["speed"] == pytest.approx(600)
    cmd = state.move_towards(k, (1000, 14000))
    assert cmd["angle"] == pytest.approx(180) and cmd["speed"] == 5000
    assert state.move_towards(r, (1000, 7500)) is None
    cmd = state.move_towards(k, (1000, 4000), stop_at=2500)
    assert cmd["speed"] == pytest.approx(500)


def test_check_commands_in_free_mode():
    state = make_free_state([robot(11, 1, "R", 1000, 7500),
                             robot(12, 1, "D", 1000, 9000),
                             robot(13, 1, "K", 2000, 2000)])
    ok = [move(11, angle=10, speed=1000), shield(12, angle=0),
          shoot(13, angle=90)]
    assert check_commands(state, ok) == []
    bad = [move(11, angle=10, speed=1001), {"robot_id": 12, "action": "SHIELD"},
           shoot(13, 21)]
    assert len(check_commands(state, bad)) == 3


def test_targets_shields_and_first_hit():
    state = make_free_state([
        robot(13, 1, "K", 5000, 5000),
        robot(21, 2, "R", 7000, 5000),
        robot(31, 3, "R", 5000, 7000),
        robot(32, 3, "D", 5000, 6600, shield=0),    # bouclier vers le haut
    ])
    k = state.get_robot(13)
    assert [e.id for e in state.targets_in_range(k)] == [21]
    assert state.is_shot_blocked(k, state.get_robot(31))
    assert state.is_shot_blocked(k, state.get_robot(32))
    hit, blocked, _ = state.first_hit(k, 180)
    assert hit is None and blocked
    # en contournant le bouclier, le Radar 31 devient une cible
    spot = state.firing_spot(k, state.get_robot(31))
    assert spot is not None
    assert math.dist(spot, k.pos) <= 5000
    assert state.can_hit_from(k, spot, state.get_robot(31))


def storm(radius, later=None):
    forecast = [radius, radius] + [later or radius] * 4
    return {"center": [7500, 7500], "radius": radius, "forecast": forecast,
            "state": "pause", "target": later, "shrink_turn": None, "end_turn": None}


def test_zone_escape_in_units():
    zone = storm(5500)
    state = make_free_state([robot(11, 1, "R", 1500, 7500),
                             robot(13, 1, "K", 7500, 7500)],
                            phase=2, zone=zone, turn=40)
    assert state.zone_escape(state.get_robot(11)) == pytest.approx((2300, 7500))
    assert not state.in_zone((3000, 3000))             # coin : la tempête est ronde
    assert state.in_zone((7500, 2000))
    assert state.zone_escape(state.get_robot(13)) is None


def test_grid_tools_explain_themselves_in_free_mode():
    state = make_free_state([robot(11, 1, "R", 1000, 7500)])
    with pytest.raises(NotImplementedError, match="mode libre"):
        state.path_towards(state.get_robot(11), (5, 5))


@pytest.mark.parametrize("strategy_class", FREE_BOTS)
@pytest.mark.parametrize("phase", [1, 2])
def test_free_strategies_valid_on_random_states(strategy_class, phase):
    rng = random.Random(1)
    bot = strategy_class()
    bot.on_game_start(1, {"mode": "libre", "teams": {"1": "A", "2": "B", "3": "C"}})
    for turn in range(150):
        def p():
            return rng.uniform(300, 14700), rng.uniform(300, 14700)
        robots = [robot(11, 1, "R", *p(), carrying=rng.random() < 0.2),
                  robot(12, 1, "D", *p(), shield=rng.choice([None, 0, 200])),
                  robot(13, 1, "K", *p()),
                  robot(21, 2, "R", *p()),
                  robot(22, 2, "D", *p(), shield=rng.choice([None, 90])),
                  robot(33, 3, "K", *p())]
        robots = [r for r in robots if rng.random() < 0.9]
        zone = None
        if phase == 2:
            r = rng.uniform(1500, 10600)
            zone = storm(r, max(1500, r - 1000))
        state = make_free_state(robots, phase=phase, zone=zone, turn=turn)
        commands = bot.decide(state)
        assert check_commands(state, commands) == [], (turn, commands)
        bot.on_turn_result(turn, {"deaths": []})


def test_bot_shortcuts_play_both_modes():
    bot = BOTS["bot2"]()
    bot.on_game_start(1, {"mode": "libre"})
    assert isinstance(bot.delegate, FreeRusherBot)
    state = make_free_state([robot(11, 1, "R", 1500, 7500)])
    cmd = bot.decide(state)[0]
    assert cmd["angle"] == pytest.approx(90)        # vers la batterie


def test_moving_storm_center_is_followed_by_the_tools():
    zone = {"center": [7500, 7500], "radius": 6000,
            "forecast": [6000, 5500, 5000], "state": "shrink", "target": 3500,
            "target_center": [9500, 8000],
            "forecast_centers": [[7500, 7500], [7900, 7600], [8300, 7700]],
            "shrink_turn": 30, "end_turn": 36}
    state = make_free_state([robot(11, 1, "R", 2000, 7500)], phase=2, zone=zone)
    assert state.storm_center_at(2) == (8300, 7700)
    assert state.safe_center == (9500, 8000)
    assert state.in_zone((2000, 7500))                    # 5500 du centre actuel
    assert not state.in_zone((2000, 7500), lookahead=2)   # le cercle s'éloigne
    escape = state.zone_escape(state.get_robot(11))
    assert escape is not None and escape[0] > 2000
