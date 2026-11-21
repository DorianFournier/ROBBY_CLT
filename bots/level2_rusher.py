# bots/level2_rusher.py
# NIVEAU 2 : « fonceur », aucune prudence, aucune mémoire.
#   - Collecteur : va droit sur la batterie la plus proche puis la ramène.
#   - Radar : accompagne le Collecteur en phase 1, puis suit son Destructeur
#     en phase 2 (il lui donne la vision).
#   - Destructeur : tire sur l'ennemi le plus proche qu'il peut toucher, sinon
#     fonce vers l'ennemi visible le plus proche ; sinon reste près du Radar.
#   - Défenseur : tourne son bouclier vers l'ennemi le plus proche, sinon
#     suit le Radar.
#   - Zone (phase 2) : tout robot en danger rentre dans la zone sûre d'abord.

from bots.chasse import aller, aveugle, chasse, heurte, patrouille, ronde
from robby import GameState, shield, shoot
from robby.geometry import angle_diff
from robby.strategy import Strategy


class RusherBot(Strategy):

    def decide(self, state: GameState) -> list[dict]:
        commands = []
        for robot in state.my_robots:
            if not robot.can_act:
                continue
            escape = state.zone_escape(robot)
            if escape:
                command = state.move_towards(robot, escape)
            elif robot.type == "R":
                command = self.radar(state, robot)
            elif robot.type == "C":
                command = self.collector(state, robot)
            elif robot.type == "K":
                command = self.destructor(state, robot)
            else:
                command = self.defender(state, robot)
            command = state.keep_safe(robot, command)   # tir en roulant : prudence
            if command:
                commands.append(command)
        # dernières commandes : un robot arrêté net au tour suivant a heurté
        # quelque chose (voir bots/chasse.py, heurte)
        self.last = {c["robot_id"]: c for c in commands}
        return commands

    def collector(self, state, collector):
        """Phase 1 : la batterie libre la plus proche, puis retour à la base.
        Phase 2 : il attrape l'ennemi à l'arrêt le plus proche et le porte à
        la déchèterie ; sinon il suit le Radar."""
        if state.phase == 1:
            if collector.carrying_element:
                return state.move_towards(collector, state.my_base)
            battery = state.nearest_battery(collector)
            if battery:
                return state.move_towards(collector, battery.pos)
        command = chasse(state, collector, offensif=True)   # phase 2 : déchèterie
        if command:
            return command
        radars = state.my_robots_of_type("R")
        if radars:
            return state.move_towards(collector, state.clamp_to_zone(radars[0].pos, 2),
                                      stop_at=900)
        return state.move_towards(collector, state.clamp_to_zone(state.safe_center, 2))

    def radar(self, state, radar):
        """Phase 1 : le Radar accompagne le Collecteur (on voit qui vient le
        chercher). Phase 2 : il suit le Destructeur, pour lui donner la vision ;
        si personne n'est en vue, c'est lui qui part à la recherche des ennemis
        (le Destructeur le suit), sinon tout le monde s'attendrait."""
        collectors = state.my_robots_of_type("C")
        if state.phase == 1 and collectors:
            target = state.clamp_to_zone(collectors[0].pos, 2)
            return state.move_towards(radar, target, stop_at=800)
        if state.phase == 2 and not state.enemies:
            return aller(state, radar, ronde(state, radar))
        killers = state.my_robots_of_type("K") or state.my_robots_of_type("C")
        if killers:     # le Destructeur, sinon le Collecteur qui chasse
            target = state.clamp_to_zone(killers[0].pos, 2)
            return state.move_towards(radar, target, stop_at=1200)
        return state.move_towards(radar, state.clamp_to_zone(state.safe_center, 2))

    def destructor(self, state, k):
        targets = state.targets_in_range(k)
        if targets:
            return state.shoot_at(k, state.nearest(k, targets))
        # Ennemi à portée mais derrière un bouclier : tirer quand même l'use,
        # et il se brise au bout de quelques tirs (anti-blocage)
        shielded = state.shielded_targets(k)
        if shielded:
            return state.shoot_at(k, state.nearest(k, shielded))
        # arrêté net sans rien voir : un ennemi invisible est juste devant
        bump = heurte(k, getattr(self, "last", {}).get(k.id))
        if bump is not None:
            return shoot(k, angle=bump)
        enemy = state.nearest(k, state.enemies)
        if enemy:
            return state.move_towards(k, state.clamp_to_zone(enemy.pos, 2),
                                      stop_at=2200)
        if aveugle(state):          # plus de Radar : patrouille
            return patrouille(state, k)
        radars = state.my_robots_of_type("R")
        if radars:
            return state.move_towards(k, state.clamp_to_zone(radars[0].pos, 2),
                                      stop_at=1000)
        return state.move_towards(k, state.safe_center, stop_at=1000)

    def defender(self, state, d):
        enemy = state.nearest(d, state.enemies)
        if enemy and d.shield_ready:          # bouclier brisé : indisponible
            wanted = d.angle_to(enemy)
            if wanted is not None and (d.shield_direction is None
                                       or angle_diff(wanted, d.shield_direction) > 20):
                return shield(d, angle=wanted)
        radars = state.my_robots_of_type("R")
        if radars:
            return state.move_towards(d, state.clamp_to_zone(radars[0].pos, 2),
                                      stop_at=700)
        if aveugle(state):          # plus de Radar : il suit le Destructeur
            killers = state.my_robots_of_type("K")
            if killers:
                return state.move_towards(d, state.clamp_to_zone(killers[0].pos, 2),
                                          stop_at=700)
            return patrouille(state, d)
        return None
