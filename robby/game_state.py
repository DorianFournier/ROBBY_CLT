# robby/game_state.py
# Modèles de données côté client, reconstruits à partir des messages du serveur.
#
# Repère : x de 0 (gauche) à map_width - 1, y de 0 (HAUT) à map_height - 1.
# Distance : on compte en nombre de cases, diagonales comprises
#            (distance de Tchebychev = max(|dx|, |dy|)).

from robby.constants import DEFAULT_CONFIG, DIRECTIONS

Position = tuple[int, int]


class Robot:
    def __init__(self, data: dict):
        self.id: int = data["id"]
        self.team_id: int = data["team"]
        self.type: str = data["type"]  # "R", "D" ou "K"
        self.x: int = data["x"]
        self.y: int = data["y"]
        self.alive: bool = data["alive"]
        self.shield_direction: str | None = data.get("shield")
        self.carrying_element: bool = data.get("carrying_element", False)
        self.penalty: int = data.get("penalty", 0)

    @property
    def pos(self) -> Position:
        return (self.x, self.y)

    @property
    def can_act(self) -> bool:
        """Vivant et non pénalisé : une commande pour ce robot sera prise en compte."""
        return self.alive and self.penalty == 0

    def distance_to(self, other: "Robot | Position") -> int:
        return distance(self.pos, other.pos if isinstance(other, Robot) else other)

    def __repr__(self):
        return (f"Robot(id={self.id}, team={self.team_id}, type={self.type}, "
                f"pos=({self.x}, {self.y}), alive={self.alive})")


class Element:
    def __init__(self, data: dict):
        self.x: int = data["x"]
        self.y: int = data["y"]
        self.carried_by_id: int | None = data["carried_by_id"]

    @property
    def pos(self) -> Position:
        return (self.x, self.y)

    @property
    def is_free(self) -> bool:
        return self.carried_by_id is None


