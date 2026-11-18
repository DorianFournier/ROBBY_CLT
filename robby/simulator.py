# robby/simulator.py
# MODE LIBRE : simulateur d'UN tour, côté client.
#
# Il refait les calculs du serveur (mêmes règles, même ordre) sur ce que
# votre équipe voit. Il sert à TESTER des commandes avant de les envoyer :
#
#     sim = TurnSimulator(state)                       # copie de l'état visible
#     after = sim.run({state.team_id: mes_commandes,   # vos commandes...
#                      2: commandes_supposees_de_l_equipe_2})   # ...et celles
#     after.robot(13).alive, after.robot(13).pos       # que vous prêtez aux autres
#
# Ordre de résolution (comme le serveur) :
#   1. tirs, sur les positions du DÉBUT de tour ; morts
#   2. déplacements des survivants, en petits pas simultanés : un robot
#      s'arrête avant de toucher un ennemi ou d'entrer dans un bouclier ennemi
#   3. batterie (ramassage, capture), boucliers, zone
#
# Limites : les ennemis invisibles n'existent pas pour le simulateur (sauf si
# vous les ajoutez avec `extra`), et il ne connaît pas les commandes des autres
# équipes : c'est à vous de faire des hypothèses.

from dataclasses import dataclass, field

from robby.geometry import (
    direction,
    distance,
    in_sector,
    is_number,
    ray_circle,
    ray_sector,
)

SUBSTEPS = 20   # comme le serveur : mêmes résultats au centième près


@dataclass
class SimRobot:
    id: int
    team_id: int
    type: str
    x: float
    y: float
    alive: bool = True
    shield_direction: float | None = None
    carrying_element: bool = False
    penalty: int = 0
    ghost: bool = False          # ennemi supposé (mémoire), pas vu ce tour

    @property
    def pos(self):
        return (self.x, self.y)


@dataclass
class SimResult:
    robots: dict                                   # id -> SimRobot (après le tour)
    deaths: list = field(default_factory=list)     # ids détruits ce tour
    killers: dict = field(default_factory=dict)    # id détruit -> équipe du tireur
    zone_deaths: list = field(default_factory=list)
    shots: list = field(default_factory=list)      # (tireur, cible ou None, bloqué)
    carrier: int | None = None                     # porteur de la batterie
    battery: tuple = (0.0, 0.0)
    captured_by: int | None = None                 # équipe qui a marqué la capture

    def robot(self, robot_id):
        return self.robots.get(robot_id)

    def alive(self, team_id=None):
        return [r for r in self.robots.values()
                if r.alive and (team_id is None or r.team_id == team_id)]


