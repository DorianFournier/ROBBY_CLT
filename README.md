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
| `--strategy` | `bot1`, `bot2`, `bot3` (bots de référence) ou `module:Classe` | `strategy.my_strategy:MyStrategy` |
| `-v` | affiche les commandes envoyées à chaque tour | |

Pour vous entraîner, lancez le serveur en local, puis plusieurs clients dans des
terminaux différents, par exemple votre stratégie contre un bot de référence :

```bash
uv run main.py --name Moi
```

```bash
uv run main.py --name Bot2 --strategy bot2
```

Tests :

```bash
uv run pytest
```

## Bots de référence (paliers)

Le dossier `bots/` contient trois adversaires d'entraînement, du plus faible au
plus fort. Le but est de les battre l'un après l'autre.

| Option | Bot | Comportement |
|---|---|---|
| `bot1` | `RandomBot` | Joue au hasard, mais sans faute de règle. |
| `bot2` | `RusherBot` | « Fonceur » : le Radar va droit sur l'élément, le Destructeur tire sur l'ennemi le plus proche ou lui fonce dessus et reste près de son Radar s'il ne voit personne, le Défenseur suit le Radar. Aucune prudence, aucune mémoire. |
| `bot3` | `TacticianBot` | « Tacticien » : le groupe se déplace autour du Radar. Le Défenseur sert de garde du corps (il se place entre le Radar et la menace, bouclier tourné vers elle), le Radar recule s'il est exposé, les Destructeurs restent sur ses flancs (dans sa zone de vision) et choisissent leurs cibles. En phase 2, il tient sa position : avec le brouillard de guerre, celui qui attend voit l'autre arriver en premier. Il mémorise les ennemis et leurs boucliers, même quand ils sortent de la vue. |

Mesuré sur 60 parties en 1 contre 1 (côtés alternés, avec 10 % d'actions
aléatoires des deux côtés pour que les parties soient toutes différentes) :
`bot2` bat `bot1` 55 fois, `bot3` bat `bot2` 51 fois et `bot3` bat `bot1`
52 fois.

Lire leur code (`bots/level2_rusher.py`, `bots/level3_tactician.py`) est une
bonne source d'idées... mais pour les battre, il faudra faire mieux !

## S'entraîner sur des dizaines de parties

Le serveur (dépôt ROBBY) peut enchaîner des parties **sans affichage** et
afficher un classement. C'est le meilleur moyen de savoir si une modification
de votre stratégie l'améliore vraiment :

```bash
uv run python -m server.server --headless --games 20 --teams 3
```

Lancez cette commande dans le dossier ROBBY. Ensuite, dans le dossier
robby_clt, démarrez trois clients, chacun dans son terminal :

```bash
uv run main.py --name Moi
```

```bash
uv run main.py --name Bot2 --strategy bot2
```

```bash
uv run main.py --name Bot3 --strategy bot3
```

Les places sur la carte tournent d'une partie à l'autre. Chaque partie affiche
sa graine : pour **rejouer à l'identique** une partie perdue (et comprendre
pourquoi), relancez le serveur avec `--headless --games 1 --seed <graine>` et
les mêmes clients.

Pour **revoir** une partie en détail, ajoutez `--record replays` à la commande
du serveur. Ouvrez ensuite le fichier de la partie avec le lecteur du dépôt
ROBBY :

```bash
uv run python -m ui.replay replays/<fichier>.json
```

Avec `Espace` (pause), `←` / `→` (tour par tour) et `↑` / `↓` (vitesse), vous
voyez la partie et les commandes envoyées par chaque équipe à chaque tour.

## Les règles

La carte fait 15 × 15 cases. `x` va de 0 (gauche) à 14, `y` de 0 (**haut**) à 14.
Les distances se comptent en nombre de déplacements, **diagonales comprises** :
`distance = max(|dx|, |dy|)`.

Chaque équipe a une **base** au milieu d'un bord de la carte et trois robots :

| Type | Nom | Vitesse | Capacité |
|---|---|---|---|
| `R` | Radar | 1 case par tour | Détecte les ennemis à 3 cases ou moins. Seul robot pouvant ramasser l'élément. |
| `D` | Défenseur | 2 cases par tour | Pose un bouclier qui couvre 3 cases sur un côté (`SU`, `SR`, `SD`, `SL`). |
| `K` | Destructeur | 3 cases par tour | Tire sur un ennemi à 3 cases ou moins. |

### Déplacements

Un déplacement est un **chemin** : une direction par case parcourue, sans
dépasser la vitesse du robot. Par exemple, `move(k, "R", "R", "UR")` fait
avancer un K de 3 cases. Chaque case du chemin doit être dans la carte et hors
des boucliers ennemis. Les robots se croisent librement en chemin : seule la
case d'arrivée compte (2 robots au maximum par case).

### Boucliers

Un bouclier couvre les 3 cases d'un côté du Défenseur. Par exemple, `SR`
protège les cases `(x+1, y-1)`, `(x+1, y)` et `(x+1, y+1)`. Il reste en place
tant que le Défenseur ne change pas son orientation, et il **suit le Défenseur
quand celui-ci se déplace**. Il ne gêne que les **ennemis** :

