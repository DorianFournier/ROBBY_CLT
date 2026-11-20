# robby/constants.py
# Constantes du jeu côté client.
# Les valeurs numériques (taille de l'arène, portées...) sont envoyées par le
# serveur au démarrage (message game_start) : celles-ci ne sont que des
# valeurs par défaut.

ROBOT_TYPES = {
    "R": "Radar",       # détecte les ennemis (seul robot qui voit)
    "C": "Collecteur",  # ramasse et rapporte les batteries (le plus lent)
    "D": "Défenseur",   # pose un bouclier
    "K": "Destructeur", # tire
}

SPAWN_STEP = 1000   # écart entre les positions de départ (bases au milieu des côtés)

DEFAULT_CONFIG = {
    "map_width": 15000,
    "map_height": 15000,
    "radar_range": 3000,
    "destructor_range": 3000,
    "move_speed": {"R": 1500, "C": 1000, "D": 2000, "K": 3000},   # vitesse max par tour
    "robot_radius": 300,
    "shield_radius": 1500,
    "shield_arc": 90,
    "pickup_radius": 500,
    "base_radius": 700,
    "phase1_turns": 60,
    "phase2_turns": 100,
    "respawn_delay": 3,
    "penalty_turns": 3,
    "kill_points": {"K": 250, "D": 500, "C": 500, "R": 750, "CE": 1000},
    "capture_points": 500,         # batterie ramenée à la base
    "survivor_points": 300,        # par robot en vie en fin de partie
    "battery_respawn_delay": 3,    # tours avant qu'une batterie capturée revienne
    "shield_hp": 3,             # résistance d'un bouclier (tirs arrêtés)
    "shield_break_turns": 4,    # tours sans bouclier quand il est brisé
    "shield_recharge_delay": 3, # tours sans impact avant de regagner 1 point
    # déchèterie (phase 2) : voir le README
    "dump_enabled": True,
    "grab_radius": 700,         # contact pour attraper un ennemi à l'arrêt
    "carry_speed": 600,         # vitesse max d'un Collecteur chargé
    "dump_radius": 700,         # rayon de la déchèterie
    "dump_points": {"K": 375, "D": 750, "C": 750, "R": 1125},
    "bases": {},
    "teams": {},
}
