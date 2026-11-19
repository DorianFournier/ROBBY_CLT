# bots/level2_rusher.py
# NIVEAU 2 — « fonceur » : aucune prudence, aucune mémoire.
#   - Radar : va droit sur l'élément, puis le ramène à la base.
#   - Destructeur : tire sur l'ennemi visible le plus proche, sinon lui fonce
#     dessus ; s'il ne voit personne, il reste près de son Radar.
#   - Défenseur : suit le Radar et tourne son bouclier vers l'ennemi le plus
#     proche.
#   - Zone (phase 2) : tout robot hors de la zone sûre y rentre en priorité.

from robby import GameState, move, shield, shoot
from robby.game_state import Robot
from robby.strategy import Strategy


def shield_towards(defender: Robot, target_pos) -> str:
    """Côté du bouclier qui fait face à une position (axe dominant)."""
    dx, dy = target_pos[0] - defender.x, target_pos[1] - defender.y
    if abs(dx) >= abs(dy):
        return "SR" if dx > 0 else "SL"
    return "SD" if dy > 0 else "SU"


class RusherBot(Strategy):

    def decide(self, state: GameState) -> list[dict]:
        commands = []
        taken = set()  # cases d'arrivée déjà visées par nos robots
        # Les robots en danger dans la zone choisissent leur case en premier
        robots = sorted(state.my_robots, key=lambda r: state.in_zone(r.pos, 2))
        for robot in robots:
            if not robot.can_act:
                taken.add(robot.pos)
                continue
            # Zone (phase 2) : rentrer dans la zone sûre avant tout
            escape = state.zone_escape_path(robot, lookahead=2, taken=taken)
            if escape:
                command = move(robot, *escape)
            elif robot.type == "R":
                command = self.radar(state, robot)
            elif robot.type == "K":
                command = self.destructor(state, robot)
            else:
                command = self.defender(state, robot)
            # Deux robots qui visent la même case ne bougent pas : on évite
            if command and command["action"] == "MOVE":
                path = state.trim_to_free(robot, command["path"], taken)
                command = move(robot, *path) if path else None
            if command and command["action"] == "MOVE":
                taken.add(state.destination(robot, command["path"]))
            else:
                taken.add(robot.pos)
            if command:
                commands.append(command)
        return commands

    def radar(self, state, radar):
        if state.phase != 1:
            return None
        if radar.carrying_element:
            target = state.my_base
        elif state.element.is_free:
            target = state.element.pos
        else:
            return None
        path = state.path_towards(radar, target)
        return move(radar, *path) if path else None

    def destructor(self, state, k):
        targets = state.targets_in_range(k)
        if targets:
            return shoot(k, state.nearest(k, targets))
        # Ennemi à portée mais derrière un bouclier : tirer quand même l'use,
        # et il se brise au bout de quelques tirs (anti-blocage)
        shielded = state.shielded_targets(k)
        if shielded:
            return shoot(k, state.nearest(k, shielded))
        enemy = state.nearest(k, state.enemies)
        if enemy:
            target = enemy.pos
        else:
            # Sans ennemi visible : rester près du Radar, sinon on ne voit rien
            radars = state.my_robots_of_type("R")
            if radars and k.distance_to(radars[0]) > 2:
                target = radars[0].pos
            elif radars:
                return None
            else:
                target = state.safe_cell
        path = state.path_towards(k, state.clamp_to_zone(target, 2))
        return move(k, *path) if path else None

    def defender(self, state, d):
        enemy = state.nearest(d, state.enemies)
        if enemy and d.shield_ready:          # bouclier brisé : indisponible
            wanted = shield_towards(d, enemy.pos)
            if wanted != d.shield_direction:
                return shield(d, wanted)
        radars = state.my_robots_of_type("R")
        if radars and d.distance_to(radars[0]) > 1:
            path = state.path_towards(d, radars[0].pos)
            return move(d, *path) if path else None
        return None
