# bots/free_rusher.py
# MODE LIBRE — NIVEAU 2 : « fonceur », aucune prudence, aucune mémoire.
#   - Radar : va droit sur la batterie puis la ramène ; en phase 2, suit son K.
#   - Destructeur : tire sur l'ennemi le plus proche qu'il peut toucher, sinon
#     fonce vers l'ennemi visible le plus proche ; sinon reste près du Radar.
#   - Défenseur : tourne son bouclier vers l'ennemi le plus proche, sinon
#     suit le Radar.
#   - Zone (phase 2) : tout robot en danger rentre dans la zone sûre d'abord.

from robby import FreeGameState, shield
from robby.geometry import angle_diff
from robby.strategy import Strategy


class FreeRusherBot(Strategy):
    modes = ("libre",)

    def decide(self, state: FreeGameState) -> list[dict]:
        commands = []
        for robot in state.my_robots:
            if not robot.can_act:
                continue
            escape = state.zone_escape(robot)
            if escape:
                command = state.move_towards(robot, escape)
            elif robot.type == "R":
                command = self.radar(state, robot)
            elif robot.type == "K":
                command = self.destructor(state, robot)
            else:
                command = self.defender(state, robot)
            command = state.keep_safe(robot, command)   # tir en roulant : prudence
            if command:
                commands.append(command)
        return commands

    def radar(self, state, radar):
        if state.phase == 1:
            if radar.carrying_element:
                return state.move_towards(radar, state.my_base)
            if state.element.is_free:
                return state.move_towards(radar, state.element.pos)
        killers = state.my_robots_of_type("K")
        if killers:
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
        enemy = state.nearest(k, state.enemies)
        if enemy:
            return state.move_towards(k, state.clamp_to_zone(enemy.pos, 2),
                                      stop_at=2200)
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
        return None
