from __future__ import annotations

import math
import statistics
from .schemas import TurnState, RobotState

ROBOT_TYPES = ("R", "K", "D")


def _distance(a_x: int, a_y: int, b_x: int, b_y: int) -> float:
    return math.dist((a_x, a_y), (b_x, b_y))


def _robot_type_index(robot: RobotState) -> int:
    try:
        return ROBOT_TYPES.index(robot.type)
    except ValueError:
        return -1


def build_features(state: TurnState, team_id: int, robot_id: int) -> list[float]:
    robot = next(r for r in state.robots if r.id == robot_id)
    allies = [r for r in state.robots if r.team == team_id and r.alive]
    enemies = [r for r in state.robots if r.team != team_id and r.alive]

    distances_to_enemies = [_distance(robot.x, robot.y, e.x, e.y) for e in enemies]
    min_enemy_distance = min(distances_to_enemies) if distances_to_enemies else 999.0
    mean_enemy_distance = statistics.fmean(distances_to_enemies) if distances_to_enemies else 999.0

    features = [
        float(state.turn),
        float(state.penalty_remaining),
        float(robot.x),
        float(robot.y),
        float(_robot_type_index(robot)),
        float(int(robot.carrying_element)),
        float(len(allies)),
        float(len(enemies)),
        float(min_enemy_distance),
        float(mean_enemy_distance),
        float(_distance(robot.x, robot.y, state.element.x, state.element.y)),
    ]
    return features


def action_to_label(action: str, direction: str | None = None) -> str:
    if action == "MOVE" and direction:
        return f"MOVE:{direction}"
    return action
