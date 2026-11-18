# robby/constants.py
# Constantes du jeu côté client.
# Les valeurs numériques (taille de carte, portées...) sont envoyées par le
# serveur au démarrage (message game_start) : celles-ci ne sont que des
# valeurs par défaut.

# Déplacements : direction -> (dx, dy). Y augmente vers le BAS.
DIRECTIONS = {
    "U": (0, -1),
    "UR": (1, -1),
    "R": (1, 0),
    "DR": (1, 1),
    "D": (0, 1),
    "DL": (-1, 1),
    "L": (-1, 0),
    "UL": (-1, -1),
}

# Boucliers (Défenseur uniquement) : côté protégé
SHIELD_DIRECTIONS = ["SU", "SR", "SD", "SL"]

ROBOT_TYPES = {
    "R": "Radar",       # détecte les ennemis, ramasse l'élément
    "D": "Défenseur",   # pose un bouclier
    "K": "Destructeur", # tire
}

DEFAULT_CONFIG = {
    "map_width": 15,
    "map_height": 15,
    "max_robots_per_cell": 2,
    "radar_range": 3,
    "destructor_range": 3,
    "phase1_turns": 100,
    "phase2_turns": 100,
    "respawn_delay": 5,
    "penalty_turns": 3,
    "kill_points": {"K": 250, "D": 500, "R": 750, "RE": 1000},
    "move_speed": {"K": 3, "D": 2, "R": 1},  # cases par tour
    "capture_points": 0,   # bonus pour avoir ramené l'élément
    "survivor_points": 0,  # bonus par robot en vie en fin de partie
    "bases": {},
    "teams": {},
}
