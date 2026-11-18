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
| `--strategy` | `bot1`, `bot2`, `bot3` (bots de référence, pour les deux modes), `bot4` (mode libre) ou `module:Classe` | `strategy.my_strategy:MyStrategy` |
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
| `bot2` | `RusherBot` | « Fonceur » (ses robots rentrent dans la zone en priorité, sans jamais viser la même case) : le Radar va droit sur l'élément, le Destructeur tire sur l'ennemi le plus proche ou lui fonce dessus et reste près de son Radar s'il ne voit personne, le Défenseur suit le Radar. Aucune prudence, aucune mémoire. |
| `bot3` | `TacticianBot` | « Tacticien » : le groupe se déplace autour du Radar. Le Défenseur sert de garde du corps (il se place entre le Radar et la menace, bouclier tourné vers elle), le Radar recule s'il est exposé, les Destructeurs restent sur ses flancs (dans sa zone de vision) et choisissent leurs cibles. En phase 2, il prend le centre et le tient : avec le brouillard de guerre, celui qui attend voit l'autre arriver en premier, et la zone qui rétrécit oblige les autres à venir. Il mémorise les ennemis et leurs boucliers, même quand ils sortent de la vue. |

Mesuré sur 40 parties en 1 contre 1 (côtés alternés, avec 10 % d'actions
aléatoires des deux côtés pour que les parties soient toutes différentes) :
`bot2` et `bot3` battent `bot1` 40 fois sur 40. Depuis l'ajout de la zone qui
rétrécit, `bot3` et `bot2` sont à égalité (20 victoires contre 19).

Lire leur code (`bots/level2_rusher.py`, `bots/level3_tactician.py`) est une
bonne source d'idées... mais pour les battre, il faudra faire mieux !

En **mode libre**, les mêmes options lancent `FreeRandomBot`, `FreeRusherBot`
et `FreeTacticianBot` (`bots/free_*.py`). Le tacticien contourne les boucliers
ennemis pour tirer de côté. Mesure faite (30 parties par duel, 10 % d'actions
au hasard) : bot2 bat bot1 29 fois sur 30, bot3 bat bot1 30 fois sur 30, et
bot3 bat bot2 23 fois sur 30.

### bot4 : le « simulateur » (mode libre uniquement)

`--strategy bot4` lance `FreeSimulatorBot` (`bots/free_simulator.py`). Il ne
suit pas des règles fixes : il **essaie des plans** et garde le meilleur.
À chaque tour :

1. il part du plan du tacticien (bot3) ;
2. pour chaque robot, il prépare une vingtaine de commandes possibles (rester,
   8 directions, aller vers la batterie, tirer sur chaque cible, contourner un
   bouclier, intercepter le porteur, tourner le bouclier vers chaque menace...) ;