class TurnSimulator:

    def __init__(self, state, extra=()):
        """`extra` : robots supplémentaires (SimRobot), par exemple des ennemis
        vus aux tours précédents et supposés toujours au même endroit."""
        self.state = state
        c = state.config
        self.range = c["destructor_range"]
        self.radius = c["robot_radius"]
        self.shield_radius = c["shield_radius"]
        self.shield_arc = c["shield_arc"]
        self.pickup = c["pickup_radius"]
        self.base_radius = c["base_radius"]
        self.speed = c["move_speed"]
        self.width, self.height = state.map_width, state.map_height
        self.robots = [SimRobot(r.id, r.team_id, r.type, r.x, r.y, r.alive,
                                r.shield_direction, r.carrying_element, r.penalty)
                       for r in state.robots]
        self.robots += list(extra)

    # ------------------------------------------------------------------

    def _copy(self):
        return {r.id: SimRobot(**r.__dict__) for r in self.robots}

    def _shields(self, robots, against_team):
        return [(r.pos, r.shield_direction) for r in robots.values()
                if r.alive and r.type == "D" and r.shield_direction is not None
                and r.team_id != against_team]

    def first_hit(self, robots, shooter, angle, origin=None):
        """(robot touché ou None, bloqué ?) pour un tir depuis `origin`."""
        start = shooter.pos if origin is None else origin
        reach, hit = self.range, None
        for r in robots.values():
            if not r.alive or r.team_id == shooter.team_id:
                continue
            t = ray_circle(start, angle, reach, r.pos, self.radius)
            if t is not None and t < reach:
                reach, hit = t, r
        for center, heading in self._shields(robots, shooter.team_id):
            t = ray_sector(start, angle, reach, center, self.shield_radius,
                           heading, self.shield_arc)
            if t is not None and t <= reach:
                return None, True
        return hit, False

    # ------------------------------------------------------------------

    def run(self, commands_by_team: dict) -> SimResult:
        robots = self._copy()
        st = self.state
        moves, shots, shields = {}, [], {}
        for team_id, commands in commands_by_team.items():
            seen = set()
            for cmd in commands or []:
                r = robots.get(cmd.get("robot_id"))
                if (r is None or r.team_id != team_id or not r.alive or r.penalty
                        or r.id in seen or not is_number(cmd.get("angle"))):
                    continue
                seen.add(r.id)
                angle = cmd["angle"] % 360
                action = cmd.get("action")
                if action == "MOVE":
                    speed = cmd.get("speed")
                    if is_number(speed) and 0 <= speed <= self.speed.get(r.type, 0):
                        dx, dy = direction(angle)
                        moves[r.id] = (dx * speed / SUBSTEPS, dy * speed / SUBSTEPS)
                elif action == "SHOOT" and r.type == "K":
                    shots.append((r, angle))
                elif action == "SHIELD" and r.type == "D":
                    shields[r.id] = angle

        result = SimResult(robots=robots)

        # 1. tirs (positions du début de tour), puis morts
        for shooter, angle in shots:
            hit, blocked = self.first_hit(robots, shooter, angle)
            result.shots.append((shooter.id, hit.id if hit else None, blocked))
            if hit is not None and hit.id not in result.killers:
                result.killers[hit.id] = shooter.team_id
        carrier = st.element.carried_by_id
        battery = st.element.pos
        for rid in result.killers:
            r = robots[rid]
            r.alive = False
            result.deaths.append(rid)
            if r.carrying_element:
                r.carrying_element, carrier, battery = False, None, r.pos

        # 2. déplacements simultanés des survivants
        movers = [rid for rid in moves if robots[rid].alive]
        alive = [r for r in robots.values() if r.alive]
        start = {r.id: r.pos for r in alive}
        pos = dict(start)
        team = {r.id: r.team_id for r in alive}
        enemy_shields = {t: self._shields(robots, t) for t in set(team.values())}
        low_x, high_x = self.radius, self.width - self.radius
        low_y, high_y = self.radius, self.height - self.radius
        gap = 2 * self.radius
        stopped = set()
        first_touch = {}            # radar -> pas où il touche la batterie

        def in_shield(p, t):
            return any(in_sector(p, c, self.shield_radius, a, self.shield_arc)
                       for c, a in enemy_shields[t])

        for step in range(SUBSTEPS):
            proposed = {}
            for rid in movers:
                if rid in stopped:
                    continue
                x, y = pos[rid]
                sx, sy = moves[rid]
                nx = min(max(x + sx, low_x), high_x)
                ny = min(max(y + sy, low_y), high_y)
                if in_shield((nx, ny), team[rid]) and not in_shield((x, y), team[rid]):
                    stopped.add(rid)
                    continue
                proposed[rid] = (nx, ny)
            while True:
                refused = set()
                for rid, new in proposed.items():
                    for o in pos:
                        if team[o] == team[rid]:
                            continue
                        d_new = distance(new, proposed.get(o, pos[o]))
                        if d_new < gap and d_new < distance(pos[rid], pos[o]) - 1e-9:
                            refused.add(rid)
                            break
                if not refused:
                    break
                for rid in refused:
                    del proposed[rid]
                stopped |= refused
            pos.update(proposed)
            if st.phase == 1 and carrier is None:
                for rid in proposed:
                    if robots[rid].type == "R" and rid not in first_touch \
                            and distance(pos[rid], battery) <= self.pickup:
                        first_touch[rid] = step
        for rid, p in pos.items():
            robots[rid].x, robots[rid].y = p

        # 3. batterie : ramassage (le premier arrivé), capture à la base
        if st.phase == 1 and carrier is None and first_touch:
            winner = min(first_touch, key=lambda rid: (first_touch[rid], rid))
            carrier = winner
            robots[winner].carrying_element = True
        if carrier is not None and robots.get(carrier) and robots[carrier].alive:
            c = robots[carrier]
            battery = c.pos
            base = st.base_of(c.team_id)
            if st.phase == 1 and base and distance(c.pos, base) <= self.base_radius:
                result.captured_by = c.team_id
                c.carrying_element, carrier = False, None
        result.carrier, result.battery = carrier, battery

        # boucliers
        for rid, angle in shields.items():
            if robots[rid].alive:
                robots[rid].shield_direction = angle

        # zone : hors de la zone sûre en fin de tour = détruit
        if st.phase == 2:
            for r in robots.values():
                if r.alive and not st.in_zone(r.pos):
                    r.alive = False
                    result.zone_deaths.append(r.id)
                    result.deaths.append(r.id)
        return result
