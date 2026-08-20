"""Field geometry: pin -> polygon, centroid, area.

The Build Brief wants a boundary drawn in under 30 seconds with no typing.
True Sentinel-2 segmentation is a scale path; for the prototype a pin becomes a
square plot of typical smallholder size, and a farmer-drawn polygon is accepted
verbatim. Both paths produce the same shape downstream.
"""

from __future__ import annotations

import math

# Mean smallholder plot in the Haryana wheat belt. Tunable per nation.
DEFAULT_PLOT_HA = 1.5

METRES_PER_DEGREE_LAT = 110_574.0


def _metres_per_degree_lng(latitude: float) -> float:
    return 111_320.0 * math.cos(math.radians(latitude))


def square_polygon_around(lat: float, lng: float, area_ha: float = DEFAULT_PLOT_HA) -> list[list[float]]:
    """Return a closed square polygon of `area_ha` centred on the pin.

    Points are [lat, lng] to match the Firestore `Field.polygon` contract.
    """
    side_m = math.sqrt(area_ha * 10_000.0)
    half_lat = (side_m / 2.0) / METRES_PER_DEGREE_LAT
    half_lng = (side_m / 2.0) / _metres_per_degree_lng(lat)

    return [
        [round(lat - half_lat, 6), round(lng - half_lng, 6)],
        [round(lat - half_lat, 6), round(lng + half_lng, 6)],
        [round(lat + half_lat, 6), round(lng + half_lng, 6)],
        [round(lat + half_lat, 6), round(lng - half_lng, 6)],
        [round(lat - half_lat, 6), round(lng - half_lng, 6)],
    ]


def centroid_of(polygon: list[list[float]]) -> dict[str, float]:
    """Arithmetic centroid of the polygon's distinct vertices."""
    points = _open_ring(polygon)
    return {
        "lat": round(sum(p[0] for p in points) / len(points), 6),
        "lng": round(sum(p[1] for p in points) / len(points), 6),
    }


def area_ha(polygon: list[list[float]]) -> float:
    """Shoelace area in hectares, projecting degrees to metres about the centroid.

    Accurate enough at field scale (sub-kilometre), where the local flat-earth
    approximation costs far less than the precision of the boundary itself.
    """
    points = _open_ring(polygon)
    if len(points) < 3:
        return 0.0

    origin_lat = sum(p[0] for p in points) / len(points)
    lat_scale = METRES_PER_DEGREE_LAT
    lng_scale = _metres_per_degree_lng(origin_lat)

    xy = [((p[1] - points[0][1]) * lng_scale, (p[0] - points[0][0]) * lat_scale) for p in points]

    total = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        total += x1 * y2 - x2 * y1

    return round(abs(total) / 2.0 / 10_000.0, 4)


def to_geojson(polygon: list[list[float]]) -> dict:
    """GeoJSON Polygon ([lng, lat] order) for Earth Engine and map layers."""
    ring = _open_ring(polygon)
    coordinates = [[p[1], p[0]] for p in ring]
    coordinates.append(coordinates[0])
    return {"type": "Polygon", "coordinates": [coordinates]}


def _open_ring(polygon: list[list[float]]) -> list[list[float]]:
    """Drop the duplicated closing vertex if present."""
    if len(polygon) > 1 and polygon[0] == polygon[-1]:
        return polygon[:-1]
    return polygon


def is_simple(polygon: list[list[float]]) -> bool:
    """True when no two edges of the boundary cross.

    A farmer dragging a finger across their own line makes a bow-tie, and the
    shoelace formula quietly sums the two lobes with opposite winding: a crossed
    square does not merely under-report, it returns 0.0 ha. Every per-hectare
    number downstream — seed, fertiliser, yield, credit — divides by that.
    Better to refuse the boundary than to advise on it.
    """
    ring = _open_ring(polygon)
    count = len(ring)
    if count < 4:  # a triangle cannot cross itself
        return True

    for i in range(count):
        a1, a2 = ring[i], ring[(i + 1) % count]
        # Start at i+2: neighbouring edges legitimately share a vertex.
        for j in range(i + 2, count):
            # The last edge wraps to vertex 0, so it neighbours edge 0.
            if i == 0 and j == count - 1:
                continue
            if _segments_cross(a1, a2, ring[j], ring[(j + 1) % count]):
                return False
    return True


def _segments_cross(p1, p2, q1, q2) -> bool:
    """Proper intersection test via the four orientation signs."""
    d1 = _orientation(q1, q2, p1)
    d2 = _orientation(q1, q2, p2)
    d3 = _orientation(p1, p2, q1)
    d4 = _orientation(p1, p2, q2)

    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True

    # Collinear overlap: a segment doubling back along its neighbour.
    return (
        (d1 == 0 and _on_segment(q1, q2, p1))
        or (d2 == 0 and _on_segment(q1, q2, p2))
        or (d3 == 0 and _on_segment(p1, p2, q1))
        or (d4 == 0 and _on_segment(p1, p2, q2))
    )


def _orientation(a, b, c) -> float:
    """Cross product sign: >0 left turn, <0 right turn, 0 collinear."""
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if abs(value) < 1e-12:
        return 0.0
    return value


def _on_segment(a, b, point) -> bool:
    return (
        min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
    )
