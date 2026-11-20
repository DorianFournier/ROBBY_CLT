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

from robby import move
from robby.geometry import angle_to, direction

ROULE = 1500         # une proie qui roule « compte » comme plus loin
DERNIER_RECOURS = 4000  # un Collecteur garé « compte » comme bien plus loin
OBSTACLE = 1200      # un ennemi sur la route, à moins de ça : on le contourne
DETOUR = 60          # ... par la droite, de ce nombre de degrés
RONDE = 2500         # rayon de la patrouille autour du centre de la zone
ARRIVE = 800         # une piste atteinte (personne) est abandonnée


def aller(state, c, but, cible=None):
    """Vers `but`, en contournant par la droite un ennemi (autre que la
    cible) qui barre la route : deux Collecteurs face à face se croisent
    au lieu de se bloquer nez à nez."""
    cap = c.angle_to(but)
    if cap is not None:
        for e in state.enemies:
            a = c.angle_to(e)
            # un ennemi devant nous, plus près que le but : il barre la route
            if e is not cible and a is not None and c.distance_to(e) <= OBSTACLE \
                    and c.distance_to(e) < c.distance_to(but) \
                    and abs((a - cap + 180) % 360 - 180) < 45:
                return move(c, angle=(cap + DETOUR) % 360, speed=state.max_speed(c))
    return state.move_towards(c, but)


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


def ronde(state, c):
    """Point de patrouille : on tourne autour du centre de la zone, dans le
    sens des aiguilles d'une montre, un quart de tour à la fois."""
    centre = state.safe_center
    rayon = min(RONDE, max(0.0, state.storm_radius(2) - 1500))
    if rayon < 500:
        return centre
    a = angle_to(centre, c.pos)
    if a is None:
        a = 0.0
    dx, dy = direction(a + 90)
    return state.clamp_to_zone((centre[0] + dx * rayon, centre[1] + dy * rayon), 2)
