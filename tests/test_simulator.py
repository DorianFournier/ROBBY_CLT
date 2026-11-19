# tests/test_simulator.py
# Simulateur d'un tour (mode libre) et bot4 qui s'en sert.

import pytest

from bots.free_simulator import FreeSimulatorBot
from robby import move, shoot
from robby.simulator import SimRobot, TurnSimulator
from tests.helpers import make_free_state, robot


def run(robots, commands, **state_options):
    state = make_free_state(robots, **state_options)
    return TurnSimulator(state).run(commands)


def test_move_goes_speed_units_and_slides_along_borders():
    res = run([robot(13, 1, "K", 5000, 5000), robot(23, 2, "K", 1000, 1000)],
              {1: [move(13, angle=90, speed=4000)],
               2: [move(23, angle=45, speed=5000)]})
    assert res.robot(13).pos == pytest.approx((9000, 5000))
    assert res.robot(23).y == pytest.approx(300)      # bloqué en haut...
    assert res.robot(23).x > 4000                      # ...mais glisse


def test_enemies_block_allies_pass_through():
    res = run([robot(13, 1, "K", 5000, 5000), robot(11, 1, "R", 7000, 5000),
               robot(21, 2, "R", 5000, 9000), robot(23, 2, "K", 7000, 9000)],
              {1: [move(13, angle=90, speed=5000)],
               2: [move(21, angle=90, speed=1000)]})
    assert res.robot(13).x == pytest.approx(10000)     # traverse son Radar
    assert res.robot(21).x <= 7000 - 600 + 1           # arrêté devant le K


def test_shots_first_enemy_and_shields():
    robots = [robot(13, 1, "K", 5000, 5000), robot(21, 2, "R", 7000, 5000),
              robot(22, 2, "D", 5000, 6600, shield=0), robot(31, 3, "R", 5000, 7000)]
    res = run(robots, {1: [shoot(13, angle=90)]})
    assert res.deaths == [21] and res.killers == {21: 1}
    res = run(robots, {1: [shoot(13, angle=180)]})
    assert res.deaths == [] and res.shots == [(13, None, True)]   # bouclier


def test_battery_pickup_and_capture():
    res = run([robot(11, 1, "R", 6800, 7500)], {1: [move(11, angle=90, speed=1000)]})
    assert res.carrier == 11 and res.robot(11).carrying_element
    res = run([robot(11, 1, "R", 1500, 7500, carrying=True)],
              {1: [move(11, angle=270, speed=600)]}, carried_by=11)
    assert res.captured_by == 1


def test_zone_kills_and_invalid_commands_are_ignored():
    zone = {"center": [7500, 7500], "radius": 6500, "forecast": [6500],
            "state": "pause", "target": 5000, "shrink_turn": 99, "end_turn": 105}
    res = run([robot(11, 1, "R", 700, 7500), robot(13, 1, "K", 5000, 5000)],
              {1: [move(13, angle=0, speed=99999), {"robot_id": 11}]},
              phase=2, zone=zone)
    assert res.zone_deaths == [11]
    assert res.robot(13).pos == (5000, 5000)           # vitesse trop grande


def test_extra_robots_are_simulated_as_ghosts():
    state = make_free_state([robot(13, 1, "K", 5000, 5000)])
    ghost = SimRobot(21, 2, "R", 7000, 5000, ghost=True)
    res = TurnSimulator(state, extra=[ghost]).run({1: [shoot(13, angle=90)]})
    assert res.deaths == [21]


# ---------------------------------------------------------------- bot4

def play(state, bot=None):
    bot = bot or FreeSimulatorBot()
    bot.on_game_start(1, {"mode": "libre", "teams": {"1": "A", "2": "B"}})
    return {c["robot_id"]: c for c in bot.decide(state)}


def test_bot4_picks_up_the_battery():
    commands = play(make_free_state([robot(11, 1, "R", 6600, 7500),
                                     robot(12, 1, "D", 5000, 7000),
                                     robot(13, 1, "K", 5000, 8000)]))
    assert commands[11]["action"] == "MOVE"
    assert commands[11]["angle"] == pytest.approx(90, abs=30)


def test_bot4_shoots_an_exposed_enemy_radar():
    commands = play(make_free_state([robot(11, 1, "R", 4000, 7500),
                                     robot(12, 1, "D", 4000, 6500),
                                     robot(13, 1, "K", 5000, 8000),
                                     robot(21, 2, "R", 7000, 8000)]))
    assert commands[13]["action"] == "SHOOT"
    assert commands[13]["angle"] == pytest.approx(90, abs=1)


def test_bot4_is_deterministic_and_fast():
    import time
    robots = [robot(11, 1, "R", 4000, 7500), robot(12, 1, "D", 4500, 7000),
              robot(13, 1, "K", 5000, 8000), robot(21, 2, "R", 9000, 7500),
              robot(22, 2, "D", 8500, 7500, shield=270), robot(23, 2, "K", 9000, 6500)]
    started = time.perf_counter()
    a = play(make_free_state(robots))
    assert time.perf_counter() - started < 1.0          # délai serveur : 3 s
    assert a == play(make_free_state(robots))


def test_simulated_robots_keep_moving_and_stop_when_blocked():
    from robby.simulator import TurnSimulator
    state = make_free_state([robot(13, 1, "K", 2000, 5000, heading=90, speed=2000),
                             robot(23, 2, "K", 9000, 5000, heading=270, speed=1000),
                             robot(11, 1, "R", 2000, 9000, heading=90, speed=1000)])
    res = TurnSimulator(state).run({1: [shoot(13, angle=0)]})     # tire en roulant
    assert res.robot(13).pos == pytest.approx((4000, 5000))
    assert res.robot(23).pos == pytest.approx((8000, 5000))       # ennemi sur sa lancée
    res = TurnSimulator(state).run({1: [move(11, angle=0, speed=0)]})
    assert res.robot(11).pos == (2000, 9000) and res.robot(11).speed == 0
    blocked = make_free_state([robot(13, 1, "K", 2000, 5000, heading=90, speed=5000),
                               robot(21, 2, "R", 4000, 5000)])
    res = TurnSimulator(blocked).run({})
    assert res.robot(13).speed == 0 and res.robot(13).x < 4000 - 600 + 1
