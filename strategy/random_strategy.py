# strategy/random_strategy.py
# Adversaire d'entraînement : joue au hasard (mais sans erreur de règle).

import random

from robby import GameState, move, shield, shoot
from robby.constants import SHIELD_DIRECTIONS
from robby.strategy import Strategy


class RandomStrategy(Strategy):

    def decide(self, state: GameState) -> list[dict]:
        commands = []
        for robot in state.my_robots:
            if not robot.can_act:
                continue
            targets = state.targets_in_range(robot) if robot.type == "K" else []
            if targets and random.random() < 0.7:
                commands.append(shoot(robot, random.choice(targets)))
            elif robot.type == "D" and random.random() < 0.3:
                commands.append(shield(robot, random.choice(SHIELD_DIRECTIONS)))
            else:
                moves = state.possible_moves(robot)
                if moves:
                    commands.append(move(robot, random.choice(moves)))
        return commands
