# tests/test_strategies.py
# Chargement des stratégies, squelette de l'étudiant.

import pytest

from bots import BOTS
from main import load_strategy
from robby.client import check_commands
from strategy.my_strategy import MyStrategy
from tests.helpers import make_state, robot


@pytest.mark.parametrize("strategy_class", [MyStrategy, *BOTS.values()])
def test_strategies_return_valid_commands(strategy_class):
    state = make_state([
        robot(11, 1, "R", 1500, 7500), robot(12, 1, "D", 500, 8500),
        robot(13, 1, "K", 500, 6500), robot(21, 2, "R", 3500, 6500),
    ])
    bot = strategy_class()
    bot.on_game_start(1, {})
    assert check_commands(state, bot.decide(state)) == []


def test_load_strategy_shortcuts():
    assert type(load_strategy("bot1")).__name__ == "RandomBot"
    assert type(load_strategy("bot3")).__name__ == "TacticianBot"
    assert type(load_strategy("bot4")).__name__ == "SimulatorBot"
    assert isinstance(load_strategy("strategy.my_strategy:MyStrategy"), MyStrategy)


def test_example_collector_brings_battery_home():
    state = make_state([robot(14, 1, "C", 1500, 7500, carrying=True)],
                       carried_by=14, element=(1500, 7500))
    [cmd] = MyStrategy().decide(state)
    assert cmd["action"] == "MOVE" and cmd["angle"] == pytest.approx(270)
    assert cmd["speed"] == pytest.approx(1000)         # base à 1000 : pile dessus


def test_example_collector_stops_when_nothing_to_do():
    state = make_state([robot(14, 1, "C", 6000, 6000, heading=90, speed=800)],
                       phase=2)
    assert MyStrategy().decide(state) == [
        {"robot_id": 14, "action": "MOVE", "angle": 90.0, "speed": 0.0}]


def test_penalised_robot_gets_no_command():
    state = make_state([robot(11, 1, "R", 1500, 7500, penalty=2)])
    assert MyStrategy().decide(state) == []
