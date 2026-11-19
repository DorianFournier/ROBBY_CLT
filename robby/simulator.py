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
#   2. déplacements de TOUS les robots qui roulent (cap et vitesse gardés d'un
#      tour à l'autre ; MOVE les change), en petits pas simultanés : un robot
#      s'arrête net avant de toucher un ennemi ou d'entrer dans un bouclier
#      ennemi. Sans commande, un ennemi visible continue donc sur sa lancée :
#      c'est la prévision la plus simple de ce qu'il va faire.
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
    heading: float | None = None   # cap gardé d'un tour à l'autre
    speed: float = 0               # vitesse gardée d'un tour à l'autre
    shield_hp: int = 3             # résistance du bouclier
    shield_cooldown: int = 0       # tours avant de pouvoir le reposer
    shield_quiet: int = 0          # tours sans impact (recharge)

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
    shield_damage: dict = field(default_factory=dict)  # id du D -> points perdus
    shield_breaks: list = field(default_factory=list)  # boucliers brisés
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
        self.shield_break_turns = c.get("shield_break_turns", 4)
        self.shield_max = c.get("shield_hp", 3)
        self.shield_delay = c.get("shield_recharge_delay", 3)
        self.width, self.height = state.map_width, state.map_height
        self.robots = [SimRobot(r.id, r.team_id, r.type, r.x, r.y, r.alive,
                                r.shield_direction, r.carrying_element, r.penalty,
                                heading=getattr(r, "heading", None),
                                speed=getattr(r, "speed", 0) or 0,
                                shield_hp=getattr(r, "shield_hp", 3),
                                shield_cooldown=getattr(r, "shield_cooldown", 0),
                                shield_quiet=getattr(r, "shield_quiet", 0))
                       for r in state.robots]
        self.robots += list(extra)

    # ------------------------------------------------------------------

    def _copy(self):
        return {r.id: SimRobot(**r.__dict__) for r in self.robots}

    def _shields(self, robots, against_team):
        return [(r.pos, r.shield_direction) for r in robots.values()
                if r.alive and r.type == "D" and r.shield_direction is not None
                and r.team_id != against_team]

    def _recharge_shields(self, robots, hit):
        """Fin de tour, comme le serveur : fin de l'indisponibilité (bouclier
        comme neuf), ou +1 point après shield_recharge_delay tours sans impact."""
        for d in robots.values():
            if d.type != "D":
                continue
            if d.shield_cooldown > 0:
                d.shield_cooldown -= 1
                if d.shield_cooldown == 0:
                    d.shield_hp, d.shield_quiet = self.shield_max, 0
                continue
            if d.id not in hit:
                d.shield_quiet += 1
                if (d.shield_quiet >= self.shield_delay
                        and d.shield_hp < self.shield_max):
                    d.shield_hp += 1

    def first_hit(self, robots, shooter, angle, origin=None):
        """(robot touché ou None, bloqué ?) pour un tir depuis `origin`."""
        hit, shield = self.shot_outcome(robots, shooter, angle, origin)
        return hit, shield is not None

    def shot_outcome(self, robots, shooter, angle, origin=None):
        """(robot touché ou None, Défenseur dont le bouclier arrête le tir ou
        None) : le bouclier le plus proche sur la trajectoire, comme le serveur."""
        start = shooter.pos if origin is None else origin
        reach, hit, shield = self.range, None, None
        for r in robots.values():
            if not r.alive or r.team_id == shooter.team_id:
                continue
            t = ray_circle(start, angle, reach, r.pos, self.radius)
            if t is not None and t < reach:
                reach, hit = t, r
        for d in robots.values():
            if not (d.alive and d.type == "D" and d.shield_direction is not None
                    and d.team_id != shooter.team_id):
                continue
            t = ray_sector(start, angle, reach, d.pos, self.shield_radius,
                           d.shield_direction, self.shield_arc)
            if t is not None and t <= reach:
                reach, hit, shield = t, None, d
        return hit, shield

    # ------------------------------------------------------------------

    def run(self, commands_by_team: dict) -> SimResult:
        robots = self._copy()
        st = self.state
        shots, shields = [], {}
        for team_id, commands in commands_by_team.items():
            seen = set()
            for cmd in commands or []:
                r = robots.get(cmd.get("robot_id"))
                if r is None or r.team_id != team_id or not r.alive or r.penalty:
                    continue
                if r.id in seen or not is_number(cmd.get("angle")):
                    r.penalty = 1                  # faute : pénalité (moteurs coupés)
                    continue
                seen.add(r.id)
                angle = cmd["angle"] % 360
                action = cmd.get("action")
                if action == "MOVE":
                    speed = cmd.get("speed")
                    if is_number(speed) and 0 <= speed <= self.speed.get(r.type, 0):
                        r.heading, r.speed = angle, speed   # gardés aux tours suivants
                    else:
                        r.penalty = 1
                elif action == "SHOOT" and r.type == "K":
                    shots.append((r, angle))
                elif action == "SHIELD" and r.type == "D":
                    if r.shield_cooldown == 0:      # brisé : sans effet
                        shields[r.id] = round(angle, 2)   # comme le serveur
                else:
                    r.penalty = 1

        result = SimResult(robots=robots)

        # 1. tirs (positions du début de tour), puis morts
        for shooter, angle in shots:
            hit, shield = self.shot_outcome(robots, shooter, angle)
            result.shots.append((shooter.id, hit.id if hit else None,
                                 shield is not None))
            if hit is not None and hit.id not in result.killers:
                result.killers[hit.id] = shooter.team_id
            if shield is not None:   # le bouclier s'use
                result.shield_damage[shield.id] = result.shield_damage.get(shield.id,
                                                                           0) + 1
        for did, damage in result.shield_damage.items():
            d = robots[did]
            d.shield_hp -= damage
            d.shield_quiet = 0
            if d.shield_hp <= 0:     # brisé : retiré, indisponible quelques tours
                d.shield_hp, d.shield_direction = 0, None
                d.shield_cooldown = self.shield_break_turns + 1   # -1 en fin de tour
                result.shield_breaks.append(did)
        carrier = st.element.carried_by_id
        battery = st.element.pos
        for rid in result.killers:
            r = robots[rid]
            r.alive = False
            result.deaths.append(rid)
            if r.carrying_element:
                r.carrying_element, carrier, battery = False, None, r.pos

        # 2. déplacements simultanés : TOUS les robots qui roulent (cap et
        #    vitesse gardés), sauf les pénalisés, dont les moteurs sont coupés
        for r in robots.values():
            if not r.alive or r.penalty:
                r.speed = 0
        moves = {}
        for r in robots.values():
            if r.speed > 0 and r.heading is not None:
                dx, dy = direction(r.heading)
                moves[r.id] = (dx * r.speed / SUBSTEPS, dy * r.speed / SUBSTEPS)
        movers = list(moves)
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
        for rid in stopped:
            robots[rid].speed = 0          # bloqué : s'arrête net

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
            if robots[rid].alive and robots[rid].shield_cooldown == 0:
                robots[rid].shield_direction = angle
        self._recharge_shields(robots, result.shield_damage)

        # zone : hors de la zone sûre en fin de tour = détruit
        if st.phase == 2:
            for r in robots.values():
                if r.alive and not st.in_zone(r.pos):
                    r.alive = False
                    result.zone_deaths.append(r.id)
                    result.deaths.append(r.id)
        return result
