# robby/strategy.py
# Classe de base dont hérite votre stratégie.


class Strategy:
    """
    Héritez de cette classe et redéfinissez `decide`.

    Une même instance est utilisée pendant toute la partie : vous pouvez
    stocker des informations d'un tour sur l'autre dans `self`
    (dernières positions ennemies connues, plan en cours...).

    `modes` : versions du jeu que la stratégie sait jouer ("grille" et/ou
    "libre"). Le client prévient si le serveur joue dans un autre mode.
    """

    modes = ("grille",)

    def on_game_start(self, team_id: int, config: dict) -> None:
        """Appelée une fois au début de la partie."""

    def decide(self, state) -> list[dict]:
        """
        Appelée à chaque tour. Retourne la liste des commandes
        (au plus une par robot), construites avec robby.move / shoot / shield.
        """
        raise NotImplementedError

    def on_turn_result(self, turn: int, result: dict) -> None:
        """Appelée après chaque tour avec ce qui s'est passé (tous les tirs,
        déplacements, morts...)."""

    def on_game_over(self, message: dict) -> None:
        """Appelée en fin de partie (scores, vainqueur)."""


class ByMode(Strategy):
    """Joue `grid_class()` en mode grille et `free_class()` en mode libre
    (le mode est connu au début de chaque partie)."""

    modes = ("grille", "libre")

    def __init__(self, grid_class, free_class):
        self.grid_class, self.free_class = grid_class, free_class
        self.delegate = grid_class()

    def on_game_start(self, team_id, config):
        free = config.get("mode") == "libre"
        self.delegate = self.free_class() if free else self.grid_class()
        self.delegate.on_game_start(team_id, config)

    def decide(self, state):
        return self.delegate.decide(state)

    def on_turn_result(self, turn, result):
        self.delegate.on_turn_result(turn, result)

    def on_game_over(self, message):
        self.delegate.on_game_over(message)
