# ROBBY — client

Votre mission : écrire la **stratégie** d'une équipe de 3 robots qui affronte
les autres équipes sur le serveur ROBBY.

Vous ne modifiez **que le dossier `strategy/`**. Le paquet `robby/` s'occupe
du réseau, de la lecture de l'état et de la vérification des commandes.

## Installation et lancement

```bash
uv sync
```

```bash
uv run main.py --host <IP_DU_SERVEUR> --name MonEquipe
```

Options :

| Option | Rôle | Défaut |
|---|---|---|
| `--host` | adresse du serveur | `127.0.0.1` |
| `--port` | port du serveur | `8000` |
| `--name` | nom affiché sur l'écran du serveur (20 caractères max) | `TEAM` |
| `--strategy` | stratégie à charger (`module:Classe`) | `strategy.my_strategy:MyStrategy` |
| `-v` | affiche les commandes envoyées à chaque tour | |

Pour vous entraîner, lancez le serveur en local, puis plusieurs clients dans des
terminaux différents, par exemple votre stratégie contre l'adversaire aléatoire :

```bash
uv run main.py --name Moi
```

```bash
uv run main.py --name Hasard --strategy strategy.random_strategy:RandomStrategy
```

Tests :

```bash
uv run pytest
```

## Les règles

La carte fait 15 × 15 cases. `x` va de 0 (gauche) à 14, `y` de 0 (**haut**) à 14.
Les distances se comptent en nombre de déplacements, **diagonales comprises** :
`distance = max(|dx|, |dy|)`.

Chaque équipe a une **base** au milieu d'un bord de la carte et trois robots :

| Type | Nom | Capacité |
|---|---|---|
| `R` | Radar | Détecte les ennemis à 3 cases ou moins. Seul robot pouvant ramasser l'élément. |
| `D` | Défenseur | Pose un bouclier qui couvre 3 cases sur un côté (`SU`, `SR`, `SD`, `SL`). Le bouclier reste en place et bloque les tirs **et** les déplacements. |
| `K` | Destructeur | Tire sur un ennemi à 3 cases ou moins. |

**Brouillard de guerre** : vous ne voyez que vos robots et les ennemis détectés
par **vos** radars. Un radar détruit, c'est une équipe aveugle.

### Déroulement d'un tour

Toutes les équipes envoient leurs commandes, puis le serveur les applique
**en même temps**, à partir de l'état du début du tour :

1. les tirs sont résolus : les robots touchés sont détruits (deux destructeurs
   peuvent s'éliminer mutuellement) ;
2. les robots survivants se déplacent. Si deux robots visent la même case,
   aucun des deux ne bouge. Une case accueille au plus 2 robots ;
3. les boucliers sont posés.

### Phase 1 — Capture (100 tours au maximum)

Un élément est placé au centre de la carte. Le premier radar qui le ramasse puis
le **ramène sur sa base** termine la phase 1. Son équipe reçoit alors un
**second destructeur**. Un robot détruit pendant cette phase réapparaît près de
sa base 5 tours plus tard.

### Phase 2 — Match à mort (100 tours au maximum)

Les robots détruits **ne réapparaissent plus**. La partie s'arrête quand il ne
reste qu'une seule équipe ou quand le nombre de tours est atteint.

### Score

C'est le **score total** qui désigne le vainqueur. Chaque robot ennemi détruit
rapporte :

| Cible | Points |
|---|---|
| Destructeur `K` | 250 |
| Défenseur `D` | 500 |
| Radar `R` | 750 |
| Radar portant l'élément | 1000 |

### Pénalités

Une commande invalide **pénalise le robot qui l'a reçue** pendant 3 tours :
pendant ce temps, ses commandes sont ignorées. Une commande est invalide dans
ces cas :

- un robot détruit, une action inconnue ou une direction inconnue ;
- plusieurs commandes pour le même robot dans le même tour ;
- un déplacement hors de la carte ou sur une case couverte par un bouclier ;
- un tir qui ne vient pas d'un `K`, ou qui vise un allié, une cible morte ou
  une cible hors de portée ;
- un bouclier posé par un robot qui n'est pas un `D`.

Un tir **arrêté par un bouclier** n'est pas une faute : il rate, simplement.

## Écrire sa stratégie

Ouvrez `strategy/my_strategy.py`. La méthode `decide(state)` est appelée à
chaque tour et retourne une liste de commandes :

```python
from robby import move, shoot, shield

move(robot, "UR")        # U, UR, R, DR, D, DL, L, UL
shoot(destructeur, cible)
shield(defenseur, "SL")  # SU, SR, SD, SL
```

La classe garde la même instance pendant toute la partie : vous pouvez stocker
des informations dans `self`, par exemple la dernière position connue des
ennemis. Les méthodes `on_game_start`, `on_turn_result` et `on_game_over`
vous informent de ce qui se passe (voir `robby/strategy.py`).

### Ce que contient `state` (un objet `GameState`)

| Attribut / méthode | Description |
|---|---|
| `state.turn`, `state.phase`, `state.phase_turn` | numéro du tour, de la phase (1 ou 2), du tour dans la phase |
| `state.my_robots` | vos robots vivants |
| `state.enemies` | ennemis vivants **visibles** |
| `state.element` | `.pos`, `.is_free`, `.carried_by_id` |
| `state.my_base`, `state.base_of(team_id)` | positions des bases |
| `state.possible_moves(robot)` | directions valides d'après ce que vous voyez |
| `state.direction_towards(robot, (x, y))` | meilleure direction pour s'approcher d'une case |
| `state.targets_in_range(k)` | ennemis visibles à portée et non protégés |
| `state.nearest(robot, robots)` | le robot le plus proche dans une liste |
| `state.shield_cells()` | cases couvertes par les boucliers visibles |
| `state.config` | paramètres de la partie envoyés par le serveur |

Chaque `Robot` a les attributs `id`, `team_id`, `type`, `x`, `y`, `pos`,
`alive`, `shield_direction`, `carrying_element`, `penalty`, ainsi que
`can_act` (vivant et sans pénalité) et `distance_to(...)`.

Avant chaque envoi, le client vérifie les erreurs évidentes et les affiche en
`WARNING`. Une exception levée dans votre stratégie est affichée, et vous
passez simplement le tour : la connexion n'est pas perdue.

## Protocole (pour les curieux)

Le client et le serveur échangent des messages JSON par TCP, **un message par
ligne** :

```
client → {"type": "register", "name": "MonEquipe"}
serveur → {"type": "register_ack", "status": "ok", "team_id": 2}
serveur → {"type": "game_start", "team_id": 2, "config": {...}}
à chaque tour :
  serveur → {"type": "game_state", "turn", "phase", "phase_turn", "robots": [...], "element": {...}}
  client  → {"type": "commands", "commands": [...]}
  serveur → {"type": "turn_result", "turn", "data": {"moves", "shots", "deaths", "shields", "penalties"}}
serveur → {"type": "game_over", "winner": 2, "scores": {...}}
```
