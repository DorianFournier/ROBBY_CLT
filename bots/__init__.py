"""Bots de référence, du plus simple au plus fort.

Ils servent d'adversaires d'entraînement et de paliers :
    bot1  RandomBot    joue au hasard (sans faute de règle)
    bot2  RusherBot    fonce : Radar sur l'élément, Destructeur sur l'ennemi
    bot3  TacticianBot protège son Radar avec le bouclier, escorte, se replie,
                       mémorise les ennemis et choisit ses cibles

Lancement : uv run main.py --strategy bot2
"""

from bots.level1_random import RandomBot
from bots.level2_rusher import RusherBot
from bots.level3_tactician import TacticianBot

BOTS = {
    "bot1": RandomBot,
    "bot2": RusherBot,
    "bot3": TacticianBot,
}

__all__ = ["BOTS", "RandomBot", "RusherBot", "TacticianBot"]
