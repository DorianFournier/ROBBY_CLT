# robby/commands.py
# Fabriques de commandes : évitent les fautes de frappe dans les dicts.
#
# Règles (sinon le robot est pénalisé PENALTY_TURNS tours) :
#   - une seule commande par robot et par tour
#
# MODE GRILLE (V1)
#   - MOVE   : n'importe quel robot vivant ; au plus MOVE_SPEED cases
#              (K 3, D 2, R 1), chaque case dans la carte et hors des
#              boucliers ennemis
#   - SHOOT  : Destructeur (K) uniquement, cible ennemie vivante à portée
#   - SHIELD : Défenseur (D) uniquement
#
# MODE LIBRE (V2) : mêmes fonctions, avec des mots-clés
#   move(robot, angle=90, speed=2000)   0 <= speed <= max (R 1000, D 2000, K 5000)
#   shoot(k, angle=45)                  rayon : touche le 1er ennemi rencontré
#   shield(d, angle=180)                secteur de 90° centré sur l'angle
#   Angles en degrés, sens horaire, 0 = haut, 90 = droite (boussole).

from robby.constants import DIRECTIONS, SHIELD_DIRECTIONS
from robby.geometry import is_number


def _robot_id(robot) -> int:
    return robot if isinstance(robot, int) else robot.id


def _angle(angle) -> float:
    if not is_number(angle):
        raise ValueError(f"Angle invalide : {angle!r} (nombre de degrés attendu)")
    return round(float(angle) % 360, 3)


def move(robot, *directions: str, angle=None, speed=None) -> dict:
    """
    Mode grille : déplace `robot` en suivant une ou plusieurs directions
    (U, UR, R, DR, D, DL, L, UL), une case par direction.
    Nombre de cases maximal par tour (vitesse) : K 3, D 2, R 1.
        move(k, "R", "R", "UR")   # le K avance de 3 cases
        move(r, "U")              # le R avance d'une case
    On peut aussi passer une liste : move(k, *chemin)

    Mode libre : move(robot, angle=90, speed=2000)
        le robot part dans la direction `angle` et parcourt `speed` unités
        (au plus R 1000, D 2000, K 5000).
    """
    if angle is not None or speed is not None:
        if directions:
            raise ValueError("move() : directions OU angle/speed, pas les deux")
        if not is_number(speed) or speed < 0:
            raise ValueError(f"Vitesse invalide : {speed!r} (nombre >= 0 attendu)")
        return {"robot_id": _robot_id(robot), "action": "MOVE",
                "angle": _angle(angle), "speed": round(float(speed), 3)}
    if not directions:
        raise ValueError("move() demande au moins une direction "
                         "(ou angle=..., speed=... en mode libre)")
    for direction in directions:
        if direction not in DIRECTIONS:
            raise ValueError(f"Direction inconnue : {direction!r}")
    return {"robot_id": _robot_id(robot), "action": "MOVE", "path": list(directions)}


def shoot(robot, target=None, *, angle=None) -> dict:
    """
    Mode grille : le Destructeur `robot` tire sur `target` (Robot ou id).
    Mode libre  : shoot(k, angle=45) tire dans la direction `angle`
                  (state.aim(k, cible) donne l'angle vers une cible).
    """
    if angle is not None:
        return {"robot_id": _robot_id(robot), "action": "SHOOT",
                "angle": _angle(angle)}
    if target is None:
        raise ValueError("shoot() demande une cible (ou angle=... en mode libre)")
    return {"robot_id": _robot_id(robot), "action": "SHOOT",
            "target_id": _robot_id(target)}


def shield(robot, direction: str | None = None, *, angle=None) -> dict:
    """
    Mode grille : le Défenseur `robot` place son bouclier : SU, SR, SD, SL.
    Mode libre  : shield(d, angle=180) : bouclier tourné vers `angle`.
    """
    if angle is not None:
        return {"robot_id": _robot_id(robot), "action": "SHIELD",
                "angle": _angle(angle)}
    if direction not in SHIELD_DIRECTIONS:
        raise ValueError(f"Direction de bouclier inconnue : {direction!r}")
    return {"robot_id": _robot_id(robot), "action": "SHIELD", "direction": direction}
