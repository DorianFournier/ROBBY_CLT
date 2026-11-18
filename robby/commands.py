# robby/commands.py
# Fabriques de commandes : évitent les fautes de frappe dans les dicts.
#
# Règles (sinon le robot est pénalisé PENALTY_TURNS tours) :
#   - une seule commande par robot et par tour
#   - MOVE   : n'importe quel robot vivant, vers une case de la carte
#              qui n'est pas couverte par un bouclier
#   - SHOOT  : Destructeur (K) uniquement, cible ennemie vivante à portée
#   - SHIELD : Défenseur (D) uniquement

from robby.constants import DIRECTIONS, SHIELD_DIRECTIONS


def _robot_id(robot) -> int:
    return robot if isinstance(robot, int) else robot.id


def move(robot, direction: str) -> dict:
    """Déplace `robot` d'une case : U, UR, R, DR, D, DL, L, UL."""
    if direction not in DIRECTIONS:
        raise ValueError(f"Direction inconnue : {direction!r}")
    return {"robot_id": _robot_id(robot), "action": "MOVE", "direction": direction}


def shoot(robot, target) -> dict:
    """Le Destructeur `robot` tire sur `target` (Robot ou id)."""
    return {"robot_id": _robot_id(robot), "action": "SHOOT",
            "target_id": _robot_id(target)}


def shield(robot, direction: str) -> dict:
    """Le Défenseur `robot` place son bouclier : SU, SR, SD, SL."""
    if direction not in SHIELD_DIRECTIONS:
        raise ValueError(f"Direction de bouclier inconnue : {direction!r}")
    return {"robot_id": _robot_id(robot), "action": "SHIELD", "direction": direction}
