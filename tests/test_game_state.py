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
