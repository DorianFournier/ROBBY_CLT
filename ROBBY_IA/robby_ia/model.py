from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier


@dataclass
class RobbyPolicyModel:
    estimator: RandomForestClassifier

    @classmethod
    def create_default(cls, random_state: int = 42) -> "RobbyPolicyModel":
        estimator = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=2,
            random_state=random_state,
            n_jobs=-1,
        )
        return cls(estimator=estimator)

    def fit(self, X: list[list[float]], y: list[str]) -> None:
        self.estimator.fit(X, y)

    def predict(self, feature_vector: list[float]) -> str:
        return str(self.estimator.predict([feature_vector])[0])

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.estimator, path)

    @classmethod
    def load(cls, path: str | Path) -> "RobbyPolicyModel":
        estimator = joblib.load(path)
        return cls(estimator=estimator)