- un tir ennemi qui traverse une case du bouclier est arrêté ;
- un robot ennemi ne peut pas entrer sur une case du bouclier ;
- vos propres robots traversent librement votre bouclier, et vos tirs aussi.

**Brouillard de guerre** : vous ne voyez que vos robots et les ennemis détectés
par **vos** radars. Un radar détruit, c'est une équipe aveugle.

### Déroulement d'un tour

Toutes les équipes reçoivent l'état du jeu et ont **3 secondes** pour répondre
(`state.config["turn_timeout"]`). Une équipe qui répond trop tard ne joue pas ce
tour : ses robots restent immobiles. Le client vous prévient par un `WARNING`
si votre `decide()` est trop lent.

Le serveur applique ensuite toutes les commandes **en même temps**, à partir
de l'état du début du tour :

1. les tirs sont résolus : les robots touchés sont détruits (deux destructeurs
   peuvent s'éliminer mutuellement) ;
2. les robots survivants suivent leur chemin. Si deux robots visent la même
   case d'arrivée, aucun des deux ne bouge. Une case accueille au plus 2 robots ;
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

C'est le **score total** qui désigne le vainqueur. **Attention : une équipe dont
le client se déconnecte (plantage, Ctrl+C...) est disqualifiée**, quel que soit
son score. Ses robots restent sur la carte et peuvent toujours être détruits. Chaque robot ennemi détruit
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
- un chemin plus long que la vitesse du robot, qui sort de la carte ou qui
  traverse une case couverte par un bouclier ennemi ;
- un tir qui ne vient pas d'un `K`, ou qui vise un allié, une cible morte ou
  une cible hors de portée ;
- un bouclier posé par un robot qui n'est pas un `D`.

Un tir **arrêté par un bouclier** n'est pas une faute : il rate, simplement.

## Écrire sa stratégie

Ouvrez `strategy/my_strategy.py`. La méthode `decide(state)` est appelée à
chaque tour et retourne une liste de commandes :

```python
from robby import move, shoot, shield

move(robot, "UR")        # une case : U, UR, R, DR, D, DL, L, UL
move(k, "R", "R", "DR")  # plusieurs cases (K : 3 max, D : 2 max, R : 1)
move(k, *chemin)         # chemin = liste de directions
shoot(destructeur, cible)
shield(defenseur, "SL")  # SU, SR, SD, SL
```

La classe garde la même instance pendant toute la partie : vous pouvez stocker
des informations dans `self`, par exemple la dernière position connue des
ennemis. Une **nouvelle instance** est créée au début de chaque partie (une
série en enchaîne plusieurs). Le module `random` est initialisé avec la
graine de la partie : utilisez-le (et pas un autre générateur) pour qu'une
partie puisse être rejouée à l'identique. Les méthodes `on_game_start`, `on_turn_result` et `on_game_over`
vous informent de ce qui se passe (voir `robby/strategy.py`).

### Ce que contient `state` (un objet `GameState`)

| Attribut / méthode | Description |
|---|---|
| `state.turn`, `state.phase`, `state.phase_turn` | numéro du tour, de la phase (1 ou 2), du tour dans la phase |
| `state.my_robots` | vos robots vivants |
| `state.enemies` | ennemis vivants **visibles** |
| `state.element` | `.pos`, `.is_free`, `.carried_by_id` |
| `state.my_base`, `state.base_of(team_id)` | positions des bases |
| `state.path_towards(robot, (x, y), avoid=())` | début du plus court chemin vers une case, à la vitesse du robot, en contournant les boucliers ennemis visibles et les cases de `avoid` (par exemple des boucliers vus plus tôt) |
| `state.shortest_path((x0, y0), (x1, y1))` | plus court chemin complet (liste de directions) |
| `state.speed(robot)` | nombre de cases par tour (K 3, D 2, R 1) |
| `state.can_follow(robot, chemin)` | le chemin est-il valide d'après ce que vous voyez ? |
| `state.possible_moves(robot)` | directions valides pour un pas d'une case |
| `state.targets_in_range(k)` | ennemis visibles à portée et non protégés par un bouclier ennemi |
| `state.nearest(robot, robots)` | le robot le plus proche dans une liste |
| `state.shield_cells()` | cases couvertes par les boucliers ennemis visibles (`only_enemies=False` : tous) |
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
serveur → {"type": "game_start", "team_id": 2, "seed": 106, "game": 1, "games": 1,
           "config": {...}}
à chaque tour :
  serveur → {"type": "game_state", "turn", "phase", "phase_turn", "robots": [...], "element": {...}}
  client  → {"type": "commands", "turn": <tour>, "commands": [...]}   (avant turn_timeout)
  serveur → {"type": "turn_result", "turn", "data": {"moves", "shots", "deaths", "shields", "penalties"}}
serveur → {"type": "game_over", "winner": 2, "scores": {...}}
(série : retour à game_start pour la partie suivante, puis à la fin)
serveur → {"type": "series_over", "ranking": [...]}
```
