# strategy/my_strategy.py
# =====================================================================
# C'EST ICI QUE VOUS DÉVELOPPEZ VOTRE STRATÉGIE.
#
# `decide(state)` est appelée à chaque tour et retourne une liste de
# commandes (au plus UNE par robot) construites avec :
#   move(robot, "U", "UR", ...)   une direction par case parcourue
#       (U, UR, R, DR, D, DL, L, UL) ; vitesse max : K 3, D 2, R 1 case(s)
#   shoot(destructeur, cible)
#   shield(defenseur, "SU" | "SR" | "SD" | "SL")
#
# Outils utiles de `state` (voir robby/game_state.py) :
#   state.my_robots, state.enemies, state.element, state.my_base,
#   state.phase, state.turn, state.path_towards(robot, (x, y)),
#   state.possible_moves(robot), state.targets_in_range(robot),
#   state.nearest(robot, liste_de_robots) ...
#
# La stratégie ci-dessous est un EXEMPLE volontairement simple.
# =====================================================================

from robby import GameState, move, shield, shoot
from robby.strategy import Strategy


class MyStrategy(Strategy):

    def decide(self, state: GameState) -> list[dict]:
        commands = []

        for robot in state.my_robots:
            if not robot.can_act:  # pénalisé : sa commande serait ignorée
                continue

            if robot.type == "R":
                command = self.play_radar(state, robot)
            elif robot.type == "K":
                command = self.play_destructor(state, robot)
            else:
                command = self.play_defender(state, robot)

            if command:
                commands.append(command)

        return commands

    def play_radar(self, state, radar):
        # Phase 1 : aller chercher l'élément puis le ramener à la base
        if state.phase == 1:
            if radar.carrying_element:
                target = state.my_base
            elif state.element.is_free:
                target = state.element.pos
            else:
                return None
            path = state.path_towards(radar, target)
            return move(radar, *path) if path else None
        return None

    def play_destructor(self, state, destructor):
        # Tirer sur l'ennemi atteignable le plus proche, sinon s'en approcher
        targets = state.targets_in_range(destructor)
        if targets:
            return shoot(destructor, state.nearest(destructor, targets))

        enemy = state.nearest(destructor, state.enemies)
        if enemy:
            path = state.path_towards(destructor, enemy.pos)
            return move(destructor, *path) if path else None
        return None

    def play_defender(self, state, defender):
        # Orienter le bouclier vers l'ennemi visible le plus proche
        enemy = state.nearest(defender, state.enemies)
        if not enemy:
            return None
        dx, dy = enemy.x - defender.x, enemy.y - defender.y
        if abs(dx) >= abs(dy):
            wanted = "SR" if dx > 0 else "SL"
        else:
            wanted = "SD" if dy > 0 else "SU"
        if wanted != defender.shield_direction:
            return shield(defender, wanted)
        return None
