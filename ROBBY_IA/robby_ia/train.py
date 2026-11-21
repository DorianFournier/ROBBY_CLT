from __future__ import annotations

import argparse

from .dataset import build_training_matrix
from .model import RobbyPolicyModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entraîner une politique ROBBY_IA")
    parser.add_argument("--dataset", required=True, help="Chemin du dataset JSONL")
    parser.add_argument("--output", required=True, help="Chemin du modèle exporté (.joblib)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X, y = build_training_matrix(args.dataset)

    if not X:
        raise ValueError("Dataset vide : impossible d'entraîner un modèle")

    model = RobbyPolicyModel.create_default()
    model.fit(X, y)
    model.save(args.output)

    print(f"[ROBBY_IA] Modèle entraîné sur {len(X)} exemples")
    print(f"[ROBBY_IA] Modèle sauvegardé : {args.output}")


if __name__ == "__main__":
    main()
