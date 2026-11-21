# bots/chasse.py
# Le Collecteur en phase 2 : la chasse aux prisonniers pour la déchèterie.
#
# Rappel des règles : un Collecteur qui finit son tour au contact d'un ennemi
# À L'ARRÊT l'attrape. Un ennemi qui roule ne peut pas être attrapé... sauf
# qu'en lui coupant la route, on le BLOQUE (deux ennemis ne se traversent
# pas) : il s'arrête net, au contact, et il est pris dans la foulée.
#
# Ce que fait le Collecteur :
#   1. il porte un prisonnier : vers le bord le plus proche de la
#      déchèterie (le centre est souvent encombré), en contournant ;
#   2. sinon il choisit une proie parmi les ennemis visibles (un Collecteur
#      seulement s'il est garé : en venant à son contact, on le prend) :
#      d'abord ceux
#      qui sont à l'arrêt, puis les plus proches. Il fonce sur une proie
#      arrêtée, et vise l'endroit où sera une proie qui roule (pour lui
#      couper la route) ;
#   3. « offensif » (plus aucun Destructeur dans l'équipe : c'est lui qui
#      doit marquer les points) : il chasse toutes les proies, même gardées
#      par un Destructeur ennemi, et sans proie visible il va où on a vu un
#      ennemi pour la dernière fois, sinon il PATROUILLE autour du centre de
#      la zone (où la tempête pousse tout le monde) : son Radar, qui le
#      suit, balaie ainsi les environs ;
#   4. « prudent » (nos Destructeurs se battent encore) : pareil, mais il
#      laisse les proies couvertes par un Destructeur ennemi à nos
#      Destructeurs. Il ne reste jamais garé : un robot à l'arrêt est une
#      proie pour les Collecteurs ennemis.

import math

from robby import move
from robby.geometry import angle_to, direction

ROULE = 1500         # une proie qui roule « compte » comme plus loin
DERNIER_RECOURS = 4000  # un Collecteur garé « compte » comme bien plus loin
DETOURS = (60, -60, 100, -100, 150, -150)   # contournements essayés (degrés)
RONDE = 2500         # rayon de la patrouille autour du centre de la zone
ARRIVE = 800         # une piste atteinte (personne) est abandonnée
TRAVERSEE = 4        # la ronde traverse le centre 4 tours sur 8


def barre(state, c, cap, longueur, cible=None):
    """Un ennemi (autre que `cible`) barre-t-il le trajet de `c` dans la
    direction `cap`, sur `longueur` unités ? (deux ennemis ne se traversent
    pas : on serait arrêté net en le frôlant)"""
    dx, dy = direction(cap)
    gene = 2 * state.robot_radius + 50
    zones = state.neutral_zones()
    for e in state.enemies:
        if e is cible or state.in_neutral_zone(e, zones):
            continue        # dans une zone neutre, il ne bloque personne
        ex, ey = e.x - c.x, e.y - c.y
        t = min(max(ex * dx + ey * dy, 0.0), longueur)     # point le plus proche
        proche = math.hypot(ex - dx * t, ey - dy * t)
        if proche < gene and proche < math.hypot(ex, ey) - 1:
            return True
    return False


def aller(state, c, but, cible=None):
    """Vers `but`, en contournant un ennemi (autre que la cible) qui barre
    le trajet : d'abord par la droite, puis par la gauche, de plus en plus
    large. Deux robots face à face se croisent au lieu de se bloquer nez à
    nez (sinon chacun répéterait la même commande bloquée, tour après tour)."""
    cap = c.angle_to(but)
    if cap is None:
        return state.move_towards(c, but)
    pas = min(c.distance_to(but), state.max_speed(c))
    if not barre(state, c, cap, pas, cible):
        return state.move_towards(c, but)
    vitesse = state.max_speed(c)
    for ecart in DETOURS:
        if not barre(state, c, cap + ecart, vitesse):
            return move(c, angle=(cap + ecart) % 360, speed=vitesse)
    return move(c, angle=(cap + DETOURS[0]) % 360, speed=vitesse)


