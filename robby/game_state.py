# robby/game_state.py
# État du jeu vu par VOTRE équipe, reconstruit à chaque tour à partir du
# message du serveur, et outils pour décider (se déplacer, viser, fuir la
# tempête...).
#
# Repère : x de 0 (gauche) à map_width, y de 0 (HAUT) à map_height
#          (15000 x 15000 unités).
# Angles : degrés, sens horaire, 0 = haut, 90 = droite (comme une boussole).
# Distances : à vol d'oiseau (distance euclidienne).
#
# Les robots sont des disques de rayon `robot_radius` (300) : les ennemis se
# bloquent entre eux. Les outils ci-dessous refont les calculs du serveur
# avec ce que VOUS voyez (un ennemi invisible peut toujours gêner).

from robby.commands import move, shoot
from robby.constants import DEFAULT_CONFIG, SPAWN_STEP
from robby.geometry import (
    angle_to,
    direction,
    distance,
    in_sector,
    ray_circle,
    ray_sector,
)

Point = tuple[float, float]


def _pos(thing) -> Point:
    return thing.pos if hasattr(thing, "pos") else (thing[0], thing[1])


class Robot:
    """
    Un robot visible. `shield_direction` : angle du bouclier (ou None).
    `heading` et `speed` : cap et vitesse actuels. Le robot les GARDE d'un
    tour à l'autre (il continue d'avancer tout seul) jusqu'à une nouvelle
    commande MOVE, un blocage ou une pénalité (vitesse remise à 0).
    """

    def __init__(self, data: dict):
        self.id: int = data["id"]
        self.team_id: int = data["team"]
        self.type: str = data["type"]  # "R", "D" ou "K"
        self.x: float = data["x"]
        self.y: float = data["y"]
        self.alive: bool = data["alive"]
        self.shield_direction: float | None = data.get("shield")
        self.carrying_element: bool = data.get("carrying_element", False)
        self.penalty: int = data.get("penalty", 0)
        # Bouclier qui s'use (Défenseur) : chaque tir ennemi arrêté retire 1
        # point ; à 0 il se brise et ne peut pas être reposé pendant
        # shield_cooldown tours.
        self.shield_hp: int = data.get("shield_hp", 3)
        self.shield_cooldown: int = data.get("shield_cooldown", 0)
        self.shield_quiet: int = data.get("shield_quiet", 0)   # tours sans impact
        self.heading: float | None = data.get("heading")
        self.speed: float = data.get("speed") or 0

    @property
    def pos(self) -> Point:
        return (self.x, self.y)

    @property
    def can_act(self) -> bool:
        """Vivant et non pénalisé : une commande pour ce robot sera prise en compte."""
        return self.alive and self.penalty == 0

    @property
    def moving(self) -> bool:
        return self.speed > 0 and self.heading is not None

    @property
    def shield_ready(self) -> bool:
        """Le Défenseur peut-il (re)poser son bouclier ce tour-ci ?"""
        return self.type == "D" and self.shield_cooldown == 0

    def distance_to(self, other) -> float:
        return distance(self.pos, _pos(other))

    def angle_to(self, other) -> float | None:
        """Angle pour aller de ce robot vers `other` (robot ou point)."""
        return angle_to(self.pos, _pos(other))

    def __repr__(self):
        return (f"Robot(id={self.id}, team={self.team_id}, type={self.type}, "
                f"pos=({self.x}, {self.y}), alive={self.alive})")


class Element:
    """La batterie."""

    def __init__(self, data: dict):
        self.x: float = data["x"]
        self.y: float = data["y"]
        self.carried_by_id: int | None = data["carried_by_id"]

    @property
    def pos(self) -> Point:
        return (self.x, self.y)

    @property
    def is_free(self) -> bool:
        return self.carried_by_id is None


