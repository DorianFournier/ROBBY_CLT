# robby/free_state.py
# État du jeu en MODE LIBRE (V2) : positions continues, angles, vitesses.
#
# Repère : x de 0 (gauche) à map_width, y de 0 (HAUT) à map_height
#          (15000 x 15000 unités ; 1 case de la V1 = 1000 unités).
# Angles : degrés, sens horaire, 0 = haut, 90 = droite (comme une boussole).
# Distances : à vol d'oiseau (distance euclidienne).
#
# Les robots sont des disques de rayon `robot_radius` (300) : ils se
# bloquent entre eux. Les outils ci-dessous refont les calculs du serveur
# avec ce que VOUS voyez (un ennemi invisible peut toujours gêner).

from robby.commands import move, shoot
from robby.game_state import Element, GameState, Robot
from robby.geometry import (
    angle_to,
    direction,
    distance,
    in_sector,
    ray_circle,
    ray_sector,
)

Point = tuple[float, float]

FREE_DEFAULTS = {
    "mode": "libre",
    "unit": 1000,
    "map_width": 15000,
    "map_height": 15000,
    "radar_range": 3000,
    "destructor_range": 3000,
    "move_speed": {"R": 1000, "D": 2000, "K": 5000},   # vitesse max par tour
    "robot_radius": 300,
    "shield_radius": 1500,
    "shield_arc": 90,
    "pickup_radius": 500,
    "base_radius": 700,
}


def _pos(thing) -> Point:
    return thing.pos if hasattr(thing, "pos") else (thing[0], thing[1])


class FreeRobot(Robot):
    """Robot du mode libre : `shield_direction` est un angle (ou None)."""

    def distance_to(self, other) -> float:
        return distance(self.pos, _pos(other))

    def angle_to(self, other) -> float | None:
        """Angle pour aller de ce robot vers `other` (robot ou point)."""
        return angle_to(self.pos, _pos(other))


class FreeGameState(GameState):
    """
    Même interface que GameState (my_robots, enemies, element, my_base,
    phase, turn, zone...), plus les outils du mode libre :

        state.move_towards(robot, point)     commande pour aller vers un point
        state.move_away(robot, point)        commande pour s'en éloigner
        state.aim(k, cible)                  angle de tir vers une cible
        state.targets_in_range(k)            ennemis qu'un tir toucherait
        state.zone_escape(robot)             point sûr si le robot est en danger
        state.firing_spot(k, cible)          où aller pour contourner un bouclier
    """

    mode = "libre"

    def __init__(self, msg: dict, team_id: int, config: dict | None = None):
        super().__init__(msg, team_id, {**FREE_DEFAULTS, **(config or {})})
        self.robots = [FreeRobot(r) for r in msg.get("robots", [])]
        self.element = Element(msg["element"])
        c = self.config
        self.unit = c["unit"]
        self.robot_radius = c["robot_radius"]
        self.shield_radius = c["shield_radius"]
        self.shield_arc = c["shield_arc"]
        self.pickup_radius = c["pickup_radius"]
        self.base_radius = c["base_radius"]

    # ------------------------------------------------------------------
    # Distances, carte
    # ------------------------------------------------------------------

    @staticmethod
    def distance(a, b) -> float:
        """Distance à vol d'oiseau entre deux robots ou points."""
        return distance(_pos(a), _pos(b))

    @staticmethod
    def nearest(origin, candidates):
        if not candidates:
            return None
        return min(candidates, key=lambda r: distance(_pos(origin), r.pos))

    @property
    def center(self) -> Point:
        return (self.map_width / 2, self.map_height / 2)

    def is_inside(self, pos) -> bool:
        """Un robot centré sur `pos` tient-il dans l'arène ?"""
        r = self.robot_radius
        return r <= pos[0] <= self.map_width - r and r <= pos[1] <= self.map_height - r

    def base_of(self, team_id: int) -> Point | None:
        bases = self.config.get("bases") or {}
        base = bases.get(str(team_id)) or bases.get(team_id)
        if base:
            return tuple(base)
        u, w, h = self.unit, self.map_width, self.map_height
        return {1: (u / 2, h / 2), 2: (w - u / 2, h / 2),
                3: (w / 2, u / 2), 4: (w / 2, h - u / 2)}.get(team_id)

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
        réduite pour ne pas dépasser le point visé. None si déjà sur place.
            commands.append(state.move_towards(k, ennemi, stop_at=2000))
        """
        goal = _pos(target)
        heading = angle_to(robot.pos, goal)
        gap = distance(robot.pos, goal) - stop_at
        if heading is None or gap <= 1:
            return None
        limit = self.max_speed(robot) if speed is None else min(speed,
                                                                 self.max_speed(robot))
        return move(robot, angle=heading, speed=min(limit, gap))

    def move_away(self, robot, threat, speed=None):
        """Commande MOVE pour s'éloigner de `threat` (robot ou point)."""
        heading = angle_to(_pos(threat), robot.pos)
        if heading is None:
            heading = angle_to(robot.pos, self.center) or 0
        limit = self.max_speed(robot) if speed is None else speed
        return move(robot, angle=heading, speed=min(limit, self.max_speed(robot)))

    # ------------------------------------------------------------------
    # Tempête (phase 2) : cercle sûr (voir GameState.storm_radius)
    # ------------------------------------------------------------------

    def calm_zone(self) -> dict:
        zone = super().calm_zone()
        zone["center"] = [self.map_width / 2, self.map_height / 2]
        return zone

    def in_zone(self, pos, lookahead: int = 0, inset: float = 0.0) -> bool:
        """Le point est-il (dans `lookahead` tours) à plus de `inset` unités à
        l'intérieur du cercle sûr ?"""
        return distance(pos, self.storm_center) <= self.storm_radius(lookahead) - inset

    def clamp_to_zone(self, pos, lookahead: int = 0, inset: float | None = None):
        """Point le plus proche de `pos` dans le cercle sûr (avec une marge)."""
        inset = self.robot_radius if inset is None else inset
        radius = max(0.0, self.storm_radius(lookahead) - inset)
        center = self.storm_center
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

    def targets_in_range(self, shooter) -> list:
        """Ennemis visibles qu'un tir visé sur eux toucherait vraiment."""
        return [e for e in self.enemies
                if self.in_range(shooter, e) and not self.is_shot_blocked(shooter, e)]

    def shoot_at(self, shooter, target):
        """Commande SHOOT visée sur `target`."""
        return shoot(shooter, angle=self.aim(shooter, target))

    # ------------------------------------------------------------------
    # Outils de la grille : sans objet en mode libre
    # ------------------------------------------------------------------

    def _grid_only(self, *args, **kwargs):
        raise NotImplementedError(
            "Outil du mode grille : en mode libre, utilisez state.move_towards(), "
            "state.zone_escape(), state.targets_in_range()...")

    shortest_path = path_towards = can_follow = can_move = _grid_only
    possible_moves = direction_towards = zone_escape_path = _grid_only
    trim_to_free = shield_cells = robots_at = _grid_only
