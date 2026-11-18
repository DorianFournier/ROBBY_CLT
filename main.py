# main.py
# Lancement du client :
#   uv run main.py --host 192.168.1.10 --name MonEquipe
#   uv run main.py --strategy strategy.random_strategy:RandomStrategy

import argparse
import importlib
import logging

from robby.client import run

DEFAULT_STRATEGY = "strategy.my_strategy:MyStrategy"


def load_strategy(path: str):
    module_name, _, class_name = path.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()


def main():
    parser = argparse.ArgumentParser(description="Client ROBBY")
    parser.add_argument("--host", default="127.0.0.1", help="adresse du serveur")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--name", default="TEAM", help="nom de votre équipe")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY,
                        help="module:Classe de la stratégie à utiliser")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="affiche les commandes envoyées à chaque tour")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(name)s] %(levelname)s %(message)s",
    )
    run(load_strategy(args.strategy), args.host, args.port, args.name)


if __name__ == "__main__":
    main()
