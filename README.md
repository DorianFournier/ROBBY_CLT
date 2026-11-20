# ROBBY — client

Votre mission : écrire la **stratégie** d'une équipe de 4 robots qui affronte
les autres équipes sur le serveur ROBBY.

Vous ne modifiez **que le dossier `strategy/`**. Votre code va dans
`strategy/my_strategy.py`. Le paquet `robby/` s'occupe du réseau, de la
lecture de l'état et de la vérification des commandes.

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
| `--strategy` | `bot1` à `bot4` (bots de référence) ou `module:Classe` | `strategy.my_strategy:MyStrategy` |
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

## Les règles

### L'arène

- Une arène carrée de 15000 × 15000 unités. `x` va de gauche à droite, `y` de
  **haut en bas**. Les distances se mesurent à vol d'oiseau.
- **Les angles sont en degrés, comme une boussole** : 0 = haut, 90 = droite,
  180 = bas, 270 = gauche. Pour aller d'un point A à un point B :
  `angle = math.degrees(math.atan2(bx - ax, -(by - ay))) % 360`, ou plus
  simplement `robot.angle_to(B)`.
- Chaque équipe a une **base** (un disque de rayon 700) au milieu d'un côté
  de l'arène, et quatre robots. Les robots sont des disques de rayon 300.

| Type | Nom | Vitesse max par tour | Capacité |
|---|---|---|---|
| `R` | Radar | 1500 | Voit les ennemis à moins de 3000 : les yeux de l'équipe. |
| `C` | Collecteur | 1000 | Seul robot pouvant ramasser et porter une batterie. Le plus lent : protégez-le ! |
| `D` | Défenseur | 2000 | Pose un bouclier : une part de tarte de 90° et de rayon 1500. |
| `K` | Destructeur | 3000 | Tire un rayon de 3000 qui touche le premier ennemi rencontré. |

**Brouillard de guerre** : vous ne voyez que vos robots et les ennemis détectés
par **vos** radars. Un radar détruit, c'est une équipe aveugle.

### Commandes (une par robot et par tour)

```python
from robby import move, shoot, shield, stop

move(robot, angle=90, speed=2000)   # cap à droite, 2000 unités par tour
stop(robot)                         # vitesse 0
shoot(k, angle=state.aim(k, cible)) # ou : state.shoot_at(k, cible)
shield(d, angle=180)                # bouclier tourné vers le bas
```

### Déplacements : un cap et une vitesse

**`move` règle un cap et une vitesse, comme un volant et un accélérateur.**
Le robot les **garde** d'un tour à l'autre : sans nouvelle commande, il
continue d'avancer tout seul dans la même direction. Il continue aussi quand il
tire (K) ou tourne son bouclier (D), puisqu'on n'envoie qu'une commande par
robot et par tour. Il s'arrête seulement :

