# robby/client.py
# Boucle principale : connexion, réception de l'état, appel à la
# stratégie, envoi des commandes.

import logging
import time
import traceback

from robby.game_state import GameState
from robby.protocol import Connection
from robby.strategy import Strategy

log = logging.getLogger("robby")


def check_commands(state: GameState, commands: list[dict]) -> list[str]:
    """Erreurs évidentes (qui vaudraient une pénalité). Liste vide si tout va bien."""
    errors = []
    seen = set()
    for cmd in commands:
        robot = state.get_robot(cmd.get("robot_id"))
        if robot is None or robot.team_id != state.team_id:
            errors.append(f"{cmd} : ce robot n'est pas à vous")
            continue
        if robot.id in seen:
            errors.append(f"{cmd} : plusieurs commandes pour le robot {robot.id}")
        seen.add(robot.id)
        if not robot.alive:
            errors.append(f"{cmd} : le robot {robot.id} est détruit")
        action = cmd.get("action")
        if action == "MOVE":
            path = cmd.get("path", [cmd.get("direction")])
            if not isinstance(path, list) or not 1 <= len(path) <= state.speed(robot):
                errors.append(f"{cmd} : chemin de 1 à {state.speed(robot)} "
                              f"case(s) maximum pour un {robot.type}")
        if action == "SHOOT" and robot.type != "K":
            errors.append(f"{cmd} : seul un Destructeur (K) peut tirer")
        if action == "SHIELD" and robot.type != "D":
            errors.append(f"{cmd} : seul un Défenseur (D) peut poser un bouclier")
    return errors


def run(strategy: Strategy, host: str, port: int, name: str) -> None:
    with Connection(host, port, timeout=10) as conn:
        conn.send({"type": "register", "name": name})
        ack = conn.receive()
        if not ack or ack.get("status") != "ok":
            log.error("Inscription refusée par le serveur : %s", ack)
            return

        team_id = ack["team_id"]
        config = {}
        log.info("Inscrit en tant qu'équipe %s (%s). En attente du départ...",
                 team_id, name)

        while True:
            msg = conn.receive()
            if msg is None:
                log.warning("Connexion perdue.")
                return

            msg_type = msg.get("type")

            if msg_type == "game_start":
                config = msg.get("config", {})
                log.info("Partie démarrée !")
                strategy.on_game_start(team_id, config)

            elif msg_type == "game_state":
                if conn.has_pending():
                    # Un message plus récent attend déjà : on a pris du retard
                    # (stratégie trop lente), inutile de répondre à ce tour.
                    log.warning("Tour %s ignoré : réponse trop lente "
                                "(limite : %s s par tour)", msg.get("turn"),
                                config.get("turn_timeout", "?"))
                    continue
                state = GameState(msg, team_id, config)
                started = time.monotonic()
                commands = _safe_decide(strategy, state)
                elapsed = time.monotonic() - started
                limit = config.get("turn_timeout")
                if limit and elapsed > limit:
                    log.warning("Tour %s : decide() a pris %.2f s (limite %s s), "
                                "commandes probablement ignorées",
                                state.turn, elapsed, limit)
                for error in check_commands(state, commands):
                    log.warning("Tour %s : %s", state.turn, error)
                log.debug("Tour %s : %s", state.turn, commands)
                conn.send({"type": "commands", "turn": state.turn,
                           "commands": commands})

            elif msg_type == "turn_result":
                strategy.on_turn_result(msg.get("turn"), msg.get("data", {}))

            elif msg_type == "game_over":
                log.info("Fin de partie : %s", msg)
                strategy.on_game_over(msg)
                return


def _safe_decide(strategy: Strategy, state: GameState) -> list[dict]:
    """Une exception dans la stratégie ne doit pas faire perdre la connexion."""
    try:
        return list(strategy.decide(state) or [])
    except Exception:
        log.error("Erreur dans la stratégie (tour %s) :\n%s",
                  state.turn, traceback.format_exc())
        return []
