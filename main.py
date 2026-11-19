# main.py
# Lancement du client :
#   uv run main.py --host 192.168.1.10 --name MonEquipe
#   uv run main.py --strategy bot2                (bot de référence niveau 2)
#   uv run main.py --strategy strategy.autre:AutreStrategie
# Sans --strategy : votre stratégie, celle du mode du serveur
# (strategy/my_free_strategy.py en mode libre, le mode par défaut ;
#  strategy/my_strategy.py si le serveur est lancé avec --mode grille).

import argparse
import importlib
import logging

from robby.client import run

DEFAULT_STRATEGY = "mine"


def load_strategy(path: str):
    """`mine` (votre stratégie), `bot1` à `bot4`, ou `module:Classe`."""
    from bots import BOTS

    if path == DEFAULT_STRATEGY:
        # Votre stratégie, selon le mode choisi par le serveur :
        # mode libre -> strategy/my_free_strategy.py, grille -> my_strategy.py
        from robby.strategy import ByMode
        from strategy.my_free_strategy import MyFreeStrategy
        from strategy.my_strategy import MyStrategy
        return ByMode(MyStrategy, MyFreeStrategy)
    if path in BOTS:
        return BOTS[path]()
    module_name, _, class_name = path.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()


def main():
    parser = argparse.ArgumentParser(description="Client ROBBY")
    parser.add_argument("--host", default="127.0.0.1", help="adresse du serveur")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--name", default="TEAM", help="nom de votre équipe")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY,
                        help="mine (défaut : votre stratégie, selon le mode du "
                             "serveur), bot1, bot2, bot3 (les deux modes), "
                             "bot4 (mode libre) ou module:Classe")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="affiche les commandes envoyées à chaque tour")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(name)s] %(levelname)s %(message)s",
    )
    load_strategy(args.strategy)  # erreur immédiate si la stratégie est introuvable
    run(lambda: load_strategy(args.strategy), args.host, args.port, args.name)


if __name__ == "__main__":
    main()