- si vous lui envoyez `stop(robot)` (ou une vitesse 0) ;
- s'il allait heurter un robot ennemi ou entrer dans un bouclier ennemi
  (il s'arrête net, vitesse 0) ;
- s'il est pénalisé (moteurs coupés).

Il traverse ses alliés, et contre un bord de l'arène il glisse le long du mur
en gardant son cap. `robot.heading` et `robot.speed` donnent le cap et la
vitesse actuels, y compris ceux des ennemis visibles : `state.predict(ennemi)`
dit où il sera au tour suivant s'il continue.

### Tir

Le tir est un **rayon instantané** de 3000 unités, tiré depuis la position du
Destructeur au **début** du tour. Il touche le **premier ennemi** sur sa
trajectoire et traverse vos alliés. Un bouclier ennemi l'arrête.

### Boucliers

Le bouclier est une part de tarte de 90° et de rayon 1500, tournée vers
l'angle choisi. Il reste orienté ainsi et **suit le Défenseur quand celui-ci
se déplace**. Il ne gêne que les **ennemis** :

- un tir ennemi qui le traverse est arrêté ;
- un robot ennemi ne peut pas y entrer ;
- vos propres robots le traversent librement, et vos tirs aussi.

Un tir qui arrive par derrière touche le Défenseur : à vous de bien l'orienter.

**Le bouclier s'use** :

- il a **3 points de résistance**, et chaque tir ennemi qu'il arrête lui en
  retire un ;
- à 0, il **se brise** : il disparaît et ne peut plus être posé pendant
  **4 tours**, puis il revient entier (une commande `SHIELD` pendant ce temps
  est sans effet) ;
- s'il n'est pas touché pendant 3 tours, il regagne 1 point par tour.

Tirer sur un ennemi protégé n'est donc pas inutile : trois tirs et la voie est
libre, et deux Destructeurs vont deux fois plus vite. `robot.shield_hp`,
`robot.shield_cooldown` et `robot.shield_ready` vous renseignent (y compris
sur les Défenseurs ennemis visibles), et `state.shielded_targets(k)` donne les
ennemis à portée mais derrière un bouclier.

### Déroulement d'un tour

Toutes les équipes reçoivent l'état du jeu et ont **3 secondes** pour répondre
(`state.config["turn_timeout"]`). Une équipe qui répond trop tard ne joue pas ce
tour : ses robots continuent sur leur lancée. Le client vous prévient par un
`WARNING` si votre `decide()` est trop lent.

Le serveur applique ensuite toutes les commandes **en même temps**, à partir
de l'état du début du tour :

1. les tirs sont résolus : les boucliers touchés s'usent, les robots touchés
   sont détruits (deux Destructeurs peuvent s'éliminer mutuellement) ;
2. les robots survivants qui roulent avancent (puis, en phase 2, la
   déchèterie : dépôts, puis prises de prisonniers) ;
3. les boucliers sont posés ;
4. la tempête détruit les robots restés dehors.

### Phase 1 — Course aux batteries (60 tours)

Des **batteries** sont posées dans l'arène :
- une **grosse batterie au centre**, qui rapporte **1000 points** : le gros
  lot, mais là où tout le monde se croise ;
- des **petites batteries** (**500 points**), chacune à égale distance des
  bases de deux équipes voisines : deux à 2 équipes (au-dessus et au-dessous
  du centre), trois à 3 équipes, quatre à 4 équipes.

À 3 équipes, les bases sont sur un cercle autour du centre, espacées de 120° :
chaque équipe est exactement dans la même situation. Un Collecteur ramasse
une batterie en passant à moins de 500 unités, et n'en porte qu'une à la fois.

**Chaque batterie ramenée dans votre base rapporte ses points.** Elle
disparaît, puis **réapparaît à sa place 3 tours plus tard** : faites autant
d'allers-retours que possible pendant les 60 tours ! Sûr mais peu payant, ou
risqué mais rentable : à vous de choisir (`state.best_battery(robot)` calcule
la batterie la plus rentable). Si le porteur est détruit, la batterie tombe là
où il est mort. Un robot détruit pendant cette phase réapparaît près de sa
base 3 tours plus tard.

### Phase 2 — Match à mort (100 tours au maximum)

Les robots détruits **ne réapparaissent plus**. La partie s'arrête **dès qu'il
ne reste qu'une seule équipe en vie**. Les 100 tours sont une durée maximale.
Attention : survivre ne suffit pas, c'est **le score** qui désigne le
vainqueur.

**La tempête arrive.** La zone sûre est un **cercle**, qui contient d'abord
toute l'arène et se resserre par étapes. Chaque étape a deux temps :

1. une **pause**, pendant laquelle la tempête est immobile et le **prochain
   cercle est annoncé** ;
2. une **avancée** à vitesse constante jusqu'à ce cercle.

| Étape | Pause | Cercle visé (rayon) | Vitesse | Tours de la phase 2 |
|---|---|---|---|---|
| 1 | 15 tours | 6000 | 500 par tour | pause 1–15, avancée 16–25 |
| 2 | 6 tours | 3500 | 400 par tour | pause 26–31, avancée 32–38 |
| 3 | 6 tours | 1500 | 300 par tour | pause 39–44, avancée 45–51 |
| Épreuve finale | 6 tours | 0 | 100 par tour | pause 52–57, avancée 58–72 |

**L'épreuve finale** : s'il reste plusieurs équipes, la tempête reprend
lentement jusqu'à ne laisser **aucune place sûre**. Camper ne suffit pas, il
faut gagner le combat avant.

Par défaut, tous les cercles sont centrés sur l'arène. Si le serveur est lancé
avec `--storm aleatoire`, chaque nouveau cercle est tiré au hasard **à
l'intérieur du précédent**, et pendant l'avancée le cercle glisse vers son
nouveau centre. Regardez donc où le prochain cercle est annoncé
(`state.safe_center`) plutôt que de foncer vers le milieu de l'arène !

**Un robot dont le centre est hors du cercle à la fin d'un tour est détruit.**
Le cercle est rond : les coins tombent avant le milieu des bords. La tempête
avance moins vite que le Collecteur, mais il n'avance que de 1000 par tour : partez
à temps ! Et attention à l'élan : un robot qui tire en roulant peut finir
dehors. `state.keep_safe(robot, commande)` remplace la commande par un écart
si c'est le cas.

Ce que vous savez de la tempête (`state.zone`, envoyé à chaque tour) :

| Clé | Contenu |
|---|---|
| `center` | centre du cercle à la fin de ce tour |
| `radius` | rayon sûr à la **fin de ce tour** |
| `forecast`, `forecast_centers` | rayons et centres des prochains tours (`forecast[2]` : dans 2 tours) |
| `state` | `"calm"` (phase 1), `"pause"`, `"shrink"` (elle avance) ou `"final"` |
| `target`, `target_center` | rayon et centre du prochain cercle annoncé |
| `shrink_turn`, `end_turn` | tours où la prochaine avancée commence et se termine |

Le plus simple est d'utiliser les outils de `state` (voir plus bas).

**La déchèterie.** En phase 2, votre Collecteur n'a plus de batteries à
ramasser : il ramasse... les ennemis !

- Un Collecteur qui finit son tour **au contact** (700 unités, centre à
  centre) d'un robot ennemi **à l'arrêt** (vitesse 0 : arrêté, bloqué ou
  pénalisé) l'**attrape**. Un robot qui roule ne peut pas être attrapé.
  Deux Collecteurs sur le même robot : le plus proche l'emporte. Un
  Collecteur chargé ne peut pas être attrapé. Deux Collecteurs qui
  pourraient s'attraper l'un l'autre : celui qui **arrive au contact** (il a
  roulé ce tour) prend celui qui est resté **garé** ; s'ils ont roulé tous
  les deux, ou aucun, personne.
- Un robot qui roule ne peut pas être attrapé... sauf si on lui **coupe la
  route** : bloqué par le Collecteur, il s'arrête net, au contact, et il est
  pris dans la foulée.
- Le prisonnier est **inactif** : ses commandes sont ignorées (sans
  pénalité), il ne bloque personne, les tirs le traversent (on ne peut ni
  l'achever ni le délivrer en tirant), et son Radar ne voit plus rien.
- Un Collecteur chargé roule **à 600 au plus**. Il ne porte qu'un
  prisonnier à la fois.
- S'il entre dans la **déchèterie**, un disque de rayon 700 **au centre de
  la zone sûre** (il suit la tempête), le prisonnier est **détruit** et
  rapporte **une fois et demie** sa valeur (voir le score).
- Si le Collecteur est détruit (tir, tempête), son prisonnier est
  **libéré**, là où il était.

Conséquence : en phase 2, **un robot immobile est une proie**. Un Défenseur
dont le bouclier fait face au Collecteur l'arrête (on ne traverse pas un
bouclier ennemi). Outils : `state.dump_center`, `state.in_dump(point)`,
`state.grab_targets(c)`, `state.captives`, et `robot.captive_id` (prisonnier
porté par ce Collecteur), `robot.captured_by` (Collecteur qui porte ce robot).

### Score

**L'équipe qui a le meilleur score gagne.** Être la dernière équipe en vie
arrête la partie, mais ne suffit pas pour gagner. **Attention : une équipe
dont le client se déconnecte (plantage, Ctrl+C...) est disqualifiée**, quel
que soit son score. Ses robots restent dans l'arène et peuvent toujours être
détruits.

| Ce qui rapporte | Points |
|---|---|
| Batterie ramenée à votre base | 500 (petite) ou 1000 (grosse, au centre) chaque fois |
| Destructeur `K` ennemi détruit | 250 |
| Défenseur `D` ennemi détruit | 500 |
| Collecteur `C` ennemi détruit | 500 |
| Radar `R` ennemi détruit | 750 |
| Collecteur ennemi portant une batterie détruit | 1000 |
| Ennemi déposé à la déchèterie (phase 2) | `K` 375, `D` 750, `C` 750, `R` 1125 |
| Chacun de vos robots encore en vie à la fin de la partie | 300 |

Deux équipes touchent le même robot au même tour : le tireur le plus
proche marque ; à égalité parfaite, les points sont partagés.
Un robot détruit par la tempête ne rapporte rien à personne. Un robot
prisonnier à la fin de la partie ne compte pas comme survivant.

### Pénalités

Une commande invalide **pénalise le robot qui l'a reçue** pendant 3 tours :
pendant ce temps, ses commandes sont ignorées et ses moteurs sont coupés. Une
commande est invalide dans ces cas :

- un robot détruit, une action inconnue ;
- plusieurs commandes pour le même robot dans le même tour ;
- un angle qui n'est pas un nombre, une vitesse négative ou trop grande ;
- un tir qui ne vient pas d'un `K`, un bouclier qui ne vient pas d'un `D`.

Un tir **arrêté par un bouclier** n'est pas une faute : il rate, simplement.

## Écrire sa stratégie

Ouvrez `strategy/my_strategy.py`. La méthode `decide(state)` est appelée à
chaque tour et retourne une liste de commandes (au plus une par robot).

La classe garde la même instance pendant toute la partie : vous pouvez stocker
des informations dans `self`, par exemple la dernière position connue des
ennemis. Une **nouvelle instance** est créée au début de chaque partie (une
série en enchaîne plusieurs). Le module `random` est initialisé avec la
graine de la partie : utilisez-le (et pas un autre générateur) pour qu'une
partie puisse être rejouée à l'identique. Les méthodes `on_game_start`,
`on_turn_result` et `on_game_over` vous informent de ce qui se passe (voir
`robby/strategy.py`).

### Choisir le placement de départ

Trois de vos robots commencent en **triangle** devant votre base, le
quatrième **sur la base**. Vues depuis la base, face au centre de l'arène, les
quatre places sont **`"avant"`** (la pointe, la plus proche du centre),
**`"gauche"`** et **`"droite"`** (en retrait, de part et d'autre) et
**`"milieu"`** (sur la base). C'est vous qui choisissez quel robot va où, avec
l'attribut `placement` de votre classe :

```python
class MyStrategy(Strategy):
    placement = {"R": "gauche", "C": "milieu", "D": "avant", "K": "droite"}
```

Par défaut : `{"R": "avant", "C": "milieu", "D": "droite", "K": "gauche"}`. Un robot détruit
réapparaît à sa place. Si le placement est invalide (deux robots sur la même
place, un robot oublié...), le serveur garde le placement par défaut et le
client affiche pourquoi.

### Ce que contient `state` (un objet `GameState`)

| Attribut / méthode | Description |
|---|---|
| `state.turn`, `state.phase`, `state.phase_turn` | numéro du tour, de la phase (1 ou 2), du tour dans la phase |
| `state.my_robots`, `state.my_robots_of_type("K")` | vos robots vivants (et libres : pas prisonniers) |
| `state.enemies` | ennemis vivants (et libres) **visibles** |
| `state.dump_center`, `state.in_dump(point)` | déchèterie (phase 2, `None` en phase 1) : son centre, ce point est-il dedans ? |
| `state.grab_targets(c)` | ennemis à l'arrêt, au contact, que ce Collecteur attraperait |
| `state.captives` | prisonniers visibles (les vôtres et ceux de vos Collecteurs) |
| `state.scores`, `state.my_score`, `state.lead` | scores de toutes les équipes (publics), le vôtre, et votre avance sur la meilleure équipe adverse (négative si vous êtes en retard) |
| `state.elements` | les batteries : `.pos`, `.points` (ce que rapporte sa capture), `.is_free` (posée au sol, à prendre), `.carried_by_id`, `.present` (`False` pendant qu'une batterie capturée réapparaît) |
| `state.nearest_battery(robot)` | batterie libre la plus proche, ou `None` |
| `state.best_battery(robot)` | batterie libre la plus rentable : ses points divisés par le trajet (aller la chercher, puis la ramener à votre base) |
| `state.free_batteries` | batteries posées au sol |
| `state.carried_battery(robot)` | batterie portée par ce robot, ou `None` |
| `state.element` | la première batterie (la seule à 2 équipes) |
| `state.my_base`, `state.base_of(team_id)`, `state.on_base(robot)`, `state.center` | repères |
| `state.move_towards(robot, point, stop_at=0)` | commande MOVE toute prête vers un point ou un robot, à la vitesse max sans dépasser le point visé ce tour-ci, en s'arrêtant à `stop_at` unités ; une fois arrivé, commande d'arrêt (sinon le robot continuerait) |
| `state.move_away(robot, menace)` | commande MOVE pour s'éloigner |
| `state.stop(robot)`, `state.predict(robot, tours)` | commande d'arrêt (None si déjà arrêté) ; position future si le robot garde son cap |
| `state.safe_to_coast(robot)`, `state.keep_safe(robot, commande)` | sur sa lancée, reste-t-il hors de la tempête ? ; garder un tir ou un bouclier seulement si c'est le cas |
| `state.distance(a, b)`, `state.nearest(robot, robots)` | distance à vol d'oiseau, robot (ou point, ou batterie) le plus proche ; à égalité, celui de droite |
| `state.by_distance(robot, liste)`, `state.side(point)` | liste du plus proche au plus loin (égalités : la droite d'abord) ; angle du point vu de votre base, 0 = tout droit vers le centre, sens horaire |
| `state.max_speed(robot)`, `state.destination(robot, angle, speed)` | vitesse maximale ; point d'arrivée si rien ne gêne |
| `state.targets_in_range(k)` | ennemis visibles qu'un tir visé sur eux toucherait vraiment |
| `state.shielded_targets(k)` | ennemis à portée mais derrière un bouclier : tirer dessus l'use |
| `state.shoot_at(k, cible)`, `state.aim(k, cible)` | commande de tir, angle de tir |
| `state.first_hit(k, angle)` | ce que toucherait un tir : `(robot ou None, bloqué ?, distance)` |
| `state.firing_spot(k, cible)` | point atteignable ce tour d'où tirer sur la cible sans être bloqué par un bouclier (pour contourner) |
| `state.enemy_shields()`, `state.in_enemy_shield(point)` | boucliers ennemis visibles |
| `state.zone_escape(robot)` | point sûr où fuir si la tempête menace le robot (None s'il est à l'abri) |
| `state.in_zone(point, lookahead=0, inset=0)` | le point est-il dans le cercle sûr (dans `lookahead` tours, avec une marge) ? |
| `state.clamp_to_zone(point)`, `state.safe_center` | point sûr le plus proche ; centre du prochain cercle (où se regrouper) |
| `state.storm_radius(k)`, `state.storm_center_at(k)` | rayon et centre du cercle dans `k` tours |
| `state.config` | paramètres de la partie envoyés par le serveur |

Chaque `Robot` a les attributs `id`, `team_id`, `type`, `x`, `y`, `pos`,
`alive`, `heading`, `speed`, `shield_direction`, `shield_hp`,
`shield_cooldown`, `carrying_element`, `penalty`, `captive_id` (prisonnier
porté, Collecteur), `captured_by` (Collecteur qui le porte), ainsi que
`captive` (prisonnier ?), `can_act` (vivant, libre et sans pénalité), `moving`, `shield_ready`, `distance_to(...)` et
`angle_to(...)`.

Avant chaque envoi, le client vérifie les erreurs évidentes et les affiche en
`WARNING`. Une exception levée dans votre stratégie est affichée, et vous
passez simplement le tour : la connexion n'est pas perdue.

## Bots de référence (paliers)

Le dossier `bots/` contient quatre adversaires d'entraînement, du plus faible
au plus fort. Le but est de les battre l'un après l'autre.

| Option | Bot | Comportement |
|---|---|---|
| `bot1` | `RandomBot` | Joue au hasard, mais sans faute de règle (il fuit la tempête). |
| `bot2` | `RusherBot` | « Fonceur » : le Collecteur va droit sur la batterie (le Radar l'escorte) et, en phase 2, chasse toujours les ennemis pour la déchèterie, le Destructeur tire sur l'ennemi le plus proche (ou use son bouclier) ou lui fonce dessus, le Défenseur suit le Radar et tourne son bouclier vers l'ennemi. Aucune prudence, aucune mémoire. |
| `bot3` | `TacticianBot` | « Tacticien » : il se souvient des ennemis vus, son Collecteur se cache derrière le Défenseur quand un Destructeur ennemi menace, et le Radar l'escorte pour le voir venir. En phase 2, il tient le centre du prochain cercle (celui qui attend voit l'autre arriver en premier), avance derrière son Défenseur, contourne les boucliers ennemis pour tirer de côté, ou les use. |
| `bot4` | `SimulatorBot` | « Simulateur » : il essaie des centaines de plans dans un simulateur de tour et garde le meilleur (voir plus bas). |

Mesuré sur 150 parties par duel (côtés alternés, une commande sur dix perdue
au hasard pour que les parties soient toutes différentes). Score : victoire 1,
nul 0,5, défaite 0 :

| Duel | Score du premier |
|---|---|
| bot3 contre bot2 | 0,59 |
| bot4 contre bot3 | 0,75 |
| bot4 contre bot2 | 0,72 |

En phase 2, tous les bots envoient leur Collecteur à la chasse
(`bots/chasse.py`) : il attrape les ennemis à l'arrêt ou leur coupe la route,
et les porte à la déchèterie (par le bord le plus proche). Sans proie en
vue, il suit les pistes puis patrouille autour du centre : il ne reste
jamais garé. Tant que leurs Destructeurs se battent, il leur laisse les
proies couvertes par un Destructeur ennemi ; quand il n'en reste plus,
il attaque tout, et le Radar le suit pour lui donner la vue.

Lire leur code (`bots/level2_rusher.py`, `bots/level3_tactician.py`...) est une
bonne source d'idées... mais pour les battre, il faudra faire mieux !

### bot4 : le « simulateur »

`--strategy bot4` lance `SimulatorBot` (`bots/level4_simulator.py`). Il ne
suit pas des règles fixes : il **essaie des plans** et garde le meilleur.
À chaque tour :

1. il part du plan du tacticien (bot3) ;
2. pour chaque robot, il prépare une vingtaine de commandes possibles
   (continuer sur sa lancée, s'arrêter, 8 directions, aller vers la batterie,
   tirer sur chaque cible, contourner un bouclier, intercepter le porteur,
   tourner le bouclier vers chaque menace...) ;
3. il **joue chaque plan dans le simulateur** (`robby/simulator.py`), contre
   deux hypothèses sur les ennemis : ils continuent sur leur lancée, ou ils
   foncent sur lui (leurs Destructeurs tirent sur la meilleure cible qu'ils
   ont) ;
4. il **note** chaque résultat : robots perdus et détruits, boucliers usés ou
   brisés, batterie, danger au tour suivant, occasions de tir, tempête (et
   l'élan : où il roulera sans nouvelle commande), Radar bien entouré ;
5. il améliore la commande d'un robot à la fois, en gardant les autres, puis
   recommence. Au plus 260 plans sont évalués, en environ 10 ms par tour.

Il se souvient aussi des ennemis disparus de la vue, et prévoit qu'un porteur
de batterie invisible rentre vers sa base : il peut l'intercepter ou tirer
« à l'aveugle » là où il devrait être.

C'est le dernier palier, avant de passer à vos propres idées : changer les
poids de `evaluate`, ajouter des candidats, prévoir deux tours à l'avance...

### Le simulateur de tour : tester ses coups avant de jouer

`robby/simulator.py` refait les calculs du serveur (mêmes règles, même ordre)
sur ce que vous voyez. Sur 2490 tours de vraies parties (2 à 4 équipes), il a
donné exactement les mêmes positions, destructions, boucliers et batteries que
le serveur. Vous pouvez
l'utiliser dans votre propre stratégie :

```python
from robby.simulator import TurnSimulator

sim = TurnSimulator(state)
apres = sim.run({state.team_id: mes_commandes,
                 2: commandes_que_je_prete_a_l_equipe_2})
apres.deaths                  # robots détruits pendant ce tour
apres.robot(13).pos           # position de mon K à la fin du tour
apres.carriers, apres.captures   # porteurs de batterie, équipes qui ont capturé
```

Il ne connaît que ce que vous voyez : un ennemi invisible n'existe pas pour lui,
sauf si vous l'ajoutez (`TurnSimulator(state, extra=[SimRobot(...)])`). Et il
ne devine pas les commandes des autres équipes : c'est à vous de faire des
hypothèses. Sans commande, un ennemi visible continue sur sa lancée.

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

Les places dans l'arène tournent d'une partie à l'autre. Chaque partie affiche
sa graine : pour **rejouer à l'identique** une partie perdue (et comprendre
pourquoi), relancez le serveur avec `--headless --games 1 --seed <graine>` et
les mêmes clients.

Pour **revoir** une partie en détail, ajoutez `--record replays` à la commande
du serveur. Ouvrez ensuite le fichier de la partie avec le lecteur du dépôt
ROBBY :

```bash
uv run python -m ui.replay replays/<fichier>.json
```

Avec `Espace` (pause), `←` / `→` (tour par tour), `↑` / `↓` (vitesse) et `C`
(commandes envoyées par chaque équipe), vous voyez la partie en détail.

## Protocole (pour les curieux)

Le client et le serveur échangent des messages JSON par TCP, **un message par
ligne** :

```
client → {"type": "register", "name": "MonEquipe",
          "placement": {"R": "avant", "D": "droite", "K": "gauche"}}
serveur → {"type": "register_ack", "status": "ok", "team_id": 2,
           "placement": {...}}   (+ "placement_error" si le placement est refusé)
serveur → {"type": "game_start", "team_id": 2, "seed": 106, "game": 1, "games": 1,
           "config": {...}}
à chaque tour :
  serveur → {"type": "game_state", "turn", "phase", "phase_turn", "robots": [...],
             "elements": [...], "element": {...}, "zone": {...}}
  client  → {"type": "commands", "turn": <tour>, "commands": [
               {"robot_id": 11, "action": "MOVE", "angle": 90, "speed": 1000}, ...]}
             (avant turn_timeout)
  serveur → {"type": "turn_result", "turn", "data": {"moves", "shots", "deaths",
             "shields", "penalties", "zone_deaths", "shield_breaks"}}
serveur → {"type": "game_over", "winner": 2, "scores": {...}}
(série : retour à game_start pour la partie suivante, puis à la fin)
serveur → {"type": "series_over", "ranking": [...]}
```