def distance(a: Position, b: Position) -> int:
    """Nombre de déplacements (diagonales comprises) pour aller de a à b."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def step(pos: Position, direction: str) -> Position:
    """Case atteinte en partant de `pos` dans `direction`."""
    dx, dy = DIRECTIONS[direction]
    return (pos[0] + dx, pos[1] + dy)


def direction_to(src: Position, dst: Position) -> str | None:
    """Direction (parmi les 8) qui rapproche le plus de dst. None si src == dst."""
    dx = (dst[0] > src[0]) - (dst[0] < src[0])
    dy = (dst[1] > src[1]) - (dst[1] < src[1])
    for name, vector in DIRECTIONS.items():
        if vector == (dx, dy):
            return name
    return None


class GameState:
    """
    État du jeu tel que vu par VOTRE équipe à un tour donné.

    Attention au brouillard de guerre : `robots` contient vos robots
    (vivants ou morts) et SEULEMENT les ennemis détectés par vos radars.
    """

    def __init__(self, msg: dict, team_id: int, config: dict | None = None):
        self.team_id = team_id
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        self.turn: int = msg["turn"]
        self.phase: int = msg["phase"]
        self.phase_turn: int = msg.get("phase_turn", msg["turn"])
        self.element = Element(msg["element"])
        self.robots = [Robot(r) for r in msg.get("robots", [])]

        self.map_width: int = self.config["map_width"]
        self.map_height: int = self.config["map_height"]

    # ------------------------------------------------------------------
    # Robots
    # ------------------------------------------------------------------

    @property
    def my_robots(self) -> list[Robot]:
        """Vos robots vivants."""
        return [r for r in self.robots if r.team_id == self.team_id and r.alive]

    @property
    def enemies(self) -> list[Robot]:
        """Ennemis vivants actuellement détectés par vos radars."""
        return [r for r in self.robots if r.team_id != self.team_id and r.alive]

    def my_robots_of_type(self, robot_type: str) -> list[Robot]:
        return [r for r in self.my_robots if r.type == robot_type]

    def get_robot(self, robot_id: int) -> Robot | None:
        return next((r for r in self.robots if r.id == robot_id), None)

    def robots_at(self, pos: Position) -> list[Robot]:
        """Robots vivants VISIBLES sur une case."""
        return [r for r in self.robots if r.alive and r.pos == pos]

    @staticmethod
    def nearest(origin: Robot | Position, candidates: list[Robot]) -> Robot | None:
        if not candidates:
            return None
        pos = origin.pos if isinstance(origin, Robot) else origin
        return min(candidates, key=lambda r: distance(pos, r.pos))

    # ------------------------------------------------------------------
    # Carte
    # ------------------------------------------------------------------

    def is_inside(self, pos: Position) -> bool:
        return 0 <= pos[0] < self.map_width and 0 <= pos[1] < self.map_height

    def base_of(self, team_id: int) -> Position | None:
        """Base d'une équipe (centre d'un bord de la carte)."""
        bases = self.config.get("bases") or {}
        base = bases.get(str(team_id)) or bases.get(team_id)
        if base:
            return tuple(base)
        cx, cy = self.map_width // 2, self.map_height // 2
        return {
            1: (0, cy),
            2: (self.map_width - 1, cy),
            3: (cx, 0),
            4: (cx, self.map_height - 1),
        }.get(team_id)

    @property
    def my_base(self) -> Position:
        return self.base_of(self.team_id)

    # ------------------------------------------------------------------
    # Boucliers / déplacements
    # ------------------------------------------------------------------

    @staticmethod
    def shield_cells_of(robot: Robot) -> list[Position]:
        """Les 3 cases couvertes par le bouclier d'un défenseur."""
        x, y = robot.x, robot.y
        return {
            "SL": [(x - 1, y - 1), (x - 1, y), (x - 1, y + 1)],
            "SR": [(x + 1, y - 1), (x + 1, y), (x + 1, y + 1)],
            "SU": [(x - 1, y - 1), (x, y - 1), (x + 1, y - 1)],
            "SD": [(x - 1, y + 1), (x, y + 1), (x + 1, y + 1)],
        }.get(robot.shield_direction, [])

    def shield_cells(self, only_enemies: bool = True) -> set[Position]:
        """
        Cases couvertes par les boucliers VISIBLES.

        Un bouclier ne bloque que les ennemis de son défenseur : par défaut
        on ne renvoie donc que les boucliers ENNEMIS (ceux qui vous gênent).
        `only_enemies=False` renvoie aussi les vôtres.
        """
        cells = set()
        for r in self.robots:
            if not (r.alive and r.type == "D" and r.shield_direction):
                continue
            if only_enemies and r.team_id == self.team_id:
                continue
            cells.update(self.shield_cells_of(r))
        return {c for c in cells if self.is_inside(c)}

    def can_move(self, robot: Robot, direction: str) -> bool:
        """
        True si le déplacement est valide d'après ce que vous voyez.
        (Un ennemi invisible peut encore occuper la case.)
        """
        target = step(robot.pos, direction)
        if not self.is_inside(target):
            return False
        if target in self.shield_cells():
            return False
        return len(self.robots_at(target)) < self.config["max_robots_per_cell"]

    def possible_moves(self, robot: Robot) -> list[str]:
        return [d for d in DIRECTIONS if self.can_move(robot, d)]

    def direction_towards(self, robot: Robot, target: Position) -> str | None:
        """
        Meilleure direction VALIDE pour se rapprocher de `target`
        (None si déjà sur place ou bloqué).
        """
        moves = self.possible_moves(robot)
        if robot.pos == target or not moves:
            return None
        def cost(d):
            x, y = step(robot.pos, d)
            # à distance égale, préférer la trajectoire la plus directe
            return distance((x, y), target), abs(x - target[0]) + abs(y - target[1])

        best = min(moves, key=cost)
        if distance(step(robot.pos, best), target) >= robot.distance_to(target):
            return None
        return best

    # ------------------------------------------------------------------
    # Tir
    # ------------------------------------------------------------------

    def in_range(self, shooter: Robot, target: Robot) -> bool:
        return shooter.distance_to(target) <= self.config["destructor_range"]

    def is_shot_blocked(self, shooter: Robot, target: Robot) -> bool:
        """True si un bouclier ennemi visible se trouve sur la trajectoire du tir."""
        shields = self.shield_cells()
        dx, dy = target.x - shooter.x, target.y - shooter.y
        steps = max(abs(dx), abs(dy))
        if steps == 0:
            return False
        # Même calcul que le serveur (pour obtenir exactement les mêmes cases)
        step_x, step_y = dx / steps, dy / steps
        for i in range(1, steps + 1):
            cell = (round(shooter.x + step_x * i), round(shooter.y + step_y * i))
            if cell in shields:
                return True
        return False

    def targets_in_range(self, shooter: Robot) -> list[Robot]:
        """Ennemis visibles à portée et non protégés par un bouclier ennemi visible."""
        return [
            e for e in self.enemies
            if self.in_range(shooter, e) and not self.is_shot_blocked(shooter, e)
        ]
