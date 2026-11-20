# bots/level3_tactician.py
# NIVEAU 3 : « tacticien ».
#   - Mémoire : se souvient des ennemis vus récemment (brouillard de guerre).
#   - Défenseur : se place entre son Radar et la menace la plus proche, bouclier
#     tourné vers elle (le bouclier arrête les tirs ennemis).
#   - Destructeur : choisit sa cible (porteur de batterie, puis Radar,
#     Destructeur, Défenseur) ; si un bouclier protège l'ennemi, va se placer
#     sur le côté pour tirer au tour suivant ; sinon s'approche juste à portée
#     de la menace la plus proche, ou escorte son Radar.
#   - Collecteur : va chercher la batterie la plus rentable s'il n'est pas
#     menacé, recule derrière son Défenseur sinon, puis la ramène.
#   - Radar : accompagne le Collecteur en phase 1 (il voit qui approche) ;
#     en phase 2, reste groupé, au centre de la zone, et mène la chasse.
#   - Défenseur : protège le Collecteur en phase 1, le Radar en phase 2.

from robby import GameState, shield
from robby.geometry import angle_diff, direction
from robby.strategy import Strategy

MEMORY = 6          # tours pendant lesquels on se souvient d'un ennemi
DANGER = 4500       # un K ennemi plus près que ça du Radar : menace
PRIORITY = {"C": 1, "R": 1, "K": 2, "D": 3}


