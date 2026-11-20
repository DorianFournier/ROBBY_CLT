# tests/test_game_state.py
# Côté client : commandes en angle, GameState et ses outils, bots.

import math
import random

import pytest

from bots import BOTS
from robby import move, shield, shoot
from robby.client import check_commands
from robby.geometry import angle_to, direction
from strategy.my_strategy import MyStrategy
from tests.helpers import make_state, robot

ALL_STRATEGIES = [*BOTS.values(), MyStrategy]


def test_command_factories():
    assert move(13, angle=90, speed=2500) == {
        "robot_id": 13, "action": "MOVE", "angle": 90.0, "speed": 2500.0}
    assert move(13, angle=-90, speed=0)["angle"] == 270.0
    assert shoot(13, angle=45) == {"robot_id": 13, "action": "SHOOT", "angle": 45.0}
    assert shield(12, angle=180) == {"robot_id": 12, "action": "SHIELD",
                                     "angle": 180.0}
    assert move(13, 90, 1000) == move(13, angle=90, speed=1000)
    with pytest.raises(ValueError):
        move(13, angle=90, speed=-1)           # vitesse négative
    with pytest.raises(TypeError):
        move(13, angle=90)                     # vitesse manquante
    with pytest.raises(ValueError):
        shoot(13, angle="nord")


def test_angles_are_a_compass():
    assert direction(90) == pytest.approx((1, 0))
    assert angle_to((0, 0), (0, -10)) == pytest.approx(0)
    assert angle_to((0, 0), (-10, 0)) == pytest.approx(270)


def test_move_towards_stops_on_target_and_respects_max_speed():
    state = make_state([robot(11, 1, "R", 1000, 7500),
                             robot(13, 1, "K", 1000, 1000)])
    r, k = state.get_robot(11), state.get_robot(13)
    cmd = state.move_towards(r, (1600, 7500))
    assert cmd["angle"] == pytest.approx(90) and cmd["speed"] == pytest.approx(600)
    cmd = state.move_towards(k, (1000, 14000))
    assert cmd["angle"] == pytest.approx(180) and cmd["speed"] == 3000
    assert state.move_towards(r, (1000, 7500)) is None
    cmd = state.move_towards(k, (1000, 4000), stop_at=2500)
    assert cmd["speed"] == pytest.approx(500)


def test_check_commands():
    state = make_state([robot(11, 1, "R", 1000, 7500),
                             robot(12, 1, "D", 1000, 9000),
                             robot(13, 1, "K", 2000, 2000)])
    ok = [move(11, angle=10, speed=1000), shield(12, angle=0),
          shoot(13, angle=90)]
    assert check_commands(state, ok) == []
    bad = [move(11, angle=10, speed=1501), {"robot_id": 12, "action": "SHIELD"},
           {"robot_id": 13, "action": "SHOOT"}]
    assert len(check_commands(state, bad)) == 3


