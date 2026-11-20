# bots/chasse.py
# Le Collecteur en phase 2 : la chasse aux prisonniers pour la déchèterie.
#
# Rappel des règles : un Collecteur qui finit son tour au contact d'un ennemi
# À L'ARRÊT l'attrape. Un ennemi qui roule ne peut pas être attrapé... sauf
# qu'en lui coupant la route, on le BLOQUE (deux ennemis ne se traversent
# pas) : il s'arrête net, au contact, et il est pris dans la foulée.
#
# Ce que fait le Collecteur :
#   1. il porte un prisonnier : droit vers la déchèterie ;
#   2. sinon il choisit une proie parmi les ennemis visibles (jamais un
#      Collecteur : il est imprenable pour un Collecteur) : d'abord ceux
#      qui sont à l'arrêt, puis les plus proches. Il fonce sur une proie
#      arrêtée, et vise l'endroit où sera une proie qui roule (pour lui
#      couper la route) ;
#   3. « offensif » (plus aucun Destructeur dans l'équipe : c'est lui qui
#      doit marquer les points) : il chasse toutes les proies, même gardées
#      par un Destructeur ennemi, et sans proie visible il va où on a vu un
#      ennemi pour la dernière fois, sinon il PATROUILLE autour du centre de
#      la zone (où la tempête pousse tout le monde) : son Radar, qui le
#      suit, balaie ainsi les environs ;
#   4. « prudent » (nos Destructeurs se battent) : il ne chasse que les
#      proies proches qu'aucun Destructeur ennemi ne couvre, et rend la main
#      (None) s'il n'y en a pas.

from robby import move
from robby.geometry import angle_to, direction

PROCHE = 4000        # mode prudent : proies à moins de ça
ROULE = 1500         # une proie qui roule « compte » comme plus loin
OBSTACLE = 1200      # un ennemi sur la route, à moins de ça : on le contourne
DETOUR = 60          # ... par la droite, de ce nombre de degrés
RONDE = 2500         # rayon de la patrouille autour du centre de la zone
ARRIVE = 800         # une piste atteinte (personne) est abandonnée


def aller(state, c, but, cible=None):
    """Vers `but`, en contournant par la droite un ennemi (autre que la
    cible) qui barre la route : deux Collecteurs face à face se croisent
    au lieu de se bloquer nez à nez."""
    cap = c.angle_to(but)
    if cap is not None and c.distance_to(but) > OBSTACLE:
        for e in state.enemies:
            a = c.angle_to(e)
            if e is not cible and a is not None and c.distance_to(e) <= OBSTACLE \
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
        return state.move_towards(c, state.dump_center)
    if offensif is None:
        offensif = not state.my_robots_of_type("K")
    # un Collecteur ennemi n'est jamais une proie : chargé, il est imprenable
    # (règle) ; libre, il nous prendrait en même temps (prise mutuelle :
    # personne), et les deux resteraient bloqués nez à nez
    tireurs = [e for e in state.enemies if e.type == "K"]
    proies = [e for e in state.enemies if e.type != "C"]
    souvenirs = list(souvenirs)
    portee = state.config["destructor_range"] + state.robot_radius

    def couverte(e):
        return any(k is not e and k.distance_to(e) <= portee for k in tireurs)

    def cout(e):
        return c.distance_to(e) + (0 if e.speed == 0 else ROULE)

    if not offensif:
        proies = [e for e in proies if cout(e) <= PROCHE and not couverte(e)]
    if proies:
        meilleur = min(cout(e) for e in proies)
        cible = state.nearest(c, [e for e in proies if cout(e) <= meilleur + 1])
        if cible.speed == 0:
            return aller(state, c, cible.pos, cible)
        # lui couper la route : là où il sera à la fin du tour
        return aller(state, c, state.clamp_to_zone(state.predict(cible), 1), cible)
    if not offensif:
        return None
    pistes = [p for p in souvenirs if c.distance_to(p) > ARRIVE]
    if pistes:                                        # 3. sur la piste
        return aller(state, c, state.clamp_to_zone(state.nearest(c, pistes), 2))
    return aller(state, c, ronde(state, c))


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
