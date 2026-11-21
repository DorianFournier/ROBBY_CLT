"""Framework client ROBBY : connexion au serveur, état du jeu, commandes.

Vous n'avez normalement PAS besoin de modifier ce paquet :
votre code va dans le dossier `strategy/`.
"""

from robby.commands import move, shield, shoot, stop
from robby.game_state import Element, GameState, Robot

# Version de compatibilité avec le dépôt du serveur (son dossier ia/ et
# prof/ utilisent ce client). À augmenter quand le serveur a besoin d'une
# nouveauté du client ; le serveur indique alors de mettre le client à jour.
COMPATIBILITE = 1

__all__ = ["GameState", "Robot", "Element", "move", "shoot", "shield", "stop"]
