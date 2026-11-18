# robby/geometry.py
# Géométrie du MODE LIBRE (mêmes calculs que le serveur).
#
# Repère : x vers la droite, y vers le BAS (comme l'écran et la V1).
# Angles en degrés, sens horaire, 0 = haut : un angle a donne la direction
#   (dx, dy) = (sin a, -cos a)
#   0 -> (0, -1) haut   90 -> (1, 0) droite   180 -> (0, 1) bas   270 -> (-1, 0)

import math


def is_number(value) -> bool:
    """Nombre fini (int ou float), mais pas un booléen."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def direction(angle):
    """Vecteur unitaire (dx, dy) correspondant à un angle."""
    a = math.radians(angle)
    return math.sin(a), -math.cos(a)


def angle_to(src, dst):
    """Angle de src vers dst (0..360). None si les points sont confondus."""
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    if dx == 0 and dy == 0:
        return None
    return math.degrees(math.atan2(dx, -dy)) % 360


def angle_diff(a, b):
    """Écart entre deux angles, de 0 à 180."""
    return abs((a - b + 180) % 360 - 180)


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def in_sector(point, center, radius, heading, arc):
    """Le point est-il dans le secteur (part de tarte) de rayon `radius`,
    d'ouverture `arc` degrés, centré sur l'angle `heading` ?"""
    d = distance(point, center)
    if d > radius:
        return False
    if d < 1e-9:
        return True
    return angle_diff(angle_to(center, point), heading) <= arc / 2


def ray_circle(origin, angle, length, center, radius):
    """
    Distance le long du rayon (origin, angle) à laquelle il entre dans le
    cercle, ou None s'il ne le touche pas sur `length`. 0 si origin est dedans.
    """
    ux, uy = direction(angle)
    fx, fy = origin[0] - center[0], origin[1] - center[1]
    c = fx * fx + fy * fy - radius * radius
    if c <= 0:
        return 0.0
    b = fx * ux + fy * uy
    disc = b * b - c
    if disc < 0:
        return None
    t = -b - math.sqrt(disc)
    return t if 0 <= t <= length else None


def _ray_segment(origin, angle, length, a, b):
    """Distance le long du rayon jusqu'au segment [a, b] (None si aucun)."""
    ux, uy = direction(angle)
    sx, sy = b[0] - a[0], b[1] - a[1]
    denom = ux * sy - uy * sx
    if abs(denom) < 1e-12:
        return None
    qx, qy = a[0] - origin[0], a[1] - origin[1]
    t = (qx * sy - qy * sx) / denom
    s = (qx * uy - qy * ux) / denom
    return t if 0 <= t <= length and 0 <= s <= 1 else None


def ray_sector(origin, angle, length, center, radius, heading, arc):
    """
    Distance le long du rayon à laquelle il entre dans le secteur, ou None.
    L'entrée se fait forcément sur un bord du secteur (arc ou côtés) : on
    teste chaque point de croisement possible, du plus proche au plus loin.
    """
    ux, uy = direction(angle)

    def inside(t):
        p = (origin[0] + ux * t, origin[1] + uy * t)
        return in_sector(p, center, radius + 1e-6, heading, arc + 1e-6)

    candidates = [0.0]
    # cercle : les deux points de croisement
    fx, fy = origin[0] - center[0], origin[1] - center[1]
    b = fx * ux + fy * uy
    disc = b * b - (fx * fx + fy * fy - radius * radius)
    if disc >= 0:
        candidates += [-b - math.sqrt(disc), -b + math.sqrt(disc)]
    # les deux côtés droits
    for side in (-arc / 2, arc / 2):
        ex, ey = direction(heading + side)
        edge_end = (center[0] + ex * radius, center[1] + ey * radius)
        t = _ray_segment(origin, angle, length, center, edge_end)
        if t is not None:
            candidates.append(t)

    for t in sorted(c for c in candidates if 0 <= c <= length):
        if inside(t) or inside(min(t + 1e-3, length)):
            return t
    return None
