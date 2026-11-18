# robby/commands.py
# Fabriques de commandes : évitent les fautes de frappe dans les dicts.
#
# Règles (sinon le robot est pénalisé PENALTY_TURNS tours) :
#   - une seule commande par robot et par tour
#   - MOVE   : n'importe quel robot vivant ; au plus MOVE_SPEED cases
#              (K 3, D 2, R 1), chaque case dans la carte et hors des
#              boucliers ennemis
#   - SHOOT  : Destructeur (K) uniquement, cible ennemie vivante à portée
#   - SHIELD : Défenseur (D) uniquement

from robby.constants import DIRECTIONS, SHIELD_DIRECTIONS


def _robot_id(robot) -> int:
    return robot if isinstance(robot, int) else robot.id


def move(robot, *directions: str) -> dict:
    """
    Déplace `robot` en suivant une ou plusieurs directions
    (U, UR, R, DR, D, DL, L, UL), une case par direction.

    Nombre de cases maximal par tour (vitesse) : K 3, D 2, R 1.
        move(k, "R", "R", "UR")   # le K avance de 3 cases
        move(r, "U")              # le R avance d'une case
    On peut aussi passer une liste : move(k, *chemin)
    """
    if not directions:
        raise ValueError("move() demande au moins une direction")
    for direction in directions:
        if direction not in DIRECTIONS:
            raise ValueError(f"Direction inconnue : {direction!r}")
    return {"robot_id": _robot_id(robot), "action": "MOVE", "path": list(directions)}


def shoot(robot, target) -> dict:
    """Le Destructeur `robot` tire sur `target` (Robot ou id)."""
    return {"robot_id": _robot_id(robot), "action": "SHOOT",
            "target_id": _robot_id(target)}


def shield(robot, direction: str) -> dict:
    """Le Défenseur `robot` place son bouclier : SU, SR, SD, SL."""
    if direction not in SHIELD_DIRECTIONS:
        raise ValueError(f"Direction de bouclier inconnue : {direction!r}")
    return {"robot_id": _robot_id(robot), "action": "SHIELD", "direction": direction}
