# strategy/my_strategy.py
# =====================================================
# C'est ici que tu développes ta stratégie.
# La fonction `decide` est appelée à chaque tour.
#
# Elle reçoit :
#   - state     : GameState  → état du jeu visible par ton équipe
#   - team_id   : int        → ton identifiant d'équipe
#
# Elle doit retourner :
#   - commands  : list[dict] → une commande par robot (max 3)
#
# Format d'une commande :
#   MOVE   → {"robot_id": X, "action": "MOVE",   "direction": "U/R/D/L/UR/DR/DL/UL"}
#   SHOOT  → {"robot_id": X, "action": "SHOOT",  "target_id": Y}
#   SHIELD → {"robot_id": X, "action": "SHIELD", "direction": "SU/SD/SL/SR"}
# =====================================================

from game_state import GameState
import random

DIRECTIONS = ["U", "UR", "R", "DR", "D", "DL", "L", "UL"]
SHIELD_DIRECTIONS = ["SU", "SD", "SL", "SR"]


def decide(state: GameState, team_id: int) -> list[dict]:
    """
    Stratégie par défaut : mouvements et actions aléatoires.
    À remplacer par votre propre logique.
    """
    commands = []

    my_robots = state.get_my_robots(team_id)
    enemies   = state.get_visible_enemies(team_id)

    for robot in my_robots:

        if robot.type == "D":
            # Défenseur : place un bouclier aléatoire
            commands.append({
                "robot_id": robot.id,
                "action":    "SHIELD",
                "direction": random.choice(SHIELD_DIRECTIONS),
            })

        elif robot.type == "K":
            # Destructeur : tire sur un ennemi à portée, sinon bouge
            targets_in_range = [
                e for e in enemies
                if max(abs(robot.x - e.x), abs(robot.y - e.y)) <= 3
            ]
            if targets_in_range:
                target = random.choice(targets_in_range)
                commands.append({
                    "robot_id": robot.id,
                    "action":   "SHOOT",
                    "target_id": target.id,
                })
            else:
                commands.append({
                    "robot_id":  robot.id,
                    "action":    "MOVE",
                    "direction": random.choice(DIRECTIONS),
                })

        elif robot.type == "R":
            # Radar : se déplace aléatoirement
            commands.append({
                "robot_id":  robot.id,
                "action":    "MOVE",
                "direction": random.choice(DIRECTIONS),
            })

    return commands