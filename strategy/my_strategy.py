# strategy/my_strategy.py
# =====================================================================
# C'EST ICI QUE VOUS DÉVELOPPEZ VOTRE STRATÉGIE.
#
# `decide(state)` est appelée à chaque tour et retourne la liste des
# commandes. Les robots partent dans une direction (un ANGLE en degrés) à
# une VITESSE donnée.
#   Angles : 0 = haut, 90 = droite, 180 = bas, 270 = gauche (boussole)
#   Arène  : 15000 x 15000 unités, y vers le BAS
#
# Commandes (au plus UNE par robot et par tour) :
#   move(robot, angle=90, speed=2000)   règle le CAP et la VITESSE du robot
#                                 (max par tour : R 1500, C 1000, D 2000, K 3000)
#   stop(robot)                         vitesse 0
#   shoot(destructeur, angle=45)        rayon de 3000 : touche le 1er ennemi
#   shield(defenseur, angle=180)        bouclier de 90° tourné vers l'angle
#
# ATTENTION : un robot GARDE son cap et sa vitesse d'un tour à l'autre. Sans
# nouvelle commande (ou s'il tire, s'il pose son bouclier), il continue
# d'avancer tout seul ! Il ne s'arrête que si vous le lui demandez (stop),
# s'il heurte un ennemi ou un bouclier ennemi, ou s'il est pénalisé.
# robot.heading et robot.speed : son cap et sa vitesse actuels.
#
# Outils utiles de `state` (voir robby/game_state.py et le README) :
#   state.move_towards(robot, point)    commande toute prête pour y aller
#                                       (et pour s'arrêter une fois arrivé)
#   state.predict(robot, tours)         où il sera s'il garde son cap
#   state.keep_safe(robot, commande)    tirer en roulant, sauf vers la tempête
#   state.targets_in_range(k)           ennemis qu'un tir toucherait
#   state.shoot_at(k, cible)            commande de tir visée sur la cible
#   state.aim(k, cible), state.distance(a, b), robot.angle_to(cible)
#   state.zone_escape(robot)            point sûr si la zone menace le robot
#   state.firing_spot(k, cible)         où aller pour contourner un bouclier
#
# Lancement :
#   uv run main.py --name Moi                      (votre stratégie)
#   uv run main.py --name Adversaire --strategy bot1
# Paliers : battre bot1, puis bot2, puis bot3, puis bot4
#
# Les robots : R Radar (le seul qui voit les ennemis), C Collecteur (le seul
# qui ramasse les batteries, le plus lent), D Défenseur (bouclier),
# K Destructeur (tir).
# Ce squelette ne fait bouger que le Collecteur. À vous de jouer pour le reste !
# =====================================================================

from robby import GameState
from robby.strategy import Strategy


class MyStrategy(Strategy):
    # Placement de départ (vu depuis votre base, face au centre) : "gauche",
    # "milieu" (sur la base), "droite", et "avant" devant. Une place par
    # robot. À vous de choisir !
    placement = {"R": "avant", "C": "milieu", "D": "droite", "K": "gauche"}

    def decide(self, state: GameState) -> list[dict]:
        commands = []

        for robot in state.my_robots:
            if not robot.can_act:  # pénalisé : sa commande serait ignorée
                continue

            if robot.type == "C":
                command = self.play_collector(state, robot)
            elif robot.type == "R":
                command = self.play_radar(state, robot)
            elif robot.type == "K":
                command = self.play_destructor(state, robot)
            else:
                command = self.play_defender(state, robot)

            if command:
                commands.append(command)

        return commands

    def play_collector(self, state, collector):
        # Phase 1 : aller chercher une batterie puis la ramener à la base
        # (chaque batterie ramenée rapporte des points, puis elle réapparaît)
        if state.phase == 1:
            if collector.carrying_element:
                return state.move_towards(collector, state.my_base)
            battery = state.nearest_battery(collector)   # ou state.best_battery
            if battery:
                return state.move_towards(collector, battery.pos)
        # Rien à faire : on l'arrête, sinon il continuerait sur sa lancée
        return state.stop(collector)

    def play_radar(self, state, radar):
        # TODO : le Radar est le seul à voir les ennemis. L'accompagner avec
        #        le Collecteur ? Le placer pour voir qui arrive ?
        return None

    def play_destructor(self, state, destructor):
        # TODO : tirer sur un ennemi (state.targets_in_range, state.shoot_at),
        #        sinon se déplacer... mais où ?
        return None

    def play_defender(self, state, defender):
        # TODO : tourner le bouclier vers la menace (shield(d, angle=...)) ?
        return None
