# bots/level1_random.py
# NIVEAU 1 — joue au hasard (mais sans erreur de règle).
# Objectif minimal : une stratégie d'étudiant doit le battre très largement.

import random

from robby import GameState, move, shield, shoot
from robby.constants import DIRECTIONS, SHIELD_DIRECTIONS
from robby.game_state import step
from robby.strategy import Strategy


class RandomBot(Strategy):

    def decide(self, state: GameState) -> list[dict]:
        commands = []
        for robot in state.my_robots:
            if not robot.can_act:
                continue
            escape = state.zone_escape_path(robot)  # jamais de suicide dans la zone
            if escape:
                commands.append(move(robot, *escape))
                continue
            targets = state.targets_in_range(robot) if robot.type == "K" else []
            if targets and random.random() < 0.7:
                commands.append(shoot(robot, random.choice(targets)))
            elif robot.shield_ready and random.random() < 0.3:
                commands.append(shield(robot, random.choice(SHIELD_DIRECTIONS)))
            else:
                path = self.random_path(state, robot)
                if path:
                    commands.append(move(robot, *path))
        return commands

    @staticmethod
    def random_path(state: GameState, robot) -> list[str]:
        """Chemin aléatoire valide de 1 à speed(robot) cases, qui finit dans la
        zone sûre (ou vide)."""
        for _ in range(20):
            length = random.randint(1, state.speed(robot))
            path = [random.choice(list(DIRECTIONS)) for _ in range(length)]
            dest = robot.pos
            for d in path:
                dest = step(dest, d)
            if state.can_follow(robot, path) and state.in_zone(dest, 1):
                return path
        return []
