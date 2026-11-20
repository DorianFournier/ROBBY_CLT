from robby import GameState


def robot(id, team, type, x, y, alive=True, shield=None, carrying=False, penalty=0,
          heading=None, speed=0, captive_id=None, captured_by=None):
    return {"id": id, "team": team, "type": type, "x": x, "y": y, "alive": alive,
            "shield": shield, "carrying_element": carrying, "penalty": penalty,
            "heading": heading, "speed": speed, "captive_id": captive_id,
            "captured_by": captured_by}


def make_state(robots, team_id=1, phase=1, element=(7500, 7500), carried_by=None,
               zone=None, turn=1, dump=None):
    """État du jeu vu par `team_id` (positions en unités)."""
    msg = {
        "type": "game_state", "turn": turn, "phase": phase, "phase_turn": turn,
        "robots": robots, "zone": zone, "dump": dump,
        "element": {"x": element[0], "y": element[1], "carried_by_id": carried_by},
    }
    return GameState(msg, team_id, {})
