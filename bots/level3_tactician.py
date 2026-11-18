# bots/level3_tactician.py
# NIVEAU 3 — « tacticien » : le groupe se déplace ensemble autour du Radar.
#
#   Mémoire    : retient la dernière position connue des ennemis.
#   Défenseur  : garde du corps. Se place entre le Radar et la menace
#                principale, bouclier tourné vers elle (un tir ennemi vers le
#                Radar doit alors traverser le bouclier).
#   Radar      : va chercher l'élément puis rentre, mais attend son garde du
#                corps et recule si un Destructeur ennemi est trop proche
#                alors qu'il n'est pas protégé. En phase 2, il tient sa
#                position : l'ennemi qui approche est vu avant de nous voir.
#   Destructeur: tire en priorité sur ce qui menace le Radar, sinon sur la
#                cible qui rapporte le plus. Sans cible, il reste sur un flanc
#                du Radar (dans sa zone de vision) au lieu de partir seul et
#                aveugle.
#
# Les ennemis ne sont visibles que près de VOTRE Radar : un Destructeur qui
# s'en éloigne ne voit plus rien et ne peut plus tirer. Tout le jeu de ce bot
# repose sur cette idée.

from robby import GameState, move, shield, shoot
from robby.game_state import Position, Robot, distance, step
from robby.strategy import Strategy

MEMORY_TURNS = 6            # durée de vie d'un ennemi « vu récemment »
VALUE = {"R": 750, "D": 500, "K": 250}


def clamp(state: GameState, pos: Position) -> Position:
    return (min(max(pos[0], 0), state.map_width - 1),
            min(max(pos[1], 0), state.map_height - 1))


def axis_unit(src: Position, dst: Position) -> tuple[int, int]:
    """Vecteur unitaire (axe dominant) de src vers dst."""
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    if abs(dx) >= abs(dy):
        return (1 if dx > 0 else -1, 0)
    return (0, 1 if dy > 0 else -1)


SHIELD_OF = {(1, 0): "SR", (-1, 0): "SL", (0, 1): "SD", (0, -1): "SU"}


