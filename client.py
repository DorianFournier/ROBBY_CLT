# client.py
# Boucle principale : connexion au serveur, réception de l'état,
# appel à la stratégie, envoi des commandes.

import socket
import sys
from protocol import send_json, receive_json
from game_state import GameState
from strategy.my_strategy import decide

HOST = "127.0.0.1"
PORT = 5555


def main():
    team_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    print(f"[CLIENT] Connexion au serveur {HOST}:{PORT} en tant que team {team_id}...")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        print("[CLIENT] Connecté.")

        # Handshake : envoyer l'identifiant d'équipe
        send_json(sock, {"type": "hello", "team_id": team_id})

        while True:
            msg = receive_json(sock)

            if msg is None:
                print("[CLIENT] Connexion perdue.")
                break

            msg_type = msg.get("type")

            # ── Fin de partie ──
            if msg_type == "game_over":
                print(f"[CLIENT] Partie terminée : {msg.get('message')}")
                break

            # ── Résultat du tour précédent (optionnel, pour log) ──
            if msg_type == "turn_result":
                _log_turn_result(msg)
                continue

            # ── État du jeu : calculer et envoyer les commandes ──
            if msg_type == "game_state":
                state = GameState(msg)

                if state.penalty_remaining > 0:
                    print(f"[CLIENT] Pénalité active ({state.penalty_remaining} tours)")
                    send_json(sock, {"type": "commands", "commands": []})
                    continue

                commands = decide(state, team_id)

                print(
                    f"[CLIENT] Tour {state.turn} | Phase {state.phase} | {len(commands)} commandes"
                )
                for cmd in commands:
                    print(f"  → {cmd}")

                send_json(sock, {"type": "commands", "commands": commands})


def _log_turn_result(msg: dict):
    data = msg.get("data", {})
    turn = msg.get("turn")
    moves = data.get("moves", [])
    deaths = data.get("deaths", [])
    shots = data.get("shots", [])
    shields = data.get("shields", [])

    print(
        f"[RÉSULTAT tour {turn}] "
        f"moves={len(moves)} shots={len(shots)} "
        f"deaths={deaths} shields={len(shields)}"
    )


if __name__ == "__main__":
    main()
