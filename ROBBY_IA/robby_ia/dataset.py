from __future__ import annotations

import json
from pathlib import Path

from .features import build_features, action_to_label
from .schemas import TrainingExample


def load_jsonl_examples(path: str | Path) -> list[TrainingExample]:
    items: list[TrainingExample] = []
    data_path = Path(path)

    with data_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            items.append(TrainingExample.from_dict(payload))

    return items


def build_training_matrix(path: str | Path) -> tuple[list[list[float]], list[str]]:
    examples = load_jsonl_examples(path)
    X: list[list[float]] = []
    y: list[str] = []

    for ex in examples:
        X.append(build_features(ex.state, ex.team_id, ex.robot_id))
        y.append(action_to_label(ex.action, ex.direction))

    return X, y