class TacticianBot(Strategy):

    def __init__(self):
        self.memory: dict[int, dict] = {}  # id -> {pos, type, team, turn}

    # ------------------------------------------------------------------
    # Mémoire
    # ------------------------------------------------------------------

    def on_turn_result(self, turn, result):
        for dead_id in result.get("deaths", []):
            self.memory.pop(dead_id, None)

    def remember(self, state: GameState):
        for e in state.enemies:
            self.memory[e.id] = {"pos": e.pos, "type": e.type, "team": e.team_id,
                                 "turn": state.turn,
                                 "carrying": e.carrying_element,
                                 "shield": state.shield_cells_of(e)}
        for eid in [i for i, m in self.memory.items()
                    if state.turn - m["turn"] > MEMORY_TURNS]:
            del self.memory[eid]

    def remembered_shields(self, state: GameState) -> set:
        """Boucliers ennemis vus récemment mais plus visibles (brouillard)."""
        visible = {e.id for e in state.enemies}
        cells = set()
        for eid, m in self.memory.items():
            if eid not in visible and m["type"] == "D":
                cells.update(m["shield"])
        return cells

    def known_enemies(self, of_type=None):
        return [m for m in self.memory.values()
                if of_type is None or m["type"] == of_type]

    # ------------------------------------------------------------------
    # Tour
    # ------------------------------------------------------------------

    def decide(self, state: GameState) -> list[dict]:
        self.remember(state)
        self.avoid = self.remembered_shields(state)
        mine = {r.type: r for r in state.my_robots}  # un robot par type (+ K2)
        killers = state.my_robots_of_type("K")
        radar, defender = mine.get("R"), mine.get("D")

        commands, taken = [], set()  # taken : cases d'arrivée déjà prises

        anchor = radar.pos if radar else (defender.pos if defender else None)
        threat = self.main_threat(state, anchor) if anchor else None

        # 1. Radar (il décide où va le groupe)
        radar_dest = radar.pos if radar else None
        if radar and radar.can_act:
            cmd, radar_dest = self.play_radar(state, radar, defender, threat)
            if cmd:
                commands.append(cmd)
        if radar_dest:
            taken.add(radar_dest)

        # 2. Défenseur : garde du corps du Radar
        if defender and defender.can_act:
            cmd = self.play_defender(state, defender, radar_dest, threat, taken)
            if cmd:
                commands.append(cmd)

        # 3. Destructeurs
        for i, k in enumerate(killers):
            if k.can_act:
                cmd = self.play_destructor(state, k, radar_dest, threat, taken, i)
                if cmd:
                    commands.append(cmd)
        return commands

    # ------------------------------------------------------------------
    # Menace / objectif
    # ------------------------------------------------------------------

    def main_threat(self, state, anchor) -> Position | None:
        """Position de la menace principale pour le groupe (K ennemi d'abord)."""
        ks = self.known_enemies("K")
        candidates = ks or self.known_enemies()
        if candidates:
            return min(candidates, key=lambda m: distance(m["pos"], anchor))["pos"]
        return None

    def group_goal(self, state, radar) -> Position:
        """Où le groupe doit aller."""
        if state.phase == 1:
            if radar and radar.carrying_element:
                return state.my_base
            carrier = state.element.carried_by_id
            if state.element.is_free:
                return state.element.pos
            known = [m for m in self.memory.values() if m["carrying"]]
            if known:
                return known[0]["pos"]
            if carrier is None:
                return state.element.pos
            return state.element.pos
        # Phase 2 : aller vers l'ennemi le plus proche connu, sinon une base ennemie
        known = self.known_enemies()
        origin = radar.pos if radar else state.my_base
        if known:
            return min(known, key=lambda m: distance(m["pos"], origin))["pos"]
        bases = [state.base_of(int(t)) for t in state.config.get("teams", {})
                 if int(t) != state.team_id]
        bases = [b for b in bases if b]
        if bases:
            return min(bases, key=lambda b: distance(b, origin))
        return (state.map_width // 2, state.map_height // 2)

    # ------------------------------------------------------------------
    # Radar
    # ------------------------------------------------------------------

    def play_radar(self, state, radar, defender, threat):
        goal = self.group_goal(state, radar)
        guarded = defender is not None and defender.distance_to(radar) <= 1
        danger = [e for e in state.enemies
                  if e.type == "K" and radar.distance_to(e) <= 4]

        # Exposé sans garde : reculer vers la base (sauf s'il porte l'élément,
        # auquel cas rentrer EST la retraite)
        if danger and not guarded and not radar.carrying_element:
            k = state.nearest(radar, danger)
            options = [d for d in state.possible_moves(radar)
                       if step(radar.pos, d) not in self.avoid]
            if options:
                best = max(options, key=lambda d: (
                    distance(step(radar.pos, d), k.pos),
                    -distance(step(radar.pos, d), state.my_base)))
                if distance(step(radar.pos, best), k.pos) > radar.distance_to(k):
                    return move(radar, best), step(radar.pos, best)
            return None, radar.pos

        # Phase 2 : tenir la position. Avec le brouillard de guerre, celui qui
        # attend voit l'autre arriver en premier : l'ennemi qui approche entre
        # dans la vision de notre Radar avant que nous soyons dans la sienne.
        if state.phase == 2:
            return None, radar.pos

        # Attendre le garde du corps s'il est loin (sauf porteur de l'élément)
        if defender is not None and defender.distance_to(radar) > 2 \
                and not radar.carrying_element:
            return None, radar.pos

        path = state.path_towards(radar, goal, self.avoid)
        if not path:
            return None, radar.pos
        dest = radar.pos
        for d in path:
            dest = step(dest, d)
        return move(radar, *path), dest

    # ------------------------------------------------------------------
    # Défenseur
    # ------------------------------------------------------------------

    def guard_cell(self, state, radar_dest, threat) -> Position:
        towards = threat or (state.map_width // 2, state.map_height // 2)
        if towards == radar_dest:
            towards = state.my_base
        ux, uy = axis_unit(radar_dest, towards)
        return clamp(state, (radar_dest[0] + ux, radar_dest[1] + uy))

    def play_defender(self, state, d, radar_dest, threat, taken):
        if radar_dest is None:  # plus de Radar : se battre aux côtés des K
            enemy = state.nearest(d, state.enemies)
            if enemy:
                wanted = SHIELD_OF[axis_unit(d.pos, enemy.pos)]
                if wanted != d.shield_direction:
                    return shield(d, wanted)
            return None

        cell = self.guard_cell(state, radar_dest, threat)
        towards = threat or (state.map_width // 2, state.map_height // 2)
        wanted = SHIELD_OF[axis_unit(d.pos if d.pos == cell else cell, towards)] \
            if towards != cell else d.shield_direction

        if d.pos == cell or (d.distance_to(cell) <= 1 and cell in taken):
            taken.add(d.pos)
            if wanted and wanted != d.shield_direction:
                return shield(d, wanted)
            return None

        path = state.path_towards(d, cell, self.avoid)
        path = self.avoid_taken(d, path, taken)
        if not path:
            taken.add(d.pos)
            if wanted and wanted != d.shield_direction:
                return shield(d, wanted)
            return None
        return move(d, *path)

    # ------------------------------------------------------------------
    # Destructeur
    # ------------------------------------------------------------------

    def target_value(self, state, target: Robot, radar_dest) -> int:
        value = VALUE.get(target.type, 0)
        if target.type == "R" and target.carrying_element:
            value = 1000
        # Un K ennemi proche de notre Radar est la priorité absolue
        if target.type == "K" and radar_dest and distance(target.pos, radar_dest) <= 6:
            value += 1000
        return value

    def play_destructor(self, state, k, radar_dest, threat, taken, index):
        targets = state.targets_in_range(k)
        if targets:
            best = max(targets, key=lambda t: (self.target_value(state, t, radar_dest),
                                               -k.distance_to(t)))
            taken.add(k.pos)
            return shoot(k, best)

        # Pas de cible : rester sur un flanc du Radar. Tout ce que le Radar
        # voit (3 cases) est alors presque toujours à portée de tir, et on ne
        # s'avance jamais là où un ennemi nous verrait sans être vu.
        if radar_dest is not None:
            towards = threat or self.group_goal(state, None)
            if towards == radar_dest:
                towards = (state.map_width // 2, state.map_height // 2)
            ux, uy = axis_unit(radar_dest, towards)
            px, py = (-uy, ux) if index % 2 == 0 else (uy, -ux)  # flanc gauche/droit
            goal = (radar_dest[0] + px, radar_dest[1] + py)
            if not state.is_inside(goal):  # contre un bord : l'autre flanc
                goal = (radar_dest[0] - px, radar_dest[1] - py)
            goal = clamp(state, goal)
        else:
            # Radar perdu : chasser à l'aveugle les ennemis mémorisés
            known = self.known_enemies()
            goal = (min(known, key=lambda m: distance(m["pos"], k.pos))["pos"]
                    if known else self.group_goal(state, None))

        path = self.avoid_taken(k, state.path_towards(k, goal, self.avoid), taken)
        if not path:
            taken.add(k.pos)
            return None
        return move(k, *path)

    # ------------------------------------------------------------------
    # Outils
    # ------------------------------------------------------------------

    @staticmethod
    def avoid_taken(robot, path, taken) -> list[str]:
        """Raccourcit le chemin pour ne pas viser une case déjà visée par un
        allié (deux robots qui visent la même case ne bougent pas)."""
        path = list(path)
        while path:
            dest = robot.pos
            for d in path:
                dest = step(dest, d)
            if dest not in taken:
                taken.add(dest)
                return path
            path.pop()
        return path
