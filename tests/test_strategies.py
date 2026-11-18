import random

import pytest

from bots import BOTS
from main import load_strategy
from robby.client import check_commands
from strategy.my_strategy import MyStrategy
from tests.helpers import make_state, robot

ALL = [MyStrategy, *BOTS.values()]


@pytest.mark.parametrize("strategy_class", ALL)
def test_strategies_return_valid_commands(strategy_class):
    state = make_state([
        robot(11, 1, "R", 1, 7), robot(12, 1, "D", 0, 8), robot(13, 1, "K", 0, 6),
        robot(21, 2, "R", 3, 6),
    ])
    commands = strategy_class().decide(state)
    assert check_commands(state, commands) == []


@pytest.mark.parametrize("strategy_class", ALL)
@pytest.mark.parametrize("phase", [1, 2])
def test_strategies_valid_on_random_states(strategy_class, phase):
    """Sur 200 situations au hasard : jamais d'erreur de règle visible."""
    rng = random.Random(0)
    bot = strategy_class()
    for turn in range(200):
        cells = rng.sample([(x, y) for x in range(15) for y in range(15)], 8)
        robots = [robot(11, 1, "R", *cells[0], carrying=rng.random() < 0.2),
                  robot(12, 1, "D", *cells[1], shield=rng.choice([None, "SU", "SL"])),
                  robot(13, 1, "K", *cells[2])]
        if phase == 2 and rng.random() < 0.5:
            robots.append(robot(14, 1, "K", *cells[3]))
        robots += [robot(21, 2, "R", *cells[4]),
                   robot(22, 2, "D", *cells[5], shield=rng.choice([None, "SR"])),
                   robot(33, 3, "K", *cells[6])]
        robots = [r for r in robots if rng.random() < 0.9]
        state = make_state(robots, phase=phase)
        state.turn = turn
        commands = bot.decide(state)
        assert check_commands(state, commands) == [], (turn, commands)
        for cmd in commands:
            if cmd["action"] == "MOVE":
                assert state.can_follow(state.get_robot(cmd["robot_id"]), cmd["path"])
            if cmd["action"] == "SHOOT":
                shooter = state.get_robot(cmd["robot_id"])
                target = state.get_robot(cmd["target_id"])
                assert target in state.targets_in_range(shooter)
        bot.on_turn_result(turn, {"deaths": []})


def test_load_strategy_shortcuts():
    assert type(load_strategy("bot1").delegate).__name__ == "RandomBot"
    bot3 = load_strategy("bot3")
    assert type(bot3.delegate).__name__ == "TacticianBot"
    bot3.on_game_start(1, {"mode": "libre"})
    assert type(bot3.delegate).__name__ == "FreeTacticianBot"
    assert isinstance(load_strategy("strategy.my_strategy:MyStrategy"), MyStrategy)


def test_example_radar_brings_element_home():
    state = make_state([robot(11, 1, "R", 3, 7, carrying=True)], carried_by=11,
                       element=(3, 7))
    assert MyStrategy().decide(state) == [
        {"robot_id": 11, "action": "MOVE", "path": ["L"]}
    ]


def test_penalised_robot_gets_no_command():
    state = make_state([robot(11, 1, "R", 1, 7, penalty=2)])
    assert MyStrategy().decide(state) == []


def test_tactician_defender_steps_between_radar_and_threat():
    from bots.level3_tactician import TacticianBot
    # Radar en (5, 7) qui avance vers l'élément (7, 7) ; K ennemi visible en
    # (9, 7). Le D se place juste devant la nouvelle position du Radar, côté
    # menace (sur la ligne de tir).
    state = make_state([
        robot(11, 1, "R", 5, 7), robot(12, 1, "D", 6, 7), robot(13, 1, "K", 4, 4),
        robot(23, 2, "K", 9, 7),
    ])
    commands = {c["robot_id"]: c for c in TacticianBot().decide(state)}
    assert commands[11]["path"] == ["R"]        # Radar -> (6, 7)
    assert commands[12]["path"] == ["R"]        # D     -> (7, 7), entre R et K


def test_tactician_guard_cell_is_one_step_towards_threat():
    from bots.level3_tactician import TacticianBot
    state = make_state([])
    bot = TacticianBot()
    assert bot.guard_cell(state, (6, 7), (7, 2)) == (6, 6)    # menace en haut
    assert bot.guard_cell(state, (6, 7), (12, 8)) == (7, 7)   # menace à droite


def test_tactician_defender_turns_shield_towards_threat_when_in_place():
    from bots.level3_tactician import TacticianBot
    # Radar immobile (il attend : ennemi à 4 cases en phase 2), D déjà
    # en place côté menace mais bouclier mal orienté -> il le tourne.
    state = make_state([
        robot(11, 1, "R", 7, 7), robot(12, 1, "D", 7, 6, shield="SL"),
        robot(23, 2, "K", 7, 3),
    ], phase=2)
    commands = {c["robot_id"]: c for c in TacticianBot().decide(state)}
    assert 11 not in commands
    assert commands[12] == {"robot_id": 12, "action": "SHIELD", "direction": "SU"}


def test_tactician_unguarded_radar_retreats_from_enemy_destructor():
    from bots.level3_tactician import TacticianBot
    state = make_state([
        robot(11, 1, "R", 3, 7), robot(12, 1, "D", 0, 0), robot(23, 2, "K", 6, 7),
    ])
    commands = {c["robot_id"]: c for c in TacticianBot().decide(state)}
    radar = state.get_robot(11)
    from robby.game_state import step
    new_pos = step(radar.pos, commands[11]["path"][0])
    assert new_pos[0] < radar.x                  # il s'éloigne du K ennemi
