import pytest

from robby import move, shield, shoot
from robby.client import check_commands
from tests.helpers import make_state, robot


def test_command_factories():
    state = make_state([robot(13, 1, "K", 5, 5), robot(21, 2, "R", 6, 6)])
    k, enemy = state.get_robot(13), state.get_robot(21)
    assert move(k, "U") == {"robot_id": 13, "action": "MOVE", "path": ["U"]}
    assert move(k, "R", "R", "UR") == {"robot_id": 13, "action": "MOVE",
                                       "path": ["R", "R", "UR"]}
    assert shoot(k, enemy) == {"robot_id": 13, "action": "SHOOT", "target_id": 21}
    assert shield(12, "SD") == {"robot_id": 12, "action": "SHIELD", "direction": "SD"}


def test_invalid_directions_raise():
    with pytest.raises(ValueError):
        move(1, "NORTH")
    with pytest.raises(ValueError):
        move(1)
    with pytest.raises(ValueError):
        shield(1, "U")


def test_check_commands_reports_rule_errors():
    state = make_state([
        robot(11, 1, "R", 1, 7), robot(13, 1, "K", 2, 7), robot(21, 2, "R", 3, 7),
    ])
    errors = check_commands(state, [
        move(11, "U"), move(11, "D"),   # deux commandes pour le même robot
        move(21, "L"),                  # robot ennemi
    ])
    assert len(errors) == 2
    assert len(check_commands(state, [shoot(11, 21)])) == 1  # un radar ne tire pas
    assert check_commands(state, [move(11, "U"), shoot(13, 21)]) == []
    assert len(check_commands(state, [move(11, "U", "U")])) == 1  # R : 1 case
    assert check_commands(state, [move(13, "U", "U", "U")]) == []  # K : 3 cases


def test_connection_has_pending():
    import socket

    from robby.protocol import Connection

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    conn = Connection("127.0.0.1", server.getsockname()[1])
    peer, _ = server.accept()
    with conn, peer, server:
        assert not conn.has_pending()
        peer.sendall(b'{"a": 1}\n{"b": 2}\n')
        import time
        time.sleep(0.05)
        assert conn.has_pending()
        assert conn.receive() == {"a": 1}
        assert conn.has_pending()
        assert conn.receive() == {"b": 2}
        assert not conn.has_pending()
