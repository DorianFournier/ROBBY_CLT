from __future__ import annotations

from typing import Any

from .features import build_features
from .schemas import TurnState

DIRECTIONS = {"U", "UR", "R", "DR", "D", "DL", "L", "UL"}


def _prediction_to_command(robot_id: int, prediction: str) -> dict[str, Any]:
    if prediction.startswith("MOVE:"):
        direction = prediction.split(":", maxsplit=1)[1]
        if direction in DIRECTIONS:
            return {"robot_id": robot_id, "action": "MOVE", "direction": direction}
    if prediction == "SHOOT":
        return {"robot_id": robot_id, "action": "SHOOT", "target_id": -1}
    if prediction == "SHIELD":
        return {"robot_id": robot_id, "action": "SHIELD", "direction": "SU"}
    return {"robot_id": robot_id, "action": "MOVE", "direction": "U"}


def decide_with_model(state: Any, team_id: int, model: Any) -> list[dict[str, Any]]:
    """
    Compatible avec un `GameState` existant du client ou avec un `TurnState`.
    """
    if isinstance(state, TurnState):
        turn_state = state
    else:
        turn_state = TurnState.from_dict(
            {
                "turn": state.turn,
                "phase": state.phase,
                "penalty_remaining": state.penalty_remaining,
                "element": {
                    "x": state.element.x,
                    "y": state.element.y,
                    "carried_by_id": state.element.carried_by_id,
                },
                "robots": [
                    {
                        "id": r.id,
                        "team": r.team_id,
                        "type": r.type,
                        "x": r.x,
                        "y": r.y,
                        "alive": r.alive,
                        "shield": r.shield_direction,
                        "carrying_element": r.carrying_element,
                    }
                    for r in state.robots
                ],
            }
        )

    my_robots = [r for r in turn_state.robots if r.team == team_id and r.alive]
    commands: list[dict[str, Any]] = []

    for robot in my_robots:
        features = build_features(turn_state, team_id, robot.id)
        prediction = model.predict(features)
        commands.append(_prediction_to_command(robot.id, prediction))

    return commands
