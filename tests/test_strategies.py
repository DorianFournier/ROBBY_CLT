import pytest

from robby.client import check_commands
from strategy.my_strategy import MyStrategy
from strategy.random_strategy import RandomStrategy
from tests.helpers import make_state, robot


@pytest.mark.parametrize("strategy_class", [MyStrategy, RandomStrategy])
def test_strategies_return_valid_commands(strategy_class):
    state = make_state([
        robot(11, 1, "R", 1, 7), robot(12, 1, "D", 0, 8), robot(13, 1, "K", 0, 6),
        robot(21, 2, "R", 3, 6),
    ])
    commands = strategy_class().decide(state)
    assert check_commands(state, commands) == []


def test_example_radar_brings_element_home():
    state = make_state([robot(11, 1, "R", 3, 7, carrying=True)], carried_by=11,
                       element=(3, 7))
    assert MyStrategy().decide(state) == [
        {"robot_id": 11, "action": "MOVE", "path": ["L"]}
    ]


def test_penalised_robot_gets_no_command():
    state = make_state([robot(11, 1, "R", 1, 7, penalty=2)])
    assert MyStrategy().decide(state) == []
