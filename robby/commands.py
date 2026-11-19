# robby/commands.py
# Fabriques de commandes : évitent les fautes de frappe dans les dicts.
#
# Règles (sinon le robot est pénalisé PENALTY_TURNS tours) :
#   - une seule commande par robot et par tour ;
#   - angle : un nombre de degrés, sens horaire, 0 = haut, 90 = droite
#     (comme une boussole) ; -90 et 270 sont le même angle.
#
#   move(robot, angle=90, speed=2000)   règle le CAP et la VITESSE du robot
#                                       (0 <= speed <= max : R 1000, D 2000,
#                                       K 5000 unités par tour). Le robot les
#                                       garde : il continue d'avancer tout seul
#                                       aux tours suivants, même s'il tire ou
#                                       pose son bouclier. speed=0 : il s'arrête.
#   stop(robot)                         = move(robot, angle=0, speed=0)
#   shoot(k, angle=45)                  Destructeur (K) : rayon qui touche le
#                                       premier ennemi rencontré
#   shield(d, angle=180)                Défenseur (D) : secteur de 90° centré
#                                       sur l'angle

from robby.geometry import is_number


def _robot_id(robot) -> int:
    return robot if isinstance(robot, int) else robot.id


def _angle(angle) -> float:
    if not is_number(angle):
        raise ValueError(f"Angle invalide : {angle!r} (nombre de degrés attendu)")
    return round(float(angle) % 360, 3)


def move(robot, angle, speed) -> dict:
    """
    Règle le cap (`angle`) et la vitesse (`speed`, en unités par tour, au plus
    R 1000, D 2000, K 5000) du robot. Il les GARDE : il continue d'avancer
    dans cette direction à chaque tour, jusqu'à une nouvelle commande MOVE,
    un blocage (ennemi, bouclier ennemi) ou une pénalité. speed=0 l'arrête.
        move(radar, angle=90, speed=1000)    # vers la droite, à fond
    """
    if not is_number(speed) or speed < 0:
        raise ValueError(f"Vitesse invalide : {speed!r} (nombre >= 0 attendu)")
    return {"robot_id": _robot_id(robot), "action": "MOVE",
            "angle": _angle(angle), "speed": round(float(speed), 3)}


def stop(robot) -> dict:
    """Arrête le robot (vitesse 0)."""
    return move(robot, angle=0, speed=0)


def shoot(robot, angle) -> dict:
    """Le Destructeur `robot` tire dans la direction `angle`
    (state.aim(k, cible) donne l'angle vers une cible)."""
    return {"robot_id": _robot_id(robot), "action": "SHOOT", "angle": _angle(angle)}


def shield(robot, angle) -> dict:
    """Le Défenseur `robot` tourne son bouclier vers `angle`."""
    return {"robot_id": _robot_id(robot), "action": "SHIELD", "angle": _angle(angle)}
