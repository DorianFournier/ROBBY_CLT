from robby_ia.features import build_features, action_to_label
from robby_ia.schemas import TurnState


def test_build_features_shape() -> None:
    state = TurnState.from_dict(
        {
            "turn": 1,
            "phase": "main",
            "penalty_remaining": 0,
            "element": {"x": 5, "y": 5, "carried_by_id": None},
            "robots": [
                {"id": 1, "team": 0, "type": "R", "x": 1, "y": 1, "alive": True, "shield": None, "carrying_element": False},
                {"id": 2, "team": 1, "type": "K", "x": 3, "y": 3, "alive": True, "shield": None, "carrying_element": False},
            ],
        }
    )

    feats = build_features(state, team_id=0, robot_id=1)
    assert len(feats) == 11


def test_action_to_label() -> None:
    assert action_to_label("MOVE", "UR") == "MOVE:UR"
    assert action_to_label("SHOOT", None) == "SHOOT"
