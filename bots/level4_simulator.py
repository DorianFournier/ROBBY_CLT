# bots/level4_simulator.py
# NIVEAU 4 : « simulateur ».
#
# Au lieu de règles fixes (« si ... alors ... »), ce bot ESSAIE des plans et
# garde le meilleur. À chaque tour :
#
#   1. Plan de départ : celui du tacticien (bot3).
#   2. Pour chaque robot, une liste de commandes candidates (continuer sur
#      sa lancée, s'arrêter, aller vers chaque batterie (Collecteur),
#      escorter le Collecteur (Radar), tirer sur chaque cible, contourner un
#      bouclier, 8 directions, tourner le bouclier vers chaque menace...).
#   3. Chaque plan est JOUÉ dans le simulateur de tour (robby/simulator.py,
#      mêmes règles que le serveur) contre plusieurs hypothèses sur les
#      ennemis : ils restent sur place, ou ils foncent sur nous. Leurs
#      Destructeurs tirent sur la meilleure cible qu'ils ont.
#   4. Chaque résultat reçoit une note (evaluate) : robots perdus et
#      détruits, boucliers usés ou brisés, batterie, danger au tour suivant
#      (un K ennemi pourra-t-il nous toucher ?), occasions de tir, zone,
#      cohésion autour du Radar.
#   5. Recherche « robot par robot » : on améliore la commande d'un robot
#      en gardant les autres, puis on recommence (2 passes).
#
# Nombre de simulations borné (MAX_EVALS) : le temps de réflexion reste
# court, et le bot est reproductible (pas de limite en secondes).

from bots.level3_tactician import TacticianBot
from robby import GameState, move, shield
from robby.geometry import angle_to, direction, distance
from robby.simulator import SimRobot, TurnSimulator
from robby.strategy import Strategy

MEMORY = 3            # tours pendant lesquels un ennemi disparu est supposé là
MAX_EVALS = 260       # plans évalués au plus par tour
PASSES = 2

OWN_VALUE = {"R": 1400, "C": 1000, "K": 1000, "D": 700}   # un robot à nous
ENEMY_VALUE = {"R": 900, "C": 700, "K": 1000, "D": 500}   # détruire un ennemi
CARRIER_BONUS = 600
TARGET_ORDER = {"C": 0, "R": 0, "K": 1, "D": 2}

DANGER = 0.55        # part de la valeur d'un robot qu'un K ennemi menace
OPPORTUNITY = 0.35   # part de la valeur d'un ennemi que notre K menace
ZONE_SOON = 0.5      # hors de la zone du tour prochain
ZONE_LATER = 0.1     # hors de la zone dans 2 tours
COAST = 0.2          # sur sa lancée, finirait hors de la zone au tour suivant
SHIELD_WEAR = 120    # un point retiré à un bouclier ennemi
SHIELD_BREAK = 350   # bouclier ennemi brisé (indisponible plusieurs tours)
# déchèterie (phase 2)
DUMP_BONUS = 0.5     # un ennemi déposé vaut 1,5 fois sa destruction
CAPTIVE_HELD = 0.7   # part de sa valeur que vaut un prisonnier tenu
TO_DUMP = 0.15       # par unité qui reste jusqu'à la déchèterie
GRAB_DANGER = 0.3    # un de nos robots à l'arrêt près d'un Collecteur ennemi
GRAB_DANGER_RANGE = 1800


def captives_held(res, team_id):
    """[(Collecteur, prisonnier)] de l'équipe `team_id` après le tour."""
    held = []
    for c in res.robots.values():
        if c.alive and c.team_id == team_id and c.captive_id in res.robots:
            held.append((c, res.robots[c.captive_id]))
    return held


