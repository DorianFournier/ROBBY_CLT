from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RobotState:
    id: int
    team: int
    type: str
    x: int
    y: int
    alive: bool
    shield: str | None
    carrying_element: bool


@dataclass(slots=True)
class ElementState:
    x: int
    y: int
    carried_by_id: int | None


@dataclass(slots=True)
class TurnState:
    turn: int
    phase: str
    penalty_remaining: int
    element: ElementState
    robots: list[RobotState]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TurnState":
        element = ElementState(**payload["element"])
        robots = [RobotState(**raw_robot) for raw_robot in payload.get("robots", [])]
        return cls(
            turn=payload["turn"],
            phase=payload["phase"],
            penalty_remaining=payload["penalty_remaining"],
            element=element,
            robots=robots,
        )


@dataclass(slots=True)
class TrainingExample:
    state: TurnState
    team_id: int
    robot_id: int
    action: str
    direction: str | None = None
    target_id: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TrainingExample":
        return cls(
            state=TurnState.from_dict(payload["state"]),
            team_id=payload["team_id"],
            robot_id=payload["robot_id"],
            action=payload["action"],
            direction=payload.get("direction"),
            target_id=payload.get("target_id"),
        )
