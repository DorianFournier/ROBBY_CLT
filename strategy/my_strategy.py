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
            if random.random() < 0.5:
                commands.append({
                    "robot_id": robot.id,
                    "action":    "SHIELD",
                    "direction": random.choice(SHIELD_DIRECTIONS),
                })
            else:
                commands.append({
                    "robot_id": robot.id,
                    "action":   "MOVE",
                    "target_x": random.randint(0, 14),
                    "target_y": random.randint(0, 14),
                    "speed":    robot.max_speed,
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
                    "robot_id": robot.id,
                    "action":   "MOVE",
                    "target_x": random.randint(0, 14),
                    "target_y": random.randint(0, 14),
                    "speed":    robot.max_speed,
                })

        elif robot.type == "R":
            element = state.element
            if element.carried_by_id is None:
                commands.append({
                    "robot_id": robot.id,
                    "action":   "MOVE",
                    "target_x": element.x,
                    "target_y": element.y,
                    "speed":    robot.max_speed,
                })
            elif element.carried_by_id == robot.id:
                base = _get_base_position(team_id)
                print(f"\n---> base : {base}\n")
                if base:
                    commands.append({
                        "robot_id": robot.id,
                        "action":   "MOVE",
                        "target_x": base[0],
                        "target_y": base[1],
                        "speed":    robot.max_speed,
                    })

    return commands

def _get_base_position(team_id: int):
    bases = {
        1: (0.0,  5.0),
        2: (11.0, 5.0),
        3: (5.5,  0.0),
        4: (5.5, 11.0),
    }
    return bases.get(team_id)
