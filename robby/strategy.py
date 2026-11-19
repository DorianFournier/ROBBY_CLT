# robby/strategy.py
# Classe de base dont hérite votre stratégie.


class Strategy:
    """
    Héritez de cette classe et redéfinissez `decide`.

    Une même instance est utilisée pendant toute la partie : vous pouvez
    stocker des informations d'un tour sur l'autre dans `self`
    (dernières positions ennemies connues, plan en cours...).
    """

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

