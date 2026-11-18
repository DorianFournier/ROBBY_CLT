from robby.game_state import direction_to, distance, step
from tests.helpers import make_state, robot


def test_distance_counts_diagonals_as_one_move():
    assert distance((0, 0), (3, 2)) == 3


def test_step_and_direction_to():
    assert step((5, 5), "UR") == (6, 4)
    assert direction_to((5, 5), (9, 1)) == "UR"
    assert direction_to((5, 5), (5, 5)) is None


def test_my_robots_and_enemies():
    state = make_state([
        robot(11, 1, "R", 1, 7), robot(12, 1, "D", 0, 8, alive=False),
        robot(21, 2, "R", 13, 7),
    ])
    assert [r.id for r in state.my_robots] == [11]
    assert [r.id for r in state.enemies] == [21]


def test_bases_follow_map_size():
    state = make_state([])
    assert state.my_base == (0, 7)
    assert state.base_of(2) == (14, 7)
    assert state.base_of(4) == (7, 14)


def test_cannot_move_outside_map_or_into_shield():
    state = make_state([
        robot(11, 1, "R", 0, 7),
        robot(22, 2, "D", 2, 7, shield="SL"),  # couvre (1, 6), (1, 7), (1, 8)
    ])
    radar = state.get_robot(11)
    assert not state.can_move(radar, "L")
    assert not state.can_move(radar, "R")
    assert state.can_move(radar, "U")


def test_direction_towards_avoids_shield():
    state = make_state([
        robot(11, 1, "R", 0, 7),
        robot(22, 2, "D", 2, 7, shield="SL"),
    ])
    radar = state.get_robot(11)
    assert state.direction_towards(radar, (7, 7)) is None  # toute avancée bloquée
    assert state.direction_towards(radar, (0, 0)) == "U"


def test_targets_in_range_respect_range_and_shields():
    state = make_state([
        robot(13, 1, "K", 5, 5),
        robot(21, 2, "R", 8, 5),                 # à portée, trajectoire libre
        robot(23, 2, "K", 10, 5),                # hors portée
        robot(31, 3, "R", 5, 8),                 # à portée mais protégé
        robot(32, 3, "D", 5, 7, shield="SU"),    # bouclier en (4..6, 6)
    ])
    k = state.get_robot(13)
    assert {r.id for r in state.targets_in_range(k)} == {21}


def test_own_shield_does_not_block_moves_or_shots():
    state = make_state([
        robot(12, 1, "D", 5, 5, shield="SR"),   # bouclier allié en (6, 4..6)
        robot(13, 1, "K", 7, 5),
        robot(21, 2, "R", 4, 5),
    ])
    k = state.get_robot(13)
    assert state.can_move(k, "L")                         # traverse (6, 5)
    assert [r.id for r in state.targets_in_range(k)] == [21]
    assert state.shield_cells() == set()
    assert (6, 5) in state.shield_cells(only_enemies=False)


def test_speed_by_type():
    state = make_state([robot(11, 1, "R", 1, 7), robot(12, 1, "D", 0, 8),
                        robot(13, 1, "K", 0, 6)])
    assert [state.speed(state.get_robot(i)) for i in (11, 12, 13)] == [1, 2, 3]


def test_path_towards_uses_full_speed_and_straight_line():
    state = make_state([robot(13, 1, "K", 2, 7)])
    k = state.get_robot(13)
    assert state.path_towards(k, (10, 7)) == ["R", "R", "R"]
    assert state.path_towards(k, (3, 7)) == ["R"]          # s'arrête sur la cible
    assert state.path_towards(k, (2, 7)) == []


def test_path_towards_goes_around_enemy_shield():
    state = make_state([
        robot(13, 1, "K", 4, 5),
        robot(22, 2, "D", 7, 5, shield="SL"),   # (6, 4), (6, 5), (6, 6)
    ])
    k = state.get_robot(13)
    path = state.path_towards(k, (9, 5))
    assert state.can_follow(k, path) and len(path) == 3
    cells, pos = [], k.pos
    from robby.game_state import step
    for d in path:
        pos = step(pos, d)
        cells.append(pos)
    assert not {(6, 4), (6, 5), (6, 6)} & set(cells)


def test_can_follow_rejects_too_long_or_blocked_paths():
    state = make_state([robot(11, 1, "R", 1, 7), robot(13, 1, "K", 0, 6)])
    assert not state.can_follow(state.get_robot(11), ["R", "R"])
    assert not state.can_follow(state.get_robot(13), ["L"])
    assert state.can_follow(state.get_robot(13), ["R", "R", "R"])


def test_shortest_path_to_blocked_target_gets_as_close_as_possible():
    state = make_state([
        robot(13, 1, "K", 2, 7),
        robot(22, 2, "D", 10, 7, shield="SL"),  # (9, 6), (9, 7), (9, 8)
    ])
    path = state.shortest_path((2, 7), (9, 7))
    pos = (2, 7)
    for d in path:
        from robby.game_state import step
        pos = step(pos, d)
    assert distance(pos, (9, 7)) == 1
