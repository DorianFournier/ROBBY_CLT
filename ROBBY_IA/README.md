# ROBBY_IA

`ROBBY_IA` est un nouveau dépôt (dans ce monorepo) dédié à la création d'une IA pour un futur client **ROBBY_CLIENT_IA**.

## Objectif

Construire une IA de décision de commandes robots avec une approche **Machine Learning supervisée**:

1. Charger des journaux de parties (`game_state` + action jouée).
2. Construire des features numériques.
3. Entraîner un modèle de classification.
4. Exporter le modèle pour l'intégrer côté client (inférence en temps réel).

## Structure

- `robby_ia/schemas.py` : structures de données pour états/actions.
- `robby_ia/features.py` : transformation état de jeu -> vecteur ML.
- `robby_ia/dataset.py` : parsing JSONL pour dataset d'entraînement.
- `robby_ia/model.py` : classe `RobbyPolicyModel` (fit/predict/save/load).
- `robby_ia/train.py` : script CLI d'entraînement.
- `robby_ia/inference.py` : adaptation de la prédiction modèle en commandes client.
- `scripts/train_policy.py` : point d'entrée exécutable.

## Format attendu pour le dataset

Le dataset doit être un fichier JSONL avec une ligne par décision, par exemple :

```json
{"state": {"turn": 12, "phase": "main", "penalty_remaining": 0, "element": {"x": 9, "y": 8, "carried_by_id": null}, "robots": [{"id": 1, "team": 0, "type": "R", "x": 1, "y": 2, "alive": true, "shield": null, "carrying_element": false}]}, "team_id": 0, "robot_id": 1, "action": "MOVE", "direction": "UR"}
```

## Lancer un entraînement

```bash
python scripts/train_policy.py \
  --dataset data/train.jsonl \
  --output artifacts/policy.joblib
```

## Intégration dans un client ROBBY

Exemple rapide :

```python
from robby_ia.model import RobbyPolicyModel
from robby_ia.inference import decide_with_model
from game_state import GameState

model = RobbyPolicyModel.load("artifacts/policy.joblib")
commands = decide_with_model(state=GameState(msg), team_id=my_team_id, model=model)
```

## Évolutions recommandées

- Passer d'une classification de l'action globale à une politique multi-sorties (action + paramètres).
- Ajouter des données de simulation self-play.
- Ajouter un modèle séquentiel pour prendre en compte l'historique des tours.
