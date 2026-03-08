# client.py
# Boucle principale : connexion au serveur, réception de l'état,
# appel à la stratégie, envoi des commandes.

# client.py
import socket
import sys
from protocol import send_json, receive_json
from game_state import GameState
from strategy.my_strategy import decide

HOST = "127.0.0.1"
PORT = 8000

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))

        # Handshake
        send_json(sock, {"type": "register"})
        ack = receive_json(sock)

        if not ack or ack.get("status") != "ok":
            print("Connexion refusée")
            return

        team_id = ack["team_id"]
        print(f"[CLIENT] Connecté en tant que team {team_id}")

        # Attendre le signal de démarrage
        start = receive_json(sock)
        if not start or start.get("type") != "game_start":
            print("Signal de démarrage non reçu")
            return

        print("[CLIENT] Partie démarrée !")

        while True:
            msg = receive_json(sock)
            print(f"MESSAGE : {msg}\n\n")
            if msg is None:
                print("[CLIENT] Connexion perdue.")
                break

            msg_type = msg.get("type")

            if msg_type == "game_over":
                print(f"[CLIENT] Fin : {msg.get('message')}")
                break

            if msg_type == "turn_result":
                continue  # optionnel, pour log

            if msg_type == "game_state":
                state = GameState(msg)

                if state.penalty_remaining > 0:
                    send_json(sock, {"type": "commands", "commands": []})
                    continue

                commands = decide(state, team_id)
                print(f"[CLIENT] Tour {state.turn} — {len(commands)} commandes")
                send_json(sock, {"type": "commands", "commands": commands})

if __name__ == "__main__":
    main()