def grab_threatened(res, team_id):
    """Nos robots libres à l'arrêt, près d'un Collecteur ennemi libre :
    ils pourraient être attrapés au tour suivant."""
    hunters = [c for c in res.robots.values()
               if c.alive and not c.captive and c.type == "C"
               and c.team_id != team_id and c.captive_id is None]
    return [r for r in res.robots.values()
            if r.alive and not r.captive and r.team_id == team_id and r.speed == 0
            and any(distance(r.pos, c.pos) <= GRAB_DANGER_RANGE for c in hunters)]


class SimulatorBot(Strategy):

    def __init__(self):
        self.scout = TacticianBot()   # plan de départ + point de chasse
        self.memory = {}                  # id -> (team, type, pos, tour, bouclier)
        self.evals = 0

    def on_game_start(self, team_id, config):
        self.scout.on_game_start(team_id, config)

    def on_turn_result(self, turn, result):
        self.scout.on_turn_result(turn, result)
        for robot_id in result.get("deaths", []):
            self.memory.pop(robot_id, None)

    # ==================================================================
    # Décision
    # ==================================================================

    def decide(self, state: GameState) -> list[dict]:
        self.state = state
        self.me = state.team_id
        base_plan = {c["robot_id"]: c for c in self.scout.decide(state)}

        # mémoire : ennemis vus récemment mais plus visibles = « fantômes »
        visible = {e.id for e in state.enemies}
        for e in state.enemies:
            self.memory[e.id] = (e.team_id, e.type, e.pos, state.turn,
                                 e.shield_direction)
        self.memory = {i: m for i, m in self.memory.items()
                       if state.turn - m[3] <= MEMORY
                       or any(e.carried_by_id == i for e in state.elements)}
        ghosts = [self.ghost(i, *m) for i, m in self.memory.items() if i not in visible]

        self.ghosts = ghosts
        self.sim = TurnSimulator(state, extra=ghosts)
        self.start = {r.id: r for r in self.sim.robots}
        self.scenarios = self.enemy_scenarios()
        self.hunt = self.scout.hunt_point(state) if state.phase == 2 else None
        if self.hunt is None and not state.my_robots_of_type("R"):
            # aveugles : on cherche vers le prochain cercle
            self.hunt = state.clamp_to_zone(state.safe_center, 3)
        self.evals = 0

        actors = [r for r in state.my_robots if r.can_act]
        # ordre : Destructeurs (tirs), Défenseur, puis Radar
        actors.sort(key=lambda r: "KDRC".index(r.type))
        plan = {r.id: base_plan.get(r.id) for r in actors}
        candidates = {r.id: self.candidates(r, base_plan.get(r.id)) for r in actors}

        best = self.score(plan)
        for _ in range(PASSES):
            improved = False
            for robot in actors:
                for cand in candidates[robot.id]:
                    if self.evals >= MAX_EVALS:
                        break
                    if cand == plan[robot.id]:
                        continue
                    trial = {**plan, robot.id: cand}
                    value = self.score(trial)
                    if value > best + 1e-6:
                        best, plan, improved = value, trial, True
            if not improved or self.evals >= MAX_EVALS:
                break
        self.best_score = best
        return [c for c in plan.values() if c]

    def ghost(self, robot_id, team_id, rtype, pos, seen_turn, shield_angle):
        """Ennemi disparu, supposé immobile... sauf le porteur de la batterie,
        qui rentre forcément vers sa base : on prédit où il est."""
        st = self.state
        carrying = st.phase == 1 and any(e.carried_by_id == robot_id
                                         for e in st.elements)
        if carrying:
            base = st.base_of(team_id)
            if base is not None:
                left = distance(pos, base)
                walked = min(left, st.config["move_speed"]["C"]
                             * (st.turn - seen_turn))
                if left > 1:
                    pos = (pos[0] + (base[0] - pos[0]) * walked / left,
                           pos[1] + (base[1] - pos[1]) * walked / left)
        return SimRobot(robot_id, team_id, rtype, pos[0], pos[1],
                        shield_direction=shield_angle, carrying_element=carrying,
                        ghost=True)

    # ==================================================================
    # Hypothèses sur les ennemis
    # ==================================================================

    def enemy_scenarios(self):
        """Commandes supposées des autres équipes : [{team: [cmds]}, ...]."""
        robots = {r.id: r for r in self.sim.robots}
        mine = [r for r in robots.values() if r.team_id == self.me and r.alive]
        enemies = [r for r in robots.values() if r.team_id != self.me and r.alive]
        if not enemies or not mine:
            return [{}]

        shots = {}
        for k in enemies:
            if k.type != "K" or k.penalty:
                continue
            target = self.best_target(robots, k, mine)
            if target is not None:
                shots[k.id] = {"robot_id": k.id, "action": "SHOOT",
                               "angle": angle_to(k.pos, target.pos)}

        hold, rush = {}, {}
        for e in enemies:
            team_cmds = hold.setdefault(e.team_id, []), rush.setdefault(e.team_id, [])
            if e.id in shots:
                team_cmds[0].append(shots[e.id])
                team_cmds[1].append(shots[e.id])
                continue
            if e.penalty:
                continue
            near = min(mine, key=lambda r: distance(r.pos, e.pos))
            stop = 2600 if e.type == "K" else 1500
            gap = distance(e.pos, near.pos) - stop
            if gap > 1:
                speed = min(self.state.config["move_speed"][e.type], gap)
                team_cmds[1].append({"robot_id": e.id, "action": "MOVE",
                                     "angle": angle_to(e.pos, near.pos),
                                     "speed": speed})
        return [hold, rush]

    def best_target(self, robots, shooter, targets, origin=None):
        """Robot de `targets` que `shooter` toucherait vraiment (le plus
        intéressant), en visant chacun depuis `origin`."""
        start = shooter.pos if origin is None else origin
        best = None
        for t in targets:
            if distance(start, t.pos) - self.sim.radius > self.sim.range:
                continue
            angle = angle_to(start, t.pos)
            if angle is None:
                continue
            hit, _ = self.sim.first_hit(robots, shooter, angle, origin=start)
            if hit is not None and hit.alive and hit.team_id != shooter.team_id:
                if best is None or (not hit.carrying_element, TARGET_ORDER[hit.type]) \
                        < (not best.carrying_element, TARGET_ORDER[best.type]):
                    best = hit
        return best

    # ==================================================================
    # Candidats
    # ==================================================================

    def candidates(self, robot, base):
        st = self.state
        # None : aucune commande, le robot continue sur sa lancée
        cands = [None, base, st.stop(robot)]
        for k in range(8):       # 8 directions
            cands.append(move(robot, angle=45 * k, speed=st.max_speed(robot)))
            if robot.type != "R":
                cands.append(move(robot, angle=45 * k, speed=st.max_speed(robot) / 2))
        threats = [r for r in self.sim.robots if r.team_id != self.me and r.alive]
        radar = next(iter(st.my_robots_of_type("R")), None)

        collector = next(iter(st.my_robots_of_type("C")), None)

        if robot.type == "C":
            if st.phase == 1 and robot.carrying_element:
                cands.append(st.move_towards(robot, st.my_base))
            if st.phase == 1:
                for battery in st.free_batteries:
                    cands.append(st.move_towards(robot, battery.pos))
            for d in st.my_robots_of_type("D") + st.my_robots_of_type("R"):
                cands.append(st.move_towards(robot, d, stop_at=700))
            if st.dump:                    # phase 2 : la déchèterie
                if robot.captive_id is not None:
                    cands.append(st.move_towards(robot, st.dump_center))
                else:
                    for e in st.enemies:
                        if e.speed == 0 and e.captive_id is None and \
                                robot.distance_to(e) <= 4000:
                            cands.append(st.move_towards(robot, e))
        elif robot.type == "R":
            if st.phase == 1 and collector is not None:   # escorter le Collecteur
                cands.append(st.move_towards(robot, collector, stop_at=1200))
            if self.hunt:
                cands.append(st.move_towards(robot, self.hunt))
            for d in st.my_robots_of_type("D") + st.my_robots_of_type("K"):
                cands.append(st.move_towards(robot, d, stop_at=600))
        elif robot.type == "K":
            for e in st.targets_in_range(robot) + st.shielded_targets(robot):
                cands.append(st.shoot_at(robot, e))   # derrière un bouclier : l'user
            for g in self.ghosts:
                if g.carrying_element:   # intercepter le porteur
                    cands.append(st.move_towards(robot, g.pos, stop_at=2000))
            for g in self.ghosts:    # tir « à l'aveugle » sur un ennemi disparu
                if (distance(robot.pos, g.pos) - st.robot_radius
                        <= st.config["destructor_range"]
                        and st.aim(robot, g) is not None):   # pas sur nous-mêmes
                    cands.append(st.shoot_at(robot, g))
            for e in st.enemies:
                spot = st.firing_spot(robot, e)
                if spot:
                    cands.append(st.move_towards(robot, spot))
            for e in threats:
                cands.append(st.move_towards(robot, st.clamp_to_zone(e.pos, 1),
                                             stop_at=2700))
                cands.append(st.move_away(robot, e.pos))
            if radar:
                cands.append(st.move_towards(robot, radar, stop_at=1000))
        else:   # Défenseur
            for e in threats:
                a = angle_to(robot.pos, e.pos)
                if a is not None:
                    cands.append(shield(robot, angle=a))
                if radar is not None:
                    a = angle_to(radar.pos, e.pos)
                    if a is not None:
                        dx, dy = direction(a)
                        spot = st.clamp_to_zone((radar.x + dx * 700,
                                                 radar.y + dy * 700), 1)
                        cands.append(st.move_towards(robot, spot))
            if radar:
                cands.append(st.move_towards(robot, radar, stop_at=700))
        if self.hunt and robot.type not in "RC":
            cands.append(st.move_towards(robot, self.hunt))
        # sans doublons, en gardant l'ordre
        unique = []
        for c in cands:
            if c not in unique:
                unique.append(c)
        return unique

    # ==================================================================
    # Évaluation
    # ==================================================================

    def score(self, plan):
        """Note d'un plan : moyenne et pire cas sur les hypothèses ennemies."""
        mine = [c for c in plan.values() if c]
        values = []
        for scenario in self.scenarios:
            self.evals += 1
            result = self.sim.run({**scenario, self.me: mine})
            values.append(self.evaluate(result))
        return 0.5 * sum(values) / len(values) + 0.5 * min(values)

    def evaluate(self, res) -> float:
        st, me = self.state, self.me
        value = 0.0
        mine = res.alive(me)
        enemies = [r for r in res.alive() if r.team_id != me]

        # --- 1. pertes et destructions de ce tour
        for rid in res.deaths:
            r, before = res.robots[rid], self.start[rid]
            if r.team_id == me:
                value -= OWN_VALUE[r.type]
            elif rid in res.killers and res.killers[rid] == me:
                gain = ENEMY_VALUE[r.type] + (CARRIER_BONUS if before.carrying_element
                                              else 0)
                value += gain * (0.5 if r.ghost else 1.0)
        for _, rid, _ in res.dumps:          # déposé à la déchèterie : 1,5 fois
            if res.robots[rid].team_id != me and res.killers.get(rid) == me:
                value += DUMP_BONUS * ENEMY_VALUE[res.robots[rid].type]

        # --- 1 ter. déchèterie : prisonniers tenus (par nous, ou par eux)
        if st.dump:
            center = st.dump_center
            for c, captive in captives_held(res, me):
                value += CAPTIVE_HELD * ENEMY_VALUE[captive.type]
                value -= TO_DUMP * distance(c.pos, center)
            for r in res.robots.values():
                if r.alive and r.team_id == me and r.captive:
                    value -= CAPTIVE_HELD * OWN_VALUE[r.type]
            for r in grab_threatened(res, me):
                value -= GRAB_DANGER * OWN_VALUE[r.type]

        # --- 1 bis. boucliers usés ou brisés (anti-blocage)
        for did, damage in res.shield_damage.items():
            sign = -1 if res.robots[did].team_id == me else 1
            value += sign * SHIELD_WEAR * damage
            if did in res.shield_breaks:
                value += sign * SHIELD_BREAK

        # --- 2. batteries (phase 1)
        if st.phase == 1:
            if res.captured_by == me:
                value += 5000
            elif res.captured_by is not None:
                value -= 5000
            porteurs = [res.robots.get(rid) for rid in res.carriers.values()]
            miens = [c for c in porteurs if c is not None and c.team_id == me]
            # porter une batterie vaut toujours mieux que la laisser :
            # 2500 de bonus, moins 0.15 par unité qui reste jusqu'à la base
            for c in miens:
                value += 2500 - 0.15 * distance(c.pos, st.my_base)
            value -= 1500 * (len(porteurs) - len(miens))   # porteurs ennemis
            collecteurs = [r for r in mine if r.type == "C" and not r.carrying_element]
            if collecteurs and res.free_batteries and not miens:
                value -= 0.3 * min(distance(r.pos, b) for r in collecteurs
                                   for b in res.free_batteries)

        # --- 3. tour suivant : danger (K ennemis) et occasions (nos K)
        for k in enemies:
            if k.type == "K":
                hit = self.best_target(res.robots, k, mine)
                if hit is not None:
                    value -= DANGER * OWN_VALUE[hit.type]
        for k in mine:
            if k.type == "K":
                hit = self.best_target(res.robots, k, enemies)
                if hit is not None:
                    gain = ENEMY_VALUE[hit.type] + (CARRIER_BONUS
                                                    if hit.carrying_element else 0)
                    value += OPPORTUNITY * gain

        # --- 4. zone qui rétrécit (et l'élan : sans nouvelle commande, le
        #        robot continue sur sa lancée au tour suivant)
        for r in mine:
            if not st.in_zone(r.pos, 1, inset=st.robot_radius):
                value -= ZONE_SOON * OWN_VALUE[r.type]
            elif not st.in_zone(r.pos, 2, inset=st.robot_radius):
                value -= ZONE_LATER * OWN_VALUE[r.type]
            if r.speed > 0 and r.heading is not None:
                coast = st.destination(r, r.heading, r.speed)
                if not st.in_zone(coast, 1, inset=st.robot_radius):
                    value -= COAST * OWN_VALUE[r.type]

        # --- 5. cohésion : sans Radar proche, un K est aveugle. En phase 1,
        #        le Collecteur part chercher les batteries : c'est au Radar de
        #        rester près de lui (on voit qui vient l'intercepter).
        radar = next((r for r in mine if r.type == "R"), None)
        if radar is not None:
            reach = st.config["radar_range"]
            for r in mine:
                if r is radar:
                    continue
                if r.type == "C" and st.phase == 1:
                    value -= 0.08 * max(0.0, distance(r.pos, radar.pos) - 2000)
                else:
                    value -= 0.08 * max(0.0, distance(r.pos, radar.pos) - 0.8 * reach)
            # garder le contact avec les ennemis connus
            value += 60 * sum(1 for e in enemies
                              if distance(e.pos, radar.pos) <= reach)
            if self.hunt and not enemies:
                value -= 0.15 * distance(radar.pos, self.hunt)
        elif self.hunt and not enemies:
            # plus de Radar : on ne voit rien, toute l'équipe part en chasse
            for r in mine:
                value -= 0.1 * distance(r.pos, self.hunt)
        return value
