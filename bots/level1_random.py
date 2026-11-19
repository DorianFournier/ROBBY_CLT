# bots/level1_random.py
# NIVEAU 1 : joue au hasard (mais sans erreur de règle).

import random

from robby import GameState, move, shield
from robby.strategy import Strategy


class RandomBot(Strategy):

    def decide(self, state: GameState) -> list[dict]:
        commands = []
        for robot in state.my_robots:
            if not robot.can_act:
                continue
            escape = state.zone_escape(robot)     # jamais de suicide dans la zone
            if escape:
                command = state.move_towards(robot, escape)
                if command:
                    commands.append(command)
                continue
            targets = state.targets_in_range(robot) if robot.type == "K" else []
            # tirer ou tourner le bouclier n'arrête pas le robot : on vérifie
            # qu'il ne finira pas dans la tempête sur sa lancée (keep_safe)
            if targets and random.random() < 0.7:
                commands.append(state.keep_safe(
                    robot, state.shoot_at(robot, random.choice(targets))))
            elif robot.shield_ready and random.random() < 0.3:
                commands.append(state.keep_safe(
                    robot, shield(robot, angle=random.uniform(0, 360))))
            else:
                command = self.random_move(state, robot)
                if command:
                    commands.append(command)
        return commands

    @staticmethod
    def random_move(state: GameState, robot):
        """Direction et vitesse au hasard, arrivée dans la zone sûre."""
        for _ in range(20):
            angle = random.uniform(0, 360)
            speed = random.uniform(0.3, 1) * state.max_speed(robot)
            if state.in_zone(state.destination(robot, angle, speed), 1,
                             inset=state.robot_radius):
                return move(robot, angle=angle, speed=speed)
        return None