class GameState:
    """
    État du jeu tel que vu par VOTRE équipe à un tour donné.

    Attention au brouillard de guerre : `robots` contient vos robots
    (vivants ou morts) et SEULEMENT les ennemis détectés par vos radars.

    Outils principaux :
        state.move_towards(robot, point)     commande pour aller vers un point
        state.stop(robot)                    commande d'arrêt (vitesse 0)
        state.predict(robot, turns)          position future s'il garde son cap
        state.keep_safe(robot, commande)     tirer en roulant... sauf vers la tempête
        state.move_away(robot, point)        commande pour s'en éloigner
        state.aim(k, cible)                  angle de tir vers une cible
        state.targets_in_range(k)            ennemis qu'un tir toucherait
        state.zone_escape(robot)             point sûr si le robot est en danger
        state.safe_center                    centre du prochain cercle annoncé
        state.firing_spot(k, cible)          où aller pour contourner un bouclier
        state.shielded_targets(k)            ennemis derrière un bouclier : tirer
                                             dessus l'use, puis le brise
    """

    def __init__(self, msg: dict, team_id: int, config: dict | None = None):
        self.team_id = team_id
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        c = self.config

        self.turn: int = msg["turn"]
        self.phase: int = msg["phase"]
        self.phase_turn: int = msg.get("phase_turn", msg["turn"])
        self.element = Element(msg["element"])
        self.robots = [Robot(r) for r in msg.get("robots", [])]

        self.map_width: float = c["map_width"]
        self.map_height: float = c["map_height"]
        self.robot_radius = c["robot_radius"]
        self.shield_radius = c["shield_radius"]
        self.shield_arc = c["shield_arc"]
        self.pickup_radius = c["pickup_radius"]
        self.base_radius = c["base_radius"]

        # Tempête (phase 2) : un cercle sûr qui se resserre par étapes. Hors
        # du cercle en fin de tour, un robot est détruit. Le serveur envoie :
        #   center, radius (cercle à la fin de CE tour), forecast et
        #   forecast_centers (prochains tours), state ("calm", "pause",
        #   "shrink", "final"), target et target_center (prochain cercle
        #   annoncé), shrink_turn, end_turn.
        self.zone: dict = msg.get("zone") or self.calm_zone()

    # ------------------------------------------------------------------
    # Robots
    # ------------------------------------------------------------------

    @property
    def my_robots(self) -> list[Robot]:
        """Vos robots vivants."""
        return [r for r in self.robots if r.team_id == self.team_id and r.alive]

    @property
    def enemies(self) -> list[Robot]:
        """Ennemis vivants actuellement détectés par vos radars."""
        return [r for r in self.robots if r.team_id != self.team_id and r.alive]

    def my_robots_of_type(self, robot_type: str) -> list[Robot]:
        return [r for r in self.my_robots if r.type == robot_type]

    def get_robot(self, robot_id: int) -> Robot | None:
        return next((r for r in self.robots if r.id == robot_id), None)

    @staticmethod
    def nearest(origin, candidates):
        """Le robot de `candidates` le plus proche de `origin` (robot ou point)."""
        if not candidates:
            return None
        return min(candidates, key=lambda r: distance(_pos(origin), r.pos))

    # ------------------------------------------------------------------
    # Distances, arène
    # ------------------------------------------------------------------

    @staticmethod
    def distance(a, b) -> float:
        """Distance à vol d'oiseau entre deux robots ou points."""
        return distance(_pos(a), _pos(b))

    @property
    def center(self) -> Point:
        return (self.map_width / 2, self.map_height / 2)

    def is_inside(self, pos) -> bool:
        """Un robot centré sur `pos` tient-il dans l'arène ?"""
        r = self.robot_radius
        return r <= pos[0] <= self.map_width - r and r <= pos[1] <= self.map_height - r

    def base_of(self, team_id: int) -> Point | None:
        """Base d'une équipe (au milieu d'un côté de l'arène)."""
        bases = self.config.get("bases") or {}
        base = bases.get(str(team_id)) or bases.get(team_id)
        if base:
            return tuple(base)
        u, w, h = SPAWN_STEP, self.map_width, self.map_height
        return {1: (u / 2, h / 2), 2: (w - u / 2, h / 2),
                3: (w / 2, u / 2), 4: (w / 2, h - u / 2)}.get(team_id)

    @property
    def my_base(self) -> Point:
        return self.base_of(self.team_id)

    def on_base(self, robot) -> bool:
        return self.distance(robot, self.my_base) <= self.base_radius

    # ------------------------------------------------------------------
    # Déplacements
    # ------------------------------------------------------------------

    def max_speed(self, robot) -> float:
        """Distance maximale parcourue en un tour (R 1000, D 2000, K 5000)."""
        return self.config["move_speed"].get(robot.type, 0)

    speed = max_speed

    def destination(self, robot, angle, speed) -> Point:
        """Point d'arrivée si rien ne gêne (bords de l'arène compris)."""
        dx, dy = direction(angle)
        r = self.robot_radius
        return (min(max(robot.x + dx * speed, r), self.map_width - r),
                min(max(robot.y + dy * speed, r), self.map_height - r))

    def move_towards(self, robot, target, speed=None, stop_at=0.0):
        """
        Commande MOVE vers `target` (robot ou point), en s'arrêtant à
        `stop_at` unités de la cible. Vitesse : max du robot, ou `speed`,
        réduite pour ne pas dépasser le point visé CE tour-ci.
        Arrivé : commande d'arrêt si le robot roule encore (sinon il
        continuerait sur sa lancée), None s'il est déjà arrêté.
            commands.append(state.move_towards(k, ennemi, stop_at=2000))
        Rappel : le robot garde ce cap et cette vitesse aux tours suivants.
        Appelez move_towards à chaque tour pour corriger sa trajectoire.
        """
        goal = _pos(target)
        heading = angle_to(robot.pos, goal)
        gap = distance(robot.pos, goal) - stop_at
        if heading is None or gap <= 1:
            return self.stop(robot)
        limit = self.max_speed(robot) if speed is None else min(speed,
                                                                 self.max_speed(robot))
        return move(robot, angle=heading, speed=min(limit, gap))

    def stop(self, robot):
        """Commande d'arrêt (vitesse 0), ou None si le robot est déjà arrêté."""
        if getattr(robot, "speed", 0) > 0:
            return move(robot, angle=robot.heading or 0, speed=0)
        return None

    def predict(self, robot, turns: int = 1) -> Point:
        """Où sera `robot` dans `turns` tours s'il garde son cap et sa vitesse
        (sans obstacle) : utile pour viser un ennemi en mouvement... au tour
        suivant (un tir part de la position du DÉBUT de tour)."""
        if not getattr(robot, "speed", 0) or robot.heading is None:
            return robot.pos
        return self.destination(robot, robot.heading, robot.speed * turns)

    def safe_to_coast(self, robot, turns: int = 1) -> bool:
        """En continuant sur sa lancée (sans commande MOVE, par exemple s'il
        tire), le robot reste-t-il dans le cercle sûr pendant `turns` tours ?"""
        return all(self.in_zone(self.predict(robot, k), k, inset=self.robot_radius)
                   for k in range(1, turns + 1))

    def keep_safe(self, robot, command):
        """Garde `command` (tir, bouclier...) si le robot peut continuer sur sa
        lancée sans finir dans la tempête ; sinon commande pour s'en écarter."""
        if command is None or command.get("action") == "MOVE" \
                or self.safe_to_coast(robot):
            return command
        return (self.move_towards(robot, self.clamp_to_zone(robot.pos, 2))
                or self.stop(robot) or command)

    def move_away(self, robot, threat, speed=None):
        """Commande MOVE pour s'éloigner de `threat` (robot ou point)."""
        heading = angle_to(_pos(threat), robot.pos)
        if heading is None:
            heading = angle_to(robot.pos, self.center) or 0
        limit = self.max_speed(robot) if speed is None else speed
        return move(robot, angle=heading, speed=min(limit, self.max_speed(robot)))

    # ------------------------------------------------------------------
    # Tempête (phase 2)
    # ------------------------------------------------------------------

    def calm_zone(self) -> dict:
        """Pas de tempête (phase 1, ou serveur qui n'envoie rien)."""
        w, h = self.map_width, self.map_height
        radius = (w * w + h * h) ** 0.5   # largement plus grand que l'arène
        return {"center": [w / 2, h / 2], "radius": radius,
                "forecast": [radius], "state": "calm", "target": None,
                "shrink_turn": None, "end_turn": None}

    @property
    def storm_center(self):
        """Centre du cercle sûr à la fin de ce tour."""
        return tuple(self.zone["center"])

    def storm_center_at(self, lookahead: int = 0):
        """Centre du cercle sûr dans `lookahead` tours. Avec l'option de
        tempête aléatoire du serveur, le centre glisse pendant les avancées."""
        centers = self.zone.get("forecast_centers") or [self.zone["center"]]
        return tuple(centers[min(max(lookahead, 0), len(centers) - 1)])

    @property
    def safe_center(self):
        """Centre du prochain cercle annoncé (sinon du cercle actuel) : le
        meilleur endroit où se regrouper avant que la tempête n'avance."""
        return tuple(self.zone.get("target_center") or self.zone["center"])

    def storm_radius(self, lookahead: int = 0) -> float:
        """Rayon sûr à la fin de ce tour (0), du suivant (1), etc."""
        forecast = self.zone.get("forecast") or [self.zone["radius"]]
        return forecast[min(max(lookahead, 0), len(forecast) - 1)]

    def in_zone(self, pos, lookahead: int = 0, inset: float = 0.0) -> bool:
        """Le point est-il (dans `lookahead` tours) à plus de `inset` unités à
        l'intérieur du cercle sûr ?"""
        center = self.storm_center_at(lookahead)
        radius = self.storm_radius(lookahead)
        return radius > 0 and distance(pos, center) <= radius - inset

    def clamp_to_zone(self, pos, lookahead: int = 0, inset: float | None = None):
        """Point le plus proche de `pos` dans le cercle sûr (avec une marge)."""
        inset = self.robot_radius if inset is None else inset
        radius = max(0.0, self.storm_radius(lookahead) - inset)
        center = self.storm_center_at(lookahead)
        d = distance(pos, center)
        if d <= radius:
            return (pos[0], pos[1])
        if d < 1e-9:
            return center
        return (center[0] + (pos[0] - center[0]) * radius / d,
                center[1] + (pos[1] - center[1]) * radius / d)

    def zone_escape(self, robot, lookahead: int = 2) -> Point | None:
        """Point sûr où aller si le robot est (ou sera dans `lookahead`
        tours) hors de la zone ; None s'il est à l'abri."""
        if self.in_zone(robot.pos, lookahead, inset=50):
            return None
        return self.clamp_to_zone(robot.pos, lookahead)

    # ------------------------------------------------------------------
    # Boucliers
    # ------------------------------------------------------------------

    def enemy_shields(self):
        """Boucliers ennemis VISIBLES : [(centre, angle)]."""
        return [(r.pos, r.shield_direction) for r in self.robots
                if r.alive and r.type == "D" and r.team_id != self.team_id
                and r.shield_direction is not None]

    def in_enemy_shield(self, pos) -> bool:
        return any(in_sector(pos, c, self.shield_radius, a, self.shield_arc)
                   for c, a in self.enemy_shields())

    # ------------------------------------------------------------------
    # Tir : rayon instantané depuis la position du Destructeur
    # ------------------------------------------------------------------

    def aim(self, shooter, target) -> float | None:
        """Angle de tir vers `target` (robot ou point)."""
        return angle_to(shooter.pos, _pos(target))

    def first_hit(self, shooter, angle, origin=None):
        """
        Ce que toucherait un tir dans la direction `angle`, d'après ce que
        vous voyez : (robot touché ou None, bloqué par un bouclier ?, distance).
        `origin` : tirer depuis un autre point que la position du robot
        (pour tester une position avant d'y aller).
        """
        start = shooter.pos if origin is None else origin
        reach, hit = self.config["destructor_range"], None
        for r in self.robots:
            if not r.alive or r.team_id == shooter.team_id:
                continue
            t = ray_circle(start, angle, reach, r.pos, self.robot_radius)
            if t is not None and t < reach:
                reach, hit = t, r
        for center, heading in self.enemy_shields():
            t = ray_sector(start, angle, reach, center, self.shield_radius,
                           heading, self.shield_arc)
            if t is not None and t <= reach:
                return None, True, t
        return hit, False, reach

    def can_hit_from(self, shooter, pos, target) -> bool:
        """Depuis `pos`, un tir visé sur `target` la toucherait-il ?"""
        angle = angle_to(pos, target.pos)
        if angle is None:
            return False
        hit, _, _ = self.first_hit(shooter, angle, origin=pos)
        return hit is target

    def firing_spot(self, shooter, target, lookahead: int = 1):
        """
        Point atteignable CE tour d'où `shooter` pourra tirer sur `target`
        au tour suivant sans être arrêté par un bouclier visible (contourner
        un bouclier) ; le plus proche de sa position. None si aucun.
        """
        best = None
        reach = self.config["destructor_range"] - 300
        for radius in (reach, reach * 0.8, reach * 0.6):
            for k in range(24):
                dx, dy = direction(15 * k)
                spot = (target.x + dx * radius, target.y + dy * radius)
                cost = distance(shooter.pos, spot)
                if cost > self.max_speed(shooter) or not self.is_inside(spot):
                    continue
                if not self.in_zone(spot, lookahead, inset=self.robot_radius):
                    continue
                if self.in_enemy_shield(spot) or not self.can_hit_from(shooter, spot,
                                                                       target):
                    continue
                if best is None or cost < best[0]:
                    best = (cost, spot)
        return best[1] if best else None

    def in_range(self, shooter, target) -> bool:
        """Le bord de la cible est-il à portée de tir ?"""
        return (self.distance(shooter, target) - self.robot_radius
                <= self.config["destructor_range"])

    def is_shot_blocked(self, shooter, target) -> bool:
        """True si un tir visé sur `target` ne la toucherait pas (bouclier
        ennemi visible, ou autre ennemi devant)."""
        hit, _, _ = self.first_hit(shooter, self.aim(shooter, target))
        return hit is not target

    def shielded_targets(self, shooter) -> list:
        """Ennemis visibles à portée, mais derrière un bouclier ennemi : tirer
        dessus USE ce bouclier (il se brise au bout de shield_hp tirs)."""
        result = []
        for e in self.enemies:
            if not self.in_range(shooter, e):
                continue
            _, blocked, _ = self.first_hit(shooter, self.aim(shooter, e))
            if blocked:
                result.append(e)
        return result

    def targets_in_range(self, shooter) -> list:
        """Ennemis visibles qu'un tir visé sur eux toucherait vraiment."""
        return [e for e in self.enemies
                if self.in_range(shooter, e) and not self.is_shot_blocked(shooter, e)]

    def shoot_at(self, shooter, target):
        """Commande SHOOT visée sur `target`."""
        return shoot(shooter, angle=self.aim(shooter, target))
