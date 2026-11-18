"""Bots de référence, du plus simple au plus fort.

Ils servent d'adversaires d'entraînement et de paliers :
    bot1  RandomBot    joue au hasard (sans faute de règle)
    bot2  RusherBot    fonce : Radar sur l'élément, Destructeur sur l'ennemi
    bot3  TacticianBot protège son Radar avec le bouclier, escorte, se replie,
                       mémorise les ennemis et choisit ses cibles
    bot4  FreeSimulatorBot (mode libre uniquement) essaie des centaines de
                       plans dans un simulateur de tour et garde le meilleur

Chaque bot existe pour les deux versions du jeu (dossier bots/) :
    mode grille : level1_random, level2_rusher, level3_tactician
    mode libre  : free_random, free_rusher, free_tactician
`--strategy bot2` choisit automatiquement selon le mode du serveur.

Lancement : uv run main.py --strategy bot2
"""

from functools import partial

from bots.free_random import FreeRandomBot
from bots.free_rusher import FreeRusherBot
from bots.free_simulator import FreeSimulatorBot
from bots.free_tactician import FreeTacticianBot
from bots.level1_random import RandomBot
from bots.level2_rusher import RusherBot
from bots.level3_tactician import TacticianBot
from robby.strategy import ByMode

BOTS = {
    "bot1": partial(ByMode, RandomBot, FreeRandomBot),
    "bot2": partial(ByMode, RusherBot, FreeRusherBot),
    "bot3": partial(ByMode, TacticianBot, FreeTacticianBot),
    "bot4": FreeSimulatorBot,     # mode libre uniquement
}

__all__ = ["BOTS", "RandomBot", "RusherBot", "TacticianBot",
           "FreeRandomBot", "FreeRusherBot", "FreeTacticianBot", "FreeSimulatorBot"]
