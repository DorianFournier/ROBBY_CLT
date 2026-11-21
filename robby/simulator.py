# robby/simulator.py
# Simulateur d'UN tour, côté client.
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
#   3. batterie (ramassage, capture) ; en phase 2, déchèterie (dépôts, puis
#      prises de prisonniers) ; boucliers, zone
#
# Limites : les ennemis invisibles n'existent pas pour le simulateur (sauf si
# vous les ajoutez avec `extra`), et il ne connaît pas les commandes des autres
# équipes : c'est à vous de faire des hypothèses.

from dataclasses import dataclass, field

from robby.geometry import (
    angle_diff,
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
    captive_id: int | None = None  # prisonnier porté (Collecteur)
    captured_by: int | None = None  # Collecteur qui le porte (prisonnier)

    @property
    def pos(self):
        return (self.x, self.y)

    @property
    def captive(self):
        return self.captured_by is not None


@dataclass
class SimResult:
    robots: dict                                   # id -> SimRobot (après le tour)
    deaths: list = field(default_factory=list)     # ids détruits ce tour
    killers: dict = field(default_factory=dict)    # id détruit -> équipe du tireur
    zone_deaths: list = field(default_factory=list)
    shots: list = field(default_factory=list)      # (tireur, cible ou None, bloqué)
    shield_damage: dict = field(default_factory=dict)  # id du D -> points perdus
    shield_breaks: list = field(default_factory=list)  # boucliers brisés
    # batteries (phase 1). Avec plusieurs batteries, `carrier` est notre
    # porteur s'il y en a un (sinon un porteur ennemi), `battery` la première
    # batterie posée au sol, et `captured_by` notre équipe si elle a marqué
    # une capture ce tour (sinon une équipe ennemie qui en a marqué une).
    carrier: int | None = None
    battery: tuple = (0.0, 0.0)
    captured_by: int | None = None
    carriers: dict = field(default_factory=dict)   # batterie -> porteur
    free_batteries: list = field(default_factory=list)   # positions au sol
    captures: list = field(default_factory=list)   # équipes qui ont capturé
    # déchèterie (phase 2) : (Collecteur, robot pris) et (Collecteur, robot
    # détruit, points)
    grabs: list = field(default_factory=list)
    dumps: list = field(default_factory=list)

    def robot(self, robot_id):
        return self.robots.get(robot_id)

    def alive(self, team_id=None):
        return [r for r in self.robots.values()
                if r.alive and not r.captive
                and (team_id is None or r.team_id == team_id)]


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
                                shield_quiet=getattr(r, "shield_quiet", 0),
                                captive_id=getattr(r, "captive_id", None),
                                captured_by=getattr(r, "captured_by", None))
                       for r in state.robots]
        c = state.config
        self.dump_enabled = c.get("dump_enabled", False)
        self.grab_radius = c.get("grab_radius", 700)
        self.carry_speed = c.get("carry_speed", 600)
        self.dump_points = c.get("dump_points", {})
        self.cross_angle = c.get("cross_angle", 90)
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
            if not r.alive or r.team_id == shooter.team_id or r.captive:
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
    # Déchèterie (phase 2), comme le serveur
    # ------------------------------------------------------------------

    @staticmethod
    def _destroy(robots, r):
        """Détruit `r` : son prisonnier est libéré sur place ; s'il était
        prisonnier, son Collecteur est déchargé."""
        r.alive = False
        captive = robots.get(r.captive_id) if r.captive_id is not None else None
        r.captive_id = None
        if captive is not None:
            captive.captured_by = None
            captive.x, captive.y, captive.speed = r.x, r.y, 0
        carrier = robots.get(r.captured_by) if r.captured_by is not None else None
        r.captured_by = None
        if carrier is not None:
            carrier.captive_id = None

    def _dump_and_grab(self, robots, result, moved=()):
        st = self.state
        for r in robots.values():
            if r.alive and r.captive and r.captured_by in robots:
                c = robots[r.captured_by]
                r.x, r.y = c.x, c.y
        center = tuple(st.zone["center"])
        dump_radius = st.dump["radius"] if st.dump else 0
        for c in list(robots.values()):
            if not c.alive or c.captive_id is None or c.captive_id not in robots:
                continue
            if distance(c.pos, center) > dump_radius:
                continue
            captive = robots[c.captive_id]
            points = self.dump_points.get(captive.type, 0)
            self._destroy(robots, captive)
            result.deaths.append(captive.id)
            result.killers[captive.id] = c.team_id
            result.dumps.append((c.id, captive.id, points))
        free = [r for r in robots.values() if r.alive and not r.captive]
        choice = {}
        for c in free:
            if c.type != "C" or c.captive_id is not None:
                continue
            best = None
            for t in free:
                if t.team_id == c.team_id or t.speed != 0 or t.captive_id is not None:
                    continue
                d = distance(c.pos, t.pos)
                if d <= self.grab_radius and (best is None or (d, t.id) < best[:2]):
                    best = (d, t.id, t)
            if best is not None:
                choice[c.id] = best
        by_target = {}
        for cid, (d, tid, _) in choice.items():
            if tid in choice and choice[tid][1] == cid:
                # prise mutuelle : seul celui qui est venu au contact prend
                if not (cid in moved and tid not in moved):
                    continue
            by_target.setdefault(tid, []).append((d, cid))
        for tid, takers in by_target.items():
            takers.sort(key=lambda x: x[0])
            if len(takers) > 1 and takers[1][0] - takers[0][0] < 1e-9:
                continue
            c, t = robots[takers[0][1]], robots[tid]
            c.captive_id, t.captured_by = t.id, c.id
            t.x, t.y, t.speed, t.shield_direction = c.x, c.y, 0, None
            c.speed = min(c.speed, self.carry_speed)
            result.grabs.append((c.id, t.id))

    # ------------------------------------------------------------------

    def run(self, commands_by_team: dict) -> SimResult:
        robots = self._copy()
        st = self.state
        shots, shields = [], {}
        for team_id, commands in commands_by_team.items():
            seen = set()
            for cmd in commands or []:
                r = robots.get(cmd.get("robot_id"))
                if (r is None or r.team_id != team_id or not r.alive or r.penalty
                        or r.captive):
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

        # 1. tirs (positions du début de tour), puis morts. Plusieurs équipes
        #    touchent le même robot : le tireur le plus proche marque ; à
        #    égalité parfaite, les points sont partagés (équipes en tuple)
        hits = {}
        for shooter, angle in shots:
            hit, shield = self.shot_outcome(robots, shooter, angle)
            result.shots.append((shooter.id, hit.id if hit else None,
                                 shield is not None))
            if hit is not None:
                t = ray_circle(shooter.pos, angle, self.range, hit.pos, self.radius)
                hits.setdefault(hit.id, []).append((t or 0.0, shooter.team_id))
            if shield is not None:   # le bouclier s'use
                result.shield_damage[shield.id] = result.shield_damage.get(shield.id,
                                                                           0) + 1
        for hid, list_ in hits.items():
            best = min(d for d, _ in list_)
            teams = sorted({t for d, t in list_ if d - best < 1e-6})
            result.killers[hid] = teams[0] if len(teams) == 1 else tuple(teams)
        for did, damage in result.shield_damage.items():
            d = robots[did]
            d.shield_hp -= damage
            d.shield_quiet = 0
            if d.shield_hp <= 0:     # brisé : retiré, indisponible quelques tours
                d.shield_hp, d.shield_direction = 0, None
                d.shield_cooldown = self.shield_break_turns + 1   # -1 en fin de tour
                result.shield_breaks.append(did)
        # batteries : [id, position, porteur, présente]
        batteries = [[e.id, e.pos, e.carried_by_id, getattr(e, "present", True)]
                     for e in st.elements]
        for rid in result.killers:
            r = robots[rid]
            self._destroy(robots, r)
            result.deaths.append(rid)
            if r.carrying_element:          # la batterie tombe là où il était
                r.carrying_element = False
                for b in batteries:
                    if b[2] == rid:
                        b[1], b[2] = r.pos, None

        # 2. déplacements simultanés : TOUS les robots qui roulent (cap et
        #    vitesse gardés), sauf les pénalisés, dont les moteurs sont coupés
        for r in robots.values():
            if not r.alive or r.penalty or r.captive:
                r.speed = 0
            elif r.captive_id is not None:      # Collecteur chargé : lent
                r.speed = min(r.speed, self.carry_speed)
        moves = {}
        for r in robots.values():
            if r.speed > 0 and r.heading is not None:
                dx, dy = direction(r.heading)
                moves[r.id] = (dx * r.speed / SUBSTEPS, dy * r.speed / SUBSTEPS)
        movers = list(moves)
        alive = [r for r in robots.values() if r.alive and not r.captive]
        start = {r.id: r.pos for r in alive}
        pos = dict(start)
        team = {r.id: r.team_id for r in alive}
        # zones neutres (bases, déchèterie) : on s'y traverse, les boucliers
        # n'y bloquent pas, et le bouclier d'un Défenseur qui s'y trouve ne
        # bloque personne
        zones = st.neutral_zones()

        def neutre(p):
            return any(distance(p, c) <= r for c, r in zones)

        enemy_shields = {t: [sh for sh in self._shields(robots, t) if not neutre(sh[0])]
                         for t in set(team.values())}
        low_x, high_x = self.radius, self.width - self.radius
        low_y, high_y = self.radius, self.height - self.radius
        gap = 2 * self.radius
        stopped = set()
        touches = {}                # (radar, batterie) -> premier pas au contact
        libres = ([b for b in batteries if b[2] is None and b[3]]
                  if st.phase == 1 else [])

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
                if in_shield((nx, ny), team[rid]) and not in_shield((x, y), team[rid]) \
                        and not neutre((nx, ny)):
                    stopped.add(rid)
                    continue
                proposed[rid] = (nx, ny)
            while True:
                refused = set()
                for rid, new in proposed.items():
                    for o in pos:
                        if team[o] == team[rid]:
                            continue
                        other = proposed.get(o, pos[o])
                        if neutre(new) or neutre(other):
                            continue
                        if o in proposed:
                            # comme le serveur : deux robots qui roulent ne se
                            # heurtent que s'ils se suivent ou arrivent de face
                            ecart = angle_diff(robots[rid].heading, robots[o].heading)
                            if 90 < ecart < 180 - self.cross_angle:
                                continue
                        d_new = distance(new, other)
                        d_old = distance(pos[rid], pos[o])
                        # comme le serveur : refusé seulement en avançant
                        # vers l'autre (celui qui s'éloigne n'est pas arrêté
                        # par un poursuivant plus rapide)
                        if d_new < gap and d_new < d_old - 1e-9 \
                                and distance(new, pos[o]) < d_old - 1e-9:
                            refused.add(rid)
                            break
                if not refused:
                    break
                for rid in refused:
                    del proposed[rid]
                stopped |= refused
            pos.update(proposed)
            for rid in proposed:
                if robots[rid].type != "C" or robots[rid].carrying_element:
                    continue
                # positions arrondies au dixième, comme le trajet du serveur
                arrondi = (round(pos[rid][0], 1), round(pos[rid][1], 1))
                for b in libres:
                    d = distance(arrondi, b[1])
                    if (rid, b[0]) not in touches and d <= self.pickup:
                        touches[(rid, b[0])] = (step + 1, d)
        for rid, p in pos.items():
            # arrondi au dixième, comme le serveur (une capture se joue à 0.1 près)
            robots[rid].x, robots[rid].y = round(p[0], 1), round(p[1], 1)
        for rid in stopped:
            robots[rid].speed = 0          # bloqué : s'arrête net

        # 3. batteries : ramassage (pour chaque batterie, le premier
        #    Collecteur arrivé ; il n'en prend qu'une), puis capture à la base
        for b in libres:            # Collecteur qui roule, déjà au contact : pas 0
            for rid in movers:
                r = robots[rid]
                d = distance(start[rid], b[1])
                if r.type == "C" and r.alive and not r.carrying_element \
                        and d <= self.pickup:
                    touches[(rid, b[0])] = (0, d)
        # comme le serveur : le premier arrivé, puis le plus proche ; égalité
        # parfaite = batterie disputée, personne ne la prend ce tour-ci
        par_batterie = {}
        for (rid, bid), (step, d) in touches.items():
            par_batterie.setdefault(bid, []).append((step, d, rid))
        pris, radars = {}, set()
        for bid in sorted(par_batterie, key=lambda b: (min(par_batterie[b])[:2], b)):
            cands = sorted(t for t in par_batterie[bid] if t[2] not in radars)
            if not cands:
                continue
            if len(cands) > 1 and cands[1][0] == cands[0][0] \
                    and cands[1][1] - cands[0][1] < 1.0:
                continue
            pris[bid] = cands[0][2]
            radars.add(cands[0][2])
        for b in batteries:
            if b[0] in pris:
                b[2] = pris[b[0]]
                robots[b[2]].carrying_element = True
        me = st.team_id
        for b in batteries:
            c = robots.get(b[2]) if b[2] is not None else None
            if c is None or not c.alive:
                continue
            b[1] = c.pos
            base = st.base_of(c.team_id)
            if st.phase == 1 and base and distance(c.pos, base) <= self.base_radius:
                result.captures.append(c.team_id)
                c.carrying_element, b[2], b[3] = False, None, False
        result.carriers = {b[0]: b[2] for b in batteries if b[2] is not None}
        result.free_batteries = [b[1] for b in batteries if b[2] is None and b[3]]
        porteurs = list(result.carriers.values())   # un porteur peut être invisible
        mien = [rid for rid in porteurs if rid in robots and robots[rid].team_id == me]
        result.carrier = (mien or porteurs or [None])[0]
        position = [b[1] for b in batteries if b[2] == result.carrier]
        result.battery = (result.free_batteries[0] if result.free_batteries
                          else position[0] if position else st.element.pos)
        if result.captures:
            result.captured_by = me if me in result.captures else result.captures[0]

        # déchèterie (phase 2) : les prisonniers suivent leur Collecteur ;
        # dépôts, puis prises
        if st.phase == 2 and self.dump_enabled:
            moved = {rid for rid, p in start.items()
                     if distance(p, robots[rid].pos) > 0.05}
            self._dump_and_grab(robots, result, moved)

        # boucliers
        for rid, angle in shields.items():
            if robots[rid].alive and robots[rid].shield_cooldown == 0 \
                    and not robots[rid].captive:
                robots[rid].shield_direction = angle
        self._recharge_shields(robots, result.shield_damage)

        # zone : hors de la zone sûre en fin de tour = détruit
        if st.phase == 2:
            for r in robots.values():
                if r.alive and not st.in_zone(r.pos):
                    self._destroy(robots, r)
                    result.zone_deaths.append(r.id)
                    result.deaths.append(r.id)
        return result
