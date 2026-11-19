# robby/client.py
# Boucle principale : connexion, réception de l'état, appel à la
# stratégie, envoi des commandes.

import logging
import random
import time
import traceback

from robby.game_state import GameState
from robby.geometry import is_number
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
        if action not in ("MOVE", "SHOOT", "SHIELD"):
            errors.append(f"{cmd} : action inconnue")
            continue
        if not is_number(cmd.get("angle")):
            errors.append(f"{cmd} : il faut un angle (en degrés)")
            continue
        if action == "MOVE":
            speed, limit = cmd.get("speed"), state.max_speed(robot)
            if not is_number(speed) or not 0 <= speed <= limit:
                errors.append(f"{cmd} : vitesse de 0 à {limit} pour un {robot.type}")
        if action == "SHOOT" and robot.type != "K":
            errors.append(f"{cmd} : seul un Destructeur (K) peut tirer")
        if action == "SHIELD" and robot.type != "D":
            errors.append(f"{cmd} : seul un Défenseur (D) peut poser un bouclier")
        elif action == "SHIELD" and robot.shield_cooldown > 0:
            errors.append(f"{cmd} : bouclier brisé, indisponible encore "
                          f"{robot.shield_cooldown} tour(s) (commande sans effet)")
    return errors


def run(strategy_factory, host: str, port: int, name: str) -> None:
    """
    Se connecte et joue. `strategy_factory()` crée une stratégie NEUVE au
    début de chaque partie (une série peut enchaîner plusieurs parties).
    """
    strategy = None
    games_played = 0
    # placement de départ : lu sur la classe, sinon sur une stratégie d'essai
    placement = getattr(strategy_factory, "placement", None)
    if placement is None:
        placement = getattr(strategy_factory(), "placement", None)
    with Connection(host, port, timeout=10) as conn:
        conn.send({"type": "register", "name": name, "placement": placement})
        ack = conn.receive()
        if not ack or ack.get("status") != "ok":
            log.error("Inscription refusée par le serveur : %s", ack)
            return
        if ack.get("placement_error"):
            log.warning("Placement refusé (%s) : placement par défaut %s",
                        ack["placement_error"], ack.get("placement"))
        elif ack.get("placement"):
            log.info("Placement de départ : %s", ack["placement"])

        team_id = ack["team_id"]
        config = {}
        log.info("Inscrit en tant qu'équipe %s (%s). En attente du départ...",
                 team_id, name)

        while True:
            msg = conn.receive()
            if msg is None:
                if games_played:
                    log.info("Le serveur a fermé la connexion.")
                else:
                    log.warning("Connexion perdue.")
                return

            msg_type = msg.get("type")

            if msg_type == "game_start":
                config = msg.get("config", {})
                team_id = msg.get("team_id", team_id)  # la place peut changer
                seed = msg.get("seed")
                if seed is not None:
                    # Même graine => mêmes tirages aléatoires => même partie
                    random.seed(f"{seed}:{team_id}")
                strategy = strategy_factory()
                if msg.get("games", 1) > 1:
                    log.info("Partie %s/%s démarrée (équipe %s, graine %s)",
                             msg.get("game"), msg.get("games"), team_id, seed)
                else:
                    log.info("Partie démarrée ! (équipe %s, graine %s)",
                             team_id, seed)
                strategy.on_game_start(team_id, config)

            elif msg_type == "game_state" and strategy is not None:
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

            elif msg_type == "turn_result" and strategy is not None:
                strategy.on_turn_result(msg.get("turn"), msg.get("data", {}))

            elif msg_type == "game_over" and strategy is not None:
                games_played += 1
                winner = msg.get("winner")
                verdict = ("VICTOIRE" if winner == team_id
                           else "égalité" if winner is None else "défaite")
                log.info("Fin de partie : %s — scores %s", verdict,
                         msg.get("scores"))
                strategy.on_game_over(msg)

            elif msg_type == "series_over":
                log.info("Fin de la série (%s parties) :", msg.get("games"))
                for row in msg.get("ranking", []):
                    log.info("  %s. %-20s victoires %s/%s  score moyen %s",
                             row["rank"], row["name"], row["wins"], row["games"],
                             row["avg_score"])
                return


def _safe_decide(strategy: Strategy, state: GameState) -> list[dict]:
    """Une exception dans la stratégie ne doit pas faire perdre la connexion."""
    try:
        return list(strategy.decide(state) or [])
    except Exception:
        log.error("Erreur dans la stratégie (tour %s) :\n%s",
                  state.turn, traceback.format_exc())
        return []
