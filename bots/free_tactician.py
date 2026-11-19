# bots/free_tactician.py
# MODE LIBRE — NIVEAU 3 : « tacticien ».
#   - Mémoire : se souvient des ennemis vus récemment (brouillard de guerre).
#   - Défenseur : se place entre son Radar et la menace la plus proche, bouclier
#     tourné vers elle (le bouclier arrête les tirs ennemis).
#   - Destructeur : choisit sa cible (porteur de batterie, puis Radar,
#     Destructeur, Défenseur) ; si un bouclier protège l'ennemi, va se placer
#     sur le côté pour tirer au tour suivant ; sinon s'approche juste à portée
#     de la menace la plus proche, ou escorte son Radar.
#   - Radar : va chercher la batterie s'il n'est pas menacé, recule derrière
#     son Défenseur sinon ; en phase 2, reste groupé, au centre de la zone.

from robby import FreeGameState, shield
from robby.geometry import angle_diff, direction
from robby.strategy import Strategy

MEMORY = 6          # tours pendant lesquels on se souvient d'un ennemi
DANGER = 4500       # un K ennemi plus près que ça du Radar : menace
PRIORITY = {"R": 1, "K": 2, "D": 3}


class FreeTacticianBot(Strategy):
    modes = ("libre",)

    def __init__(self):
        self.seen = {}      # robot_id -> (type, position, tour)
        self.last_known = None   # dernière position ennemie connue (sans limite)
        self.team_id, self.config = None, {}

    def on_game_start(self, team_id, config):
        self.team_id, self.config = team_id, config

    def on_turn_result(self, turn, result):
        for robot_id in result.get("deaths", []):
            self.seen.pop(robot_id, None)

    # ------------------------------------------------------------------

    def decide(self, state: FreeGameState) -> list[dict]:
        for e in state.enemies:
            self.seen[e.id] = (e.type, e.pos, state.turn)
            self.last_known = e.pos
        self.seen = {i: v for i, v in self.seen.items() if state.turn - v[2] <= MEMORY}
        self.threats = [(t, p) for t, p, _ in self.seen.values()]

        radars = state.my_robots_of_type("R")
        self.radar = radars[0] if radars else None
        commands = []
        for robot in state.my_robots:
            if not robot.can_act:
                continue
            escape = state.zone_escape(robot)
            if escape:
                command = state.move_towards(robot, escape)
            elif robot.type == "R":
                command = self.play_radar(state, robot)
            elif robot.type == "K":
                command = self.play_destructor(state, robot)
            else:
                command = self.play_defender(state, robot)
            if command:
                commands.append(command)
        return commands

    def nearest_threat(self, state, origin, types="RDK"):
        candidates = [p for t, p in self.threats if t in types]
        if not candidates:
            return None
        return min(candidates, key=lambda p: state.distance(origin, p))

    def hunt_point(self, state):
        """Phase 2 sans ennemi en vue : dernier ennemi aperçu, sinon la base
        adverse la plus proche (dans la zone sûre)."""
        if self.last_known is not None:
            target = self.last_known
        else:
            teams = [int(t) for t in (state.config.get("teams") or {})]
            bases = [state.base_of(t) for t in teams if t != state.team_id]
            bases = [b for b in bases if b]
            target = min(bases, key=lambda b: state.distance(state.safe_center, b)) \
                if bases else state.safe_center
        return state.clamp_to_zone(target, 3, inset=1500)

    def home(self, state):
        """Point de ralliement : la batterie (phase 1) ou le centre de la zone."""
        if state.phase == 1 and state.element.is_free:
            return state.element.pos
        return state.clamp_to_zone(state.safe_center, 3)

    # ------------------------------------------------------------------

    def play_radar(self, state, radar):
        danger = self.nearest_threat(state, radar, "K")
        threatened = danger and state.distance(radar, danger) < DANGER
        if state.phase == 1 and radar.carrying_element:
            return state.move_towards(radar, state.my_base)
        if threatened:
            defenders = state.my_robots_of_type("D")
            if defenders:   # se cacher derrière le Défenseur
                d = defenders[0]
                away = d.angle_to(danger)
                dx, dy = direction((away + 180) % 360) if away is not None else (0, 0)
                hide = state.clamp_to_zone((d.x + dx * 700, d.y + dy * 700), 2)
                return state.move_towards(radar, hide)
            return state.move_away(radar, danger)
        if state.phase == 1 and state.element.is_free:
            return state.move_towards(radar, state.element.pos)
        if state.phase == 2:   # le Radar mène la chasse, les autres l'escortent
            if self.last_known is not None and state.distance(radar,
                                                              self.last_known) < 1000:
                self.last_known = None     # plus personne ici
            return state.move_towards(radar, self.hunt_point(state))
        killers = state.my_robots_of_type("K")
        target = killers[0].pos if killers else self.home(state)
        return state.move_towards(radar, state.clamp_to_zone(target, 3), stop_at=1500)

    def play_defender(self, state, d):
        protect = self.radar.pos if self.radar else d.pos
        threat = self.nearest_threat(state, protect, "K") or \
            self.nearest_threat(state, protect)
        if threat is None:
            target = self.radar or self.home(state)
            return state.move_towards(d, state.clamp_to_zone(
                target.pos if hasattr(target, "pos") else target, 2), stop_at=800)
        wanted = d.angle_to(threat)
        if wanted is not None and (d.shield_direction is None
                                   or angle_diff(wanted, d.shield_direction) > 25):
            return shield(d, angle=wanted)
        # se placer à 700 du Radar, du côté de la menace (le bouclier suit)
        heading = state.aim(self.radar, threat) if self.radar else None
        if heading is None:
            return None
        dx, dy = direction(heading)
        spot = state.clamp_to_zone((protect[0] + dx * 700, protect[1] + dy * 700), 2)
        return state.move_towards(d, spot)

    def play_destructor(self, state, k):
        targets = state.targets_in_range(k)
        if targets:
            best = min(targets, key=lambda e: (not e.carrying_element,
                                               PRIORITY[e.type], state.distance(k, e)))
            return state.shoot_at(k, best)
        # Ennemi visible mais protégé : contourner son bouclier
        for enemy in sorted(state.enemies, key=lambda e: (PRIORITY[e.type],
                                                          state.distance(k, e))):
            spot = state.firing_spot(k, enemy)
            if spot:
                return state.move_towards(k, spot)
        threat = self.nearest_threat(state, k)
        if threat:
            return state.move_towards(k, state.clamp_to_zone(threat, 2), stop_at=2600)
        escort = self.radar.pos if self.radar else self.home(state)
        return state.move_towards(k, state.clamp_to_zone(escort, 2), stop_at=1000)