class TacticianBot(Strategy):

    def __init__(self):
        self.seen = {}      # robot_id -> (type, position, tour)
        self.killers = {}   # K ennemis : id -> dernière position (sans limite)
        self.last_known = None   # dernière position ennemie connue (sans limite)
        self.team_id, self.config = None, {}

    def on_game_start(self, team_id, config):
        self.team_id, self.config = team_id, config

    def on_turn_result(self, turn, result):
        for robot_id in result.get("deaths", []):
            self.seen.pop(robot_id, None)
            self.killers.pop(robot_id, None)

    # ------------------------------------------------------------------

    def decide(self, state: GameState) -> list[dict]:
        for e in state.enemies:
            self.seen[e.id] = (e.type, e.pos, state.turn)
            self.last_known = e.pos
            if e.type == "K":
                self.killers[e.id] = e.pos
        self.seen = {i: v for i, v in self.seen.items() if state.turn - v[2] <= MEMORY}
        self.threats = [(t, p) for t, p, _ in self.seen.values()]

        radars = state.my_robots_of_type("R")
        self.radar = radars[0] if radars else None
        collectors = state.my_robots_of_type("C")
        self.collector = collectors[0] if collectors else None
        commands = []
        for robot in state.my_robots:
            if not robot.can_act:
                continue
            escape = state.zone_escape(robot)
            if escape:
                command = state.move_towards(robot, escape)
            elif robot.type == "R":
                command = self.play_radar(state, robot)
            elif robot.type == "C":
                command = self.play_collector(state, robot)
            elif robot.type == "K":
                command = self.play_destructor(state, robot)
            else:
                command = self.play_defender(state, robot)
            command = state.keep_safe(robot, command)   # tir en roulant : prudence
            if command:
                commands.append(command)
        return commands

    def nearest_threat(self, state, origin, types="RCDK"):
        candidates = [p for t, p in self.threats if t in types]
        if not candidates:
            return None
        return min(candidates, key=lambda p: state.distance(origin, p))

    def hunt_point(self, state):
        """Phase 2 : tenir le centre du prochain cercle. Avec le brouillard de
        guerre, celui qui attend voit l'autre arriver en premier, et la
        tempête finit par pousser tout le monde vers ce point."""
        return state.clamp_to_zone(state.safe_center, 3, inset=1000)

    def home(self, state):
        """Point de ralliement : la batterie la plus proche de notre base
        (phase 1) ou le centre de la zone."""
        battery = state.nearest_battery(state.my_base) if state.phase == 1 else None
        if battery:
            return battery.pos
        return state.clamp_to_zone(state.safe_center, 3)

    # ------------------------------------------------------------------

    def danger_for(self, state, robot):
        """K ennemi menaçant ce robot (ou None). Un K qui campe reste
        dangereux même invisible : en phase 2, on se souvient de sa
        dernière position sans limite de temps."""
        danger = self.nearest_threat(state, robot, "K")
        if self.killers and state.phase == 2:
            remembered = min(self.killers.values(),
                             key=lambda p: state.distance(robot, p))
            if danger is None or state.distance(robot, remembered) < \
                    state.distance(robot, danger):
                danger = remembered
        return danger if danger and state.distance(robot, danger) < DANGER else None

    def hide(self, state, robot, danger):
        """Se cacher derrière le Défenseur, sinon s'éloigner de la menace."""
        defenders = state.my_robots_of_type("D")
        if defenders:
            d = defenders[0]
            away = d.angle_to(danger)
            dx, dy = direction((away + 180) % 360) if away is not None else (0, 0)
            spot = state.clamp_to_zone((d.x + dx * 700, d.y + dy * 700), 2)
            return state.move_towards(robot, spot)
        return state.move_away(robot, danger)

    def play_collector(self, state, c):
        if state.phase == 1:
            if c.carrying_element:
                return state.move_towards(c, state.my_base)
            danger = self.danger_for(state, c)
            if danger:
                return self.hide(state, c, danger)
            battery = state.best_battery(c)
            if battery:
                return state.move_towards(c, battery.pos)
        if state.dump:      # phase 2 : la déchèterie
            if c.captive_id is not None:
                return state.move_towards(c, state.dump_center)
            danger = self.danger_for(state, c)
            if danger:
                return self.hide(state, c, danger)
            prey = self.prey_for(state, c)
            if prey is not None:
                return state.move_towards(c, prey)
        # plus rien à ramasser : il reste avec le Radar
        target = self.radar.pos if self.radar else self.home(state)
        return state.move_towards(c, state.clamp_to_zone(target, 2), stop_at=900)

    def prey_for(self, state, c):
        """Ennemi à l'arrêt que le Collecteur peut aller attraper : proche,
        et sans Destructeur ennemi à portée de lui."""
        stopped = [e for e in state.enemies if e.speed == 0 and e.captive_id is None
                   and c.distance_to(e) <= 2500]
        reach = state.config["destructor_range"] + 1000
        safe = [e for e in stopped
                if not any(k.type == "K" and k.distance_to(e) <= reach
                           for k in state.enemies)]
        return state.nearest(c, safe) if safe else None

    def play_radar(self, state, radar):
        danger = self.danger_for(state, radar)
        if danger:
            return self.hide(state, radar, danger)
        if state.phase == 1 and self.collector is not None:
            # il accompagne le Collecteur : on voit qui vient le chercher
            target = state.clamp_to_zone(self.collector.pos, 2)
            return state.move_towards(radar, target, stop_at=1200)
        if state.phase == 2:   # le Radar mène la chasse, les autres l'escortent
            if self.last_known is not None and state.distance(radar,
                                                              self.last_known) < 1000:
                self.last_known = None     # plus personne ici
            return state.move_towards(radar, self.hunt_point(state))
        killers = state.my_robots_of_type("K")
        target = killers[0].pos if killers else self.home(state)
        return state.move_towards(radar, state.clamp_to_zone(target, 3), stop_at=1500)

    def killer_threat(self, state, origin):
        """K ennemi le plus proche : visible, récent ou mémorisé (sans limite)."""
        known = [p for t, p in self.threats if t == "K"] + list(self.killers.values())
        if not known:
            return None
        return min(known, key=lambda p: state.distance(origin, p))

    def play_defender(self, state, d):
        # phase 1 : il protège le Collecteur (et sa batterie), puis le Radar
        garde = (self.collector if state.phase == 1 and self.collector
                 else self.radar)
        protect = garde.pos if garde else d.pos
        if state.phase == 2:
            threat = self.killer_threat(state, protect) or \
                self.nearest_threat(state, protect)
        else:
            threat = self.nearest_threat(state, protect, "K") or \
                self.nearest_threat(state, protect)
        if threat is None:
            target = garde or self.home(state)
            return state.move_towards(d, state.clamp_to_zone(
                target.pos if hasattr(target, "pos") else target, 2), stop_at=800)
        wanted = d.angle_to(threat) if d.shield_ready else None
        if wanted is not None and (d.shield_direction is None
                                   or angle_diff(wanted, d.shield_direction) > 25):
            return shield(d, angle=wanted)
        if state.phase == 2 and self.radar is not None:
            # Avancée escortée : le Défenseur ouvre la route vers la menace,
            # bouclier devant (il continue de rouler quand il le tourne), à
            # la vitesse du Radar qui le suit ; il l'attend s'il s'en éloigne.
            if state.distance(d, self.radar) > 1300:
                return state.move_towards(d, self.radar, stop_at=700)
            return state.move_towards(d, state.clamp_to_zone(threat, 2),
                                      speed=state.max_speed(self.radar),
                                      stop_at=2200)
        # se placer à 700 du robot garde, du côté de la menace (le bouclier suit)
        heading = state.aim(garde, threat) if garde else None
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
        # Ennemi à portée mais derrière un bouclier : tirer quand même l'use, et
        # il se brise au bout de quelques tirs. Sinon, contourner le bouclier
        # d'un ennemi visible plus loin pour pouvoir tirer au tour suivant.
        shielded = state.shielded_targets(k)
        if shielded:
            return state.shoot_at(k, min(shielded, key=lambda e: state.distance(k, e)))
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