def test_targets_shields_and_first_hit():
    state = make_state([
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
    state = make_state([robot(11, 1, "R", 1500, 7500),
                             robot(13, 1, "K", 7500, 7500)],
                            phase=2, zone=zone, turn=40)
    assert state.zone_escape(state.get_robot(11)) == pytest.approx((2300, 7500))
    assert not state.in_zone((3000, 3000))             # coin : la tempête est ronde
    assert state.in_zone((7500, 2000))
    assert state.zone_escape(state.get_robot(13)) is None


@pytest.mark.parametrize("strategy_class", ALL_STRATEGIES)
@pytest.mark.parametrize("phase", [1, 2])
def test_strategies_valid_on_random_states(strategy_class, phase):
    """Sur 150 situations au hasard : jamais d'erreur de règle visible."""
    rng = random.Random(1)
    bot = strategy_class()
    bot.on_game_start(1, {"teams": {"1": "A", "2": "B", "3": "C"}})
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
        state = make_state(robots, phase=phase, zone=zone, turn=turn)
        commands = bot.decide(state)
        assert check_commands(state, commands) == [], (turn, commands)
        bot.on_turn_result(turn, {"deaths": []})


def test_rusher_radar_goes_for_the_battery():
    bot = BOTS["bot2"]()
    bot.on_game_start(1, {})
    state = make_state([robot(11, 1, "R", 1500, 7500)])
    cmd = bot.decide(state)[0]
    assert cmd["angle"] == pytest.approx(90)        # vers la batterie


def test_moving_storm_center_is_followed_by_the_tools():
    zone = {"center": [7500, 7500], "radius": 6000,
            "forecast": [6000, 5500, 5000], "state": "shrink", "target": 3500,
            "target_center": [9500, 8000],
            "forecast_centers": [[7500, 7500], [7900, 7600], [8300, 7700]],
            "shrink_turn": 30, "end_turn": 36}
    state = make_state([robot(11, 1, "R", 2000, 7500)], phase=2, zone=zone)
    assert state.storm_center_at(2) == (8300, 7700)
    assert state.safe_center == (9500, 8000)
    assert state.in_zone((2000, 7500))                    # 5500 du centre actuel
    assert not state.in_zone((2000, 7500), lookahead=2)   # le cercle s'éloigne
    escape = state.zone_escape(state.get_robot(11))
    assert escape is not None and escape[0] > 2000


# ---------------------------------------------------------------- mouvement continu

def test_robots_know_their_heading_and_speed():
    state = make_state([robot(13, 1, "K", 2000, 5000, heading=90, speed=3000),
                             robot(11, 1, "R", 6000, 6000)])
    k, r = state.get_robot(13), state.get_robot(11)
    assert k.moving and (k.heading, k.speed) == (90, 3000)
    assert not r.moving
    assert state.predict(k) == pytest.approx((5000, 5000))
    assert state.predict(k, 2) == pytest.approx((8000, 5000))
    assert state.predict(r) == (6000, 6000)


def test_stop_command_and_move_towards_stops_on_arrival():
    from robby import stop
    assert stop(13) == {"robot_id": 13, "action": "MOVE", "angle": 0.0, "speed": 0.0}
    state = make_state([robot(11, 1, "R", 4000, 4000, heading=90, speed=500),
                             robot(12, 1, "R", 5000, 5000)])
    moving, still = state.get_robot(11), state.get_robot(12)
    assert state.move_towards(moving, (4000, 4000))["speed"] == 0   # arrivé : stop
    assert state.move_towards(still, (5000, 5000)) is None          # déjà arrêté
    assert state.stop(still) is None


def test_keep_safe_refuses_to_coast_into_the_storm():
    zone = storm(5000)
    state = make_state([robot(13, 1, "K", 7500, 3000, heading=0, speed=2000),
                             robot(23, 2, "R", 7500, 5000)], phase=2, zone=zone)
    k = state.get_robot(13)
    assert not state.safe_to_coast(k)
    command = state.keep_safe(k, state.shoot_at(k, state.get_robot(23)))
    assert command["action"] == "MOVE"                 # s'écarter d'abord
    k.heading = 180                                    # vers le centre : sans danger
    shot = state.shoot_at(k, state.get_robot(23))
    assert state.keep_safe(k, shot) == shot


def test_shielded_targets_and_shield_ready():
    state = make_state([robot(13, 1, "K", 4500, 7000),
                             robot(22, 2, "D", 7000, 7000, shield=270),
                             robot(21, 2, "R", 7400, 7000)])
    k, d = state.get_robot(13), state.get_robot(22)
    assert state.targets_in_range(k) == []
    assert {e.id for e in state.shielded_targets(k)} == {21, 22}
    assert d.shield_ready and d.shield_hp == 3
    broken = make_state([robot(12, 1, "D", 5000, 5000, shield=None)])
    d = broken.get_robot(12)
    d.shield_cooldown = 2
    assert not d.shield_ready
    errors = check_commands(broken, [shield(12, angle=0)])
    assert errors and "brisé" in errors[0]


def test_ties_are_broken_on_the_right_for_every_team():
    """Deux batteries à la même distance : chaque équipe prend celle de sa
    droite (vue de sa base, face au centre). Toutes les places font donc le
    même choix, et chaque petite batterie n'a qu'un seul prétendant."""
    from robby import GameState
    elements = [{"id": 0, "x": 7500, "y": 7500, "carried_by_id": None, "points": 1000},
                {"id": 1, "x": 4500, "y": 4500, "carried_by_id": None, "points": 500},
                {"id": 2, "x": 10500, "y": 4500, "carried_by_id": None, "points": 500},
                {"id": 3, "x": 10500, "y": 10500, "carried_by_id": None, "points": 500},
                {"id": 4, "x": 4500, "y": 10500, "carried_by_id": None, "points": 500}]
    bases = {"1": (500, 7500), "2": (14500, 7500), "3": (7500, 500), "4": (7500, 14500)}
    choix = {}
    for t, base in bases.items():
        st = GameState({"turn": 1, "phase": 1, "robots": [], "elements": elements},
                       int(t), {"bases": bases})
        choix[t] = st.nearest_battery(base).id
    # équipe 1 (à gauche, face à l'est) : sa droite est au sud
    assert choix == {"1": 4, "2": 2, "3": 1, "4": 3}
    assert len(set(choix.values())) == 4