def chasse(state, c, souvenirs=(), offensif=None):
    """Commande du Collecteur `c` en phase 2 (déchèterie), ou None.
    `souvenirs` : positions où l'on a vu des ennemis récemment.
    `offensif` : None = automatique (offensif s'il n'a plus de Destructeur)."""
    if not state.dump or c.type != "C" or not c.can_act:
        return None
    if c.captive_id is not None:                      # 1. à la déchèterie
        return aller(state, c, bord_de_la_decheterie(state, c))
    if offensif is None:
        offensif = not state.my_robots_of_type("K")
    # Un Collecteur ennemi n'est une proie que s'il est GARÉ (à l'arrêt) et
    # sans prisonnier : en venant à son contact, c'est nous qui le prenons
    # (prise mutuelle : celui qui a roulé l'emporte). Un Collecteur qui roule
    # se bloquerait nez à nez avec nous, sans prise.
    tireurs = [e for e in state.enemies if e.type == "K"]
    proies = [e for e in state.enemies
              if e.type != "C" or (e.speed == 0 and e.captive_id is None)]
    souvenirs = list(souvenirs)
    portee = state.config["destructor_range"] + state.robot_radius

    def couverte(e):
        return any(k is not e and k.distance_to(e) <= portee for k in tireurs)

    def cout(e):
        # un Collecteur garé : en dernier recours (il peut repartir, et deux
        # Collecteurs au contact se bloquent sans se prendre)
        return c.distance_to(e) + (0 if e.speed == 0 else ROULE) + \
            (DERNIER_RECOURS if e.type == "C" else 0)

    if not offensif:
        proies = [e for e in proies if not couverte(e)]
    if proies:
        meilleur = min(cout(e) for e in proies)
        cible = state.nearest(c, [e for e in proies if cout(e) <= meilleur + 1])
        if cible.type == "C" and c.distance_to(cible) <= state.config["grab_radius"]:
            # déjà collés : il faut ARRIVER au contact pour le prendre, on
            # recule d'un tour pour revenir
            return state.move_away(c, cible.pos)
        if cible.speed == 0:
            return aller(state, c, cible.pos, cible)
        # lui couper la route : là où il sera à la fin du tour
        return aller(state, c, state.clamp_to_zone(state.predict(cible), 1), cible)
    pistes = [p for p in souvenirs if c.distance_to(p) > ARRIVE]
    if pistes:                                        # 3. sur la piste
        return aller(state, c, state.clamp_to_zone(state.nearest(c, pistes), 2))
    return aller(state, c, ronde(state, c))


def bord_de_la_decheterie(state, c):
    """Le point de la déchèterie le plus proche de nous (un peu à
    l'intérieur) : on y dépose sans passer par le centre, où d'autres robots
    sont souvent garés."""
    centre, rayon = state.dump_center, state.dump["radius"] - 300
    d = c.distance_to(centre)
    if d <= rayon:
        return centre
    return (centre[0] + (c.x - centre[0]) * rayon / d,
            centre[1] + (c.y - centre[1]) * rayon / d)


def heurte(robot, commande):
    """Cap où `robot` a été arrêté net au dernier tour alors qu'on lui
    avait demandé de rouler (`commande` : sa dernière commande), ou None.
    Arrêté net = quelque chose barre la route : un ennemi (peut-être
    invisible, faute de Radar) ou un bouclier ennemi."""
    if (commande and commande.get("action") == "MOVE"
            and (commande.get("speed") or 0) > 0 and robot.speed == 0
            and robot.penalty == 0 and robot.heading is not None):
        return robot.heading
    return None


def aveugle(state):
    """Phase 2 et plus de Radar : l'équipe ne voit plus rien."""
    return state.phase == 2 and not state.my_robots_of_type("R")


def patrouille(state, robot):
    """Équipe aveugle (Radar détruit) en phase 2 : on ne reste pas garé, on
    tourne autour du centre de la zone, là où la tempête pousse tout le
    monde. On finira par heurter un ennemi (voir heurte) ou par le croiser
    à portée de tir."""
    return aller(state, robot, ronde(state, robot))


def ronde(state, c):
    """Point de patrouille : on tourne autour du centre de la zone, dans le
    sens des aiguilles d'une montre, un quart de tour à la fois, en
    traversant le centre une fois sur deux (TRAVERSEE tours sur 2 x
    TRAVERSEE) : deux équipes qui patrouillent ainsi finissent par se
    croiser, au lieu de se suivre sur le même cercle sans jamais se voir."""
    centre = state.safe_center
    rayon = min(RONDE, max(0.0, state.storm_radius(2) - 1500))
    if rayon < 500:
        return centre
    if (state.turn // TRAVERSEE) % 2 == 0 and c.distance_to(centre) > 600:
        return centre
    a = angle_to(centre, c.pos)
    if a is None:
        a = 0.0
    dx, dy = direction(a + 90)
    return state.clamp_to_zone((centre[0] + dx * rayon, centre[1] + dy * rayon), 2)