3. il **joue chaque plan dans le simulateur** (`robby/simulator.py`), contre
   deux hypothèses sur les ennemis : ils restent sur place, ou ils foncent sur
   lui (leurs Destructeurs tirent sur la meilleure cible qu'ils ont) ;
4. il **note** chaque résultat : robots perdus et détruits, batterie, danger au
   tour suivant, occasions de tir, zone, Radar bien entouré ;
5. il améliore la commande d'un robot à la fois, en gardant les autres, puis
   recommence. Au plus 260 plans sont évalués, en environ 10 ms par tour.

Il se souvient aussi des ennemis disparus de la vue, et prévoit qu'un porteur
de batterie invisible rentre vers sa base : il peut l'intercepter ou tirer
« à l'aveugle » là où il devrait être.

Mesuré sur 40 parties par duel (10 % d'actions au hasard) : bot4 bat bot1
40 fois sur 40, bot2 34 fois sur 40 et bot3 30 fois sur 40. C'est le dernier
palier, avant de passer à vos propres idées : changer les poids de
`evaluate`, ajouter des candidats, prévoir deux tours à l'avance...

### Le simulateur de tour : tester ses coups avant de jouer

`robby/simulator.py` refait les calculs du serveur (mêmes règles, même ordre)
sur ce que vous voyez. Sur 525 tours de vraies parties, il a donné exactement
les mêmes positions et les mêmes destructions que le serveur. Vous pouvez
l'utiliser dans votre propre stratégie :

```python
from robby.simulator import TurnSimulator

sim = TurnSimulator(state)
apres = sim.run({state.team_id: mes_commandes,
                 2: commandes_que_je_prete_a_l_equipe_2})
apres.deaths                  # robots détruits pendant ce tour
apres.robot(13).pos           # position de mon K à la fin du tour
apres.carrier, apres.captured_by
```

Il ne connaît que ce que vous voyez : un ennemi invisible n'existe pas pour lui,
sauf si vous l'ajoutez (`TurnSimulator(state, extra=[SimRobot(...)])`). Et il
ne devine pas les commandes des autres équipes : c'est à vous de faire des
hypothèses.

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
   case d'arrivée, aucun des deux ne bouge, **même s'ils sont de la même
   équipe** : coordonnez vos robots (voir `trim_to_free`). Une case accueille
   au plus 2 robots ;
3. les boucliers sont posés.

### Phase 1 — Capture (100 tours au maximum)

Un élément est placé au centre de la carte. Le premier radar qui le ramasse puis
le **ramène sur sa base** termine la phase 1. Son équipe reçoit alors un
**second destructeur**. Un robot détruit pendant cette phase réapparaît près de
sa base 5 tours plus tard.

### Phase 2 — Match à mort (100 tours au maximum)

Les robots détruits **ne réapparaissent plus**. La partie s'arrête **dès qu'il
ne reste qu'une seule équipe en vie**. Les 100 tours sont une durée maximale.

**La zone se resserre.** À partir du 20e tour de la phase 2, l'anneau
extérieur de la carte devient mortel, puis un anneau de plus tous les 8 tours,
jusqu'à un carré de 3 × 3 au centre. **Un robot hors de la zone sûre à la fin
d'un tour est détruit.** Le prochain rétrécissement est annoncé :
`state.zone["next_turn"]`. Pensez à votre Radar, qui n'avance que d'une case
par tour !

### Score

**La dernière équipe en vie gagne.** Si plusieurs équipes survivent au bout des
100 tours, la meilleure au score total parmi elles l'emporte : une équipe
éliminée ne gagne jamais. **Attention : une équipe dont
le client se déconnecte (plantage, Ctrl+C...) est disqualifiée**, quel que soit
son score. Ses robots restent sur la carte et peuvent toujours être détruits.

Chaque robot ennemi détruit rapporte :

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
| `state.in_zone((x, y), lookahead=0)` | la case est-elle dans la zone sûre (maintenant, ou dans `lookahead` tours) ? |
| `state.zone_escape_path(robot, lookahead=2, taken=...)` | chemin pour rentrer dans la zone sûre vers une case libre (vide si le robot est à l'abri) |
| `state.destination(robot, chemin)` | case d'arrivée d'un chemin |
| `state.trim_to_free(robot, chemin, taken)` | raccourcit un chemin pour ne pas viser une case déjà visée par un allié |
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

## Mode libre (V2) : angle et vitesse

Si le serveur est lancé avec `--mode libre`, les robots ne vont plus de case
en case : ils partent dans une direction donnée par un **angle**, à la
**vitesse** de votre choix. Votre client le détecte tout seul. Votre stratégie
reçoit alors un `FreeGameState`, et un avertissement s'affiche si elle n'est
écrite que pour l'autre mode.

```bash
uv run main.py --name Moi --strategy strategy.my_free_strategy:MyFreeStrategy
```

Pour une stratégie qui sait jouer les deux modes, déclarez
`modes = ("grille", "libre")` dans sa classe et testez `state.mode`.

### Repère et règles

- Arène de 15000 × 15000 unités, x vers la droite, y vers le **bas**. Une case
  de la V1 vaut 1000 unités : bases, départs et batterie sont aux mêmes
  endroits.
- **Angles en degrés, comme une boussole** : 0 = haut, 90 = droite, 180 = bas,
  270 = gauche. Pour aller d'un point A à un point B :
  `angle = math.degrees(math.atan2(bx - ax, -(by - ay))) % 360`, ou plus
  simplement `robot.angle_to(B)`.
- Vitesse maximale par tour : Radar 1000, Défenseur 2000, Destructeur 5000.
- Les robots sont des disques de rayon 300. Un robot s'arrête s'il allait
  toucher un **ennemi** ou entrer dans un bouclier ennemi. Il traverse ses
  alliés et glisse le long des bords.
- **Tir** : un rayon instantané de 3000 unités, tiré depuis la position du
  début de tour. Il touche le **premier ennemi** sur sa trajectoire, traverse
  les alliés, et un bouclier ennemi l'arrête.
- **Bouclier** : une part de tarte de 90° et de rayon 1500, tournée vers
  l'angle choisi. Il suit le Défenseur.
- **Vision** : un cercle de rayon 3000 autour de chaque Radar.
- **Batterie** : un Radar la ramasse en passant à moins de 500 unités, et
  marque la capture en entrant dans sa base (un disque de rayon 700).
- Phases, zone, points et pénalités : comme en V1. Une vitesse trop grande,
  ou une commande sans angle, vaut une pénalité.

### Commandes

```python
from robby import move, shoot, shield

move(robot, angle=90, speed=2000)   # vers la droite, 2000 unités
shoot(k, angle=state.aim(k, cible)) # ou : state.shoot_at(k, cible)
shield(d, angle=180)                # bouclier tourné vers le bas
```

### Outils de `FreeGameState`

| Méthode | Description |
|---|---|
| `state.move_towards(robot, point, stop_at=0)` | commande MOVE toute prête vers un point ou un robot, à la vitesse max sans dépasser le point visé, en s'arrêtant à `stop_at` unités |
| `state.move_away(robot, menace)` | commande MOVE pour s'éloigner |
| `state.distance(a, b)`, `robot.distance_to(x)`, `robot.angle_to(x)` | distance à vol d'oiseau, angle |
| `state.max_speed(robot)` | vitesse maximale du robot |
| `state.destination(robot, angle, speed)` | point d'arrivée si rien ne gêne |
| `state.targets_in_range(k)` | ennemis visibles qu'un tir visé sur eux toucherait vraiment |
| `state.shoot_at(k, cible)`, `state.aim(k, cible)` | commande de tir, angle de tir |
| `state.first_hit(k, angle)` | ce que toucherait un tir : `(robot ou None, bloqué ?, distance)` |
| `state.firing_spot(k, cible)` | point atteignable ce tour d'où tirer sur la cible sans être bloqué par un bouclier (pour contourner) |
| `state.enemy_shields()`, `state.in_enemy_shield(point)` | boucliers ennemis visibles |
| `state.zone_escape(robot)`, `state.in_zone(point)`, `state.clamp_to_zone(point)` | zone sûre |
| `state.center`, `state.my_base`, `state.on_base(robot)` | repères |

Les outils de la grille (`path_towards`, `shortest_path`...) n'ont pas de sens
ici : ils lèvent une erreur qui indique quoi utiliser à la place.

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
