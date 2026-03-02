# Modèles de données côté client.
# Reconstruits à partir des JSON reçus du serveur.


class Robot:
    def __init__(self, data: dict):
        self.id = data["id"]
        self.team_id = data["team"]
        self.type = data["type"]  # "R", "K", "D"
        self.x = data["x"]
        self.y = data["y"]
        self.alive = data["alive"]
        self.shield_direction = data["shield"]
        self.carrying_element = data["carrying_element"]

    def __repr__(self):
        return f"Robot(id={self.id}, team={self.team_id}, type={self.type}, pos=({self.x},{self.y}))"


class Element:
    def __init__(self, data: dict):
        self.x = data["x"]
        self.y = data["y"]
        self.carried_by_id = data["carried_by_id"]


class GameState:
    """
    Représente l'état du jeu tel que reçu du serveur pour une équipe.
    Contient uniquement les robots visibles (alliés + ennemis détectés par radar).
    """

    def __init__(self, msg: dict):
        self.turn = msg["turn"]
        self.phase = msg["phase"]
        self.penalty_remaining = msg["penalty_remaining"]
        self.element = Element(msg["element"])

        robots_data = msg.get("robots", [])
        self.robots = [Robot(r) for r in robots_data]

    def get_my_robots(self, team_id: int) -> list[Robot]:
        return [r for r in self.robots if r.team_id == team_id and r.alive]

    def get_visible_enemies(self, team_id: int) -> list[Robot]:
        return [r for r in self.robots if r.team_id != team_id and r.alive]

    def get_robot_by_id(self, robot_id: int) -> Robot | None:
        return next((r for r in self.robots if r.id == robot_id), None)
