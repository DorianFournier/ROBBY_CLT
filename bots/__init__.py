"""Bots de référence, du plus simple au plus fort.

Ils servent d'adversaires d'entraînement et de paliers :
    bot1  RandomBot     joue au hasard (sans faute de règle)
    bot2  RusherBot     fonce : Radar sur la batterie, Destructeur sur l'ennemi
    bot3  TacticianBot  tient le centre, avance derrière son Défenseur,
                        contourne ou use les boucliers, mémorise les ennemis
    bot4  SimulatorBot  essaie des centaines de plans dans un simulateur de
                        tour et garde le meilleur

Lancement : uv run main.py --strategy bot2
"""

from bots.level1_random import RandomBot
from bots.level2_rusher import RusherBot
from bots.level3_tactician import TacticianBot
from bots.level4_simulator import SimulatorBot

BOTS = {
    "bot1": RandomBot,
    "bot2": RusherBot,
    "bot3": TacticianBot,
    "bot4": SimulatorBot,
}

__all__ = ["BOTS", "RandomBot", "RusherBot", "TacticianBot", "SimulatorBot"]
