"""
h3tools.analytics
==================
Hierarchical navigation, spatial relationships, and distance functions.

Provides utilities for traversing the H3 cell hierarchy, finding spatial
neighbours, computing contiguous clusters, tracing grid paths, and
measuring distances between cells.  All functions handle h3-py v3/v4
API differences via :data:`h3tools.core.IS_H3_V4`.

Functions
---------
get_h3_parent
    Return the parent cell at a coarser resolution.
get_h3_children
    Return all child cells at a finer resolution.
get_h3_siblings
    Return all cells sharing the same parent as a given cell.
get_h3_family
    Return the parent and all sibling cells together.
get_h3_neighbors
    Return the k-ring of cells within *k* grid steps.
find_h3_contiguous_neighbors
    Cluster a set of H3 cells into spatially contiguous groups.
get_h3_path
    Find the ordered grid path between two cells.
get_h3_nearby
    Filter a set of H3 cells to those within a given hex radius of a target.
get_h3_distance
    Compute the grid-step or kilometre distance between two cells.
find_h3_hotspots
    Identify spatially elevated cells using z-score or MAD anomaly scoring.
get_h3_weighted_centroid
    Return the event-weighted geographic centre of a cell distribution.
get_h3_delta
    Compare two cell-count snapshots and return gained, lost, and stable cells.
get_h3_stats
    Return descriptive statistics for a cell-count distribution.
compact_h3_cells
    Compress a set of H3 cells to the coarsest mixed-resolution representation.
uncompact_h3_cells
    Expand a compact set of H3 cells to a uniform target resolution.
"""

from __future__ import annotations

__all__ = [
    "get_h3_parent",
    "get_h3_children",
    "get_h3_siblings",
    "get_h3_family",
    "get_h3_neighbors",
    "find_h3_contiguous_neighbors",
    "get_h3_path",
    "get_h3_nearby",
    "get_h3_distance",
    "find_h3_hotspots",
    "get_h3_weighted_centroid",
    "get_h3_delta",
    "get_h3_stats",
    "compact_h3_cells",
    "uncompact_h3_cells",
]

from collections import Counter
from math import atan2, cos, radians, sin, sqrt

import numpy as np
import h3

from h3tools.core import IS_H3_V4, get_h3_resolution, is_h3_pentagon
from h3tools._validators import _validate_h3_index, _validate_h3_resolution


# ── Path helpers ──────────────────────────────────────────────────────────────

def _try_path(start: str, end: str) -> list[str] | None:
    """Attempt a direct H3 grid path; return ``None`` on any failure."""
    try:
        return list(
            h3.grid_path_cells(start, end)
            if IS_H3_V4
            else h3.h3_line(start, end)
        )
    except Exception:
        return None


# ── Hierarchy ─────────────────────────────────────────────────────────────────

def get_h3_parent(h3_index: str, parent_resolution: int = None) -> str:
    """
    Return the parent cell of *h3_index* at a coarser resolution.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.
    parent_resolution : int, optional
        Target resolution for the parent cell.  Must be strictly less than
        the cell's current resolution and in [0, 14].  If omitted, defaults
        to ``current_resolution - 1``.

    Returns
    -------
    str
        H3 cell index string of the parent cell at *parent_resolution*.

    Raises
    ------
    ValueError
        If *h3_index* is invalid, if the cell is at resolution 0 (no
        parent exists), or if *parent_resolution* is not strictly less
        than the current resolution.

    Notes
    -----
    Internally delegates to ``h3.cell_to_parent`` (v4) or
    ``h3.h3_to_parent`` (v3).

    See Also
    --------
    get_h3_children : Traverse down the hierarchy instead.
    get_h3_family : Return both the parent and all sibling cells.

    Examples
    --------
    >>> cell = "89195da49b7ffff"   # resolution 9
    >>> parent = get_h3_parent(cell)
    >>> get_h3_resolution(parent) == 8
    True

    >>> grandparent = get_h3_parent(cell, parent_resolution=7)
    >>> get_h3_resolution(grandparent) == 7
    True
    """
    _validate_h3_index(h3_index)
    current = get_h3_resolution(h3_index)

    if parent_resolution is None:
        if current == 0:
            raise ValueError("Resolution-0 cells have no parent.")
        parent_resolution = current - 1
    else:
        if not isinstance(parent_resolution, int) or not (
            0 <= parent_resolution < current
        ):
            raise ValueError(
                f"parent_resolution must be an integer in "
                f"[0, {current - 1}], got {parent_resolution}."
            )

    return (
        h3.cell_to_parent(h3_index, parent_resolution)
        if IS_H3_V4
        else h3.h3_to_parent(h3_index, parent_resolution)
    )


def get_h3_children(h3_index: str, child_resolution: int = None) -> set[str]:
    """
    Return all child cells of *h3_index* at a finer resolution.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.
    child_resolution : int, optional
        Target resolution for child cells.  Must be strictly greater than
        the cell's current resolution and in [1, 15].  If omitted, defaults
        to ``current_resolution + 1``.

    Returns
    -------
    set of str
        H3 cell index strings of all children at *child_resolution*.
        A resolution-*n* cell typically has 7 children at resolution *n+1*.

    Raises
    ------
    ValueError
        If *h3_index* is invalid, if the cell is at resolution 15 (no
        children exist), or if *child_resolution* is not strictly greater
        than the current resolution.

    Notes
    -----
    Internally delegates to ``h3.cell_to_children`` (v4) or
    ``h3.to_children`` (v3).

    See Also
    --------
    get_h3_parent : Traverse up the hierarchy instead.
    get_h3_siblings : Return all sibling cells at the same resolution.

    Examples
    --------
    >>> cell = "89195da49b7ffff"   # resolution 9
    >>> children = get_h3_children(cell)
    >>> all(get_h3_resolution(c) == 10 for c in children)
    True
    >>> len(children) == 7
    True
    """
    _validate_h3_index(h3_index)
    current = get_h3_resolution(h3_index)

    if child_resolution is None:
        if current == 15:
            raise ValueError("Resolution-15 cells have no children.")
        child_resolution = current + 1
    else:
        if not isinstance(child_resolution, int) or not (
            current < child_resolution <= 15
        ):
            raise ValueError(
                f"child_resolution must be in [{current + 1}, 15], "
                f"got {child_resolution}."
            )

    children = (
        h3.cell_to_children(h3_index, child_resolution)
        if IS_H3_V4
        else h3.to_children(h3_index, child_resolution)
    )
    return set(children)


def get_h3_siblings(h3_index: str) -> set[str]:
    """
    Return all H3 cells that share the same parent as *h3_index*.

    The result always includes *h3_index* itself.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.  Must be at resolution ≥ 1 (resolution-0
        cells have no parent and therefore no siblings).

    Returns
    -------
    set of str
        All sibling H3 cell index strings at the same resolution as
        *h3_index*, including *h3_index* itself.  Typically 7 cells.

    Raises
    ------
    ValueError
        If *h3_index* is invalid or is a resolution-0 cell.

    See Also
    --------
    get_h3_parent : Return the shared parent cell.
    get_h3_children : Return children of a cell instead.
    get_h3_family : Return both the parent and all siblings together.

    Examples
    --------
    >>> cell = "89195da49b7ffff"   # resolution 9
    >>> siblings = get_h3_siblings(cell)
    >>> cell in siblings
    True
    >>> len(siblings) == 7
    True
    """
    _validate_h3_index(h3_index)
    current = get_h3_resolution(h3_index)
    if current == 0:
        raise ValueError("Resolution-0 cells have no siblings.")
    parent = get_h3_parent(h3_index)
    return get_h3_children(parent, current)


def get_h3_family(h3_index: str) -> dict[str, object]:
    """
    Return the parent cell and all sibling cells for *h3_index*.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.  Must be at resolution ≥ 1.

    Returns
    -------
    dict
        A dictionary with two keys:

        * ``'parent'`` : str — the parent cell index.
        * ``'siblings'`` : set of str — all cells at the same resolution
          that share the parent (including *h3_index* itself).

    Raises
    ------
    ValueError
        If *h3_index* is invalid or is a resolution-0 cell.

    See Also
    --------
    get_h3_parent : Return only the parent cell.
    get_h3_siblings : Return only the sibling set.
    get_h3_children : Return children of a cell.

    Examples
    --------
    >>> cell = "89195da49b7ffff"
    >>> family = get_h3_family(cell)
    >>> "parent" in family and "siblings" in family
    True
    >>> cell in family["siblings"]
    True
    >>> get_h3_resolution(family["parent"]) == get_h3_resolution(cell) - 1
    True
    """
    _validate_h3_index(h3_index)
    current = get_h3_resolution(h3_index)
    if current == 0:
        raise ValueError("Resolution-0 cells have no family.")
    parent = get_h3_parent(h3_index)
    return {"parent": parent, "siblings": get_h3_children(parent, current)}


# ── Neighbours ────────────────────────────────────────────────────────────────

def get_h3_neighbors(h3_index: str, k: int = 1) -> set[str]:
    """
    Return the set of H3 cells within *k* grid steps of *h3_index*.

    This is the H3 *k-ring* (or *grid disk*) centred on *h3_index*.
    The result always includes *h3_index* itself.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.
    k : int, optional
        Maximum grid-step distance from *h3_index*.
        ``k = 0`` returns only *h3_index* itself.
        ``k = 1`` returns the immediate ring of ≤ 6 neighbours plus the
        centre cell (7 cells for a regular hexagon).
        Default is ``1``.

    Returns
    -------
    set of str
        All H3 cell index strings within *k* grid steps, inclusive of
        *h3_index*.

    Raises
    ------
    ValueError
        If *h3_index* is invalid, or if *k* is not a non-negative integer.

    Notes
    -----
    Internally delegates to ``h3.grid_disk`` (v4) or ``h3.k_ring`` (v3).

    Pentagon cells have only 5 edges, so ``get_h3_neighbors(pentagon, k=1)``
    returns 6 cells (the pentagon itself plus 5 neighbours) rather than 7.
    Use :func:`h3tools.core.is_h3_pentagon` to check before calling if the
    exact ring size matters.

    See Also
    --------
    get_h3_nearby : Filter a pre-existing cell set to those within radius.
    find_h3_contiguous_neighbors : Cluster a set of cells by adjacency.
    get_h3_path : Find a linear path between two cells.
    get_h3_distance : Compute the grid-step distance between two cells.

    Examples
    --------
    >>> cell = "89195da49b7ffff"
    >>> ring_1 = get_h3_neighbors(cell, k=1)
    >>> cell in ring_1
    True
    >>> 1 < len(ring_1) <= 7
    True

    >>> get_h3_neighbors(cell, k=0) == {cell}
    True
    """
    _validate_h3_index(h3_index)
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        raise ValueError(f"k must be a non-negative integer, got {k!r}.")

    result = (
        h3.grid_disk(h3_index, k=k) if IS_H3_V4 else h3.k_ring(h3_index, k)
    )
    return set(result)


def find_h3_contiguous_neighbors(h3_index_set: set) -> list[set[str]]:
    """
    Cluster a set of H3 cell indices into spatially contiguous groups.

    Uses a breadth-first search (BFS) to identify connected components
    in the adjacency graph of the input cells.  Two cells are considered
    connected when one is an immediate neighbour (``k=1``) of the other.

    Parameters
    ----------
    h3_index_set : set of str
        Collection of H3 index strings to cluster.  All cells must be
        valid H3 indices.  For meaningful results, all cells should be at
        the same resolution.

    Returns
    -------
    list of set of str
        Each element is a set of H3 cell indices forming one spatially
        contiguous cluster.  The list is unordered.  Returns an empty list
        if *h3_index_set* is empty.

    Raises
    ------
    ValueError
        If any element of *h3_index_set* is not a valid H3 cell index.

    Notes
    -----
    Only adjacency *within the input set* is considered.  Cells that are
    grid-neighbours but not present in *h3_index_set* do not act as
    bridges between clusters.

    See Also
    --------
    get_h3_neighbors : Return the k-ring of a single cell.
    get_h3_nearby : Filter a cell set to those within a radius of a target.
    get_h3_path : Find a grid path between two cells.

    Examples
    --------
    >>> from h3tools.geo import point_to_h3
    >>> from shapely.geometry import Point
    >>> london = point_to_h3(Point(-0.1278, 51.5074), 9)
    >>> paris  = point_to_h3(Point(2.3522, 48.8566), 9)
    >>> clusters = find_h3_contiguous_neighbors({london, paris})
    >>> len(clusters) == 2
    True

    >>> disk = get_h3_neighbors(london, k=1)
    >>> len(find_h3_contiguous_neighbors(disk)) == 1
    True
    """
    if not h3_index_set:
        return []

    for cell in h3_index_set:
        _validate_h3_index(cell)

    remaining = set(h3_index_set)
    clusters: list[set[str]] = []

    while remaining:
        seed = remaining.pop()
        cluster: set[str] = {seed}
        queue = [seed]

        while queue:
            current = queue.pop()
            for neighbor in get_h3_neighbors(current, k=1):
                if neighbor in remaining:
                    remaining.discard(neighbor)
                    cluster.add(neighbor)
                    queue.append(neighbor)

        clusters.append(cluster)

    return clusters


# ── Paths ─────────────────────────────────────────────────────────────────────

def get_h3_path(start_h3: str, end_h3: str) -> list[str]:
    """
    Return the ordered list of H3 cells connecting two cells.

    Both cells must be at the same resolution.  The path is computed using
    the H3 grid-path algorithm, which finds the shortest sequence of
    adjacent cells from *start_h3* to *end_h3*.

    Parameters
    ----------
    start_h3 : str
        Valid H3 cell index string for the start of the path.
    end_h3 : str
        Valid H3 cell index string for the end of the path.  Must be at
        the same resolution as *start_h3*.

    Returns
    -------
    list of str
        Ordered H3 cell index strings from *start_h3* to *end_h3*,
        inclusive of both endpoints.  If *start_h3* == *end_h3*, returns
        a single-element list.

    Raises
    ------
    ValueError
        If either index is invalid, the cells are at different resolutions,
        or no navigable path exists even after pentagon detour attempts.

    Notes
    -----
    The path is ordered from start to end; index 0 is always *start_h3*
    and index -1 is always *end_h3*.

    Internally delegates to ``h3.grid_path_cells`` (v4) or
    ``h3.h3_line`` (v3).

    If the direct path crosses a pentagon, the function automatically tries
    routing through each of the pentagon's 5 neighbours (across all 12
    pentagons at the resolution, 60 candidates at most) and returns the
    shortest viable detour.  A ``ValueError`` is only raised if no detour
    succeeds.

    See Also
    --------
    points_to_h3_path : Derive a path from two geographic ``Point`` objects.
    get_h3_neighbors : Return all cells within k grid steps.
    get_h3_distance : Compute only the distance without returning the path.

    Examples
    --------
    >>> path = get_h3_path("89195da49b7ffff", "89195da49b7ffff")
    >>> len(path) == 1
    True

    >>> neighbors = get_h3_neighbors("89195da49b7ffff", k=1) - {"89195da49b7ffff"}
    >>> neighbor = next(iter(neighbors))
    >>> path = get_h3_path("89195da49b7ffff", neighbor)
    >>> path[0] == "89195da49b7ffff" and path[-1] == neighbor
    True
    """
    _validate_h3_index(start_h3)
    _validate_h3_index(end_h3)

    if get_h3_resolution(start_h3) != get_h3_resolution(end_h3):
        raise ValueError(
            "start_h3 and end_h3 must be at the same H3 resolution."
        )

    direct = _try_path(start_h3, end_h3)
    if direct is not None:
        return direct

    # Pentagon detour: try routing through each non-pentagon neighbour of every
    # pentagon at this resolution; return the shortest successful detour.
    res = get_h3_resolution(start_h3)
    pentagons = (
        h3.get_pentagons(res) if IS_H3_V4 else h3.get_pentagon_indexes(res)
    )
    best: list[str] | None = None
    for pent in pentagons:
        ring = set(h3.grid_disk(pent, 1) if IS_H3_V4 else h3.k_ring(pent, 1))
        for waypoint in ring - {pent}:
            if is_h3_pentagon(waypoint):
                continue
            seg1 = _try_path(start_h3, waypoint)
            if seg1 is None:
                continue
            seg2 = _try_path(waypoint, end_h3)
            if seg2 is None:
                continue
            candidate = seg1 + seg2[1:]
            if best is None or len(candidate) < len(best):
                best = candidate

    if best is not None:
        return best

    raise ValueError(
        f"Could not find a navigable path from {start_h3!r} to {end_h3!r}: "
        "direct path crosses a pentagon with no viable detour."
    )


# ── Nearby filter ─────────────────────────────────────────────────────────────

def get_h3_nearby(
    h3_index: str,
    h3_index_set: set[str],
    hex_radius: int,
) -> dict[str, int]:
    """
    Filter a set of H3 cells to those within a given hex radius of a target.

    Computes the k-disk (all cells within *hex_radius* grid steps) centred
    on *h3_index*, intersects it with *h3_index_set*, and returns the
    matching cells mapped to their exact grid distance from *h3_index*.

    Parameters
    ----------
    h3_index : str
        The target H3 cell index.  Acts as the centre of the search.
    h3_index_set : set of str
        The pool of candidate cells to filter.  All cells must be valid
        H3 indices at the same resolution as *h3_index*.
    hex_radius : int
        Maximum grid-step distance from *h3_index* to include.  Must be a
        non-negative integer.  ``hex_radius=0`` returns only *h3_index*
        itself (if it is in *h3_index_set*).

    Returns
    -------
    dict of {str: int}
        Mapping of ``{h3_index: grid_distance}`` for every cell in
        *h3_index_set* that lies within *hex_radius* grid steps of
        *h3_index*.  An empty dict is returned when no cells qualify.

    Raises
    ------
    ValueError
        If *h3_index* is invalid; if any cell in *h3_index_set* is
        invalid; if any cell in *h3_index_set* is at a different
        resolution than *h3_index*; or if *hex_radius* is not a
        non-negative integer.

    See Also
    --------
    get_h3_neighbors : Return all cells within k grid steps (no set filter).
    get_h3_distance : Compute the grid distance between any two cells.

    Examples
    --------
    >>> from h3tools.geo import point_to_h3
    >>> from shapely.geometry import Point
    >>> target = point_to_h3(Point(-0.1278, 51.5074), 9)
    >>> pool = get_h3_neighbors(target, k=3)   # 37-cell disk
    >>> nearby = get_h3_nearby(target, pool, hex_radius=1)
    >>> len(nearby) <= 7        # at most 7 cells within 1 step
    True
    >>> nearby[target] == 0     # target itself is at distance 0
    True
    >>> all(v <= 1 for v in nearby.values())
    True
    """
    _validate_h3_index(h3_index)
    if isinstance(hex_radius, bool) or not isinstance(hex_radius, int) or hex_radius < 0:
        raise ValueError(
            f"hex_radius must be a non-negative integer, got {hex_radius!r}."
        )

    target_res = get_h3_resolution(h3_index)
    h3_index_set = set(h3_index_set)

    for cell in h3_index_set:
        _validate_h3_index(cell)
        cell_res = get_h3_resolution(cell)
        if cell_res != target_res:
            raise ValueError(
                f"All cells in h3_index_set must be at resolution {target_res} "
                f"(same as h3_index), but found resolution {cell_res} "
                f"for cell {cell!r}."
            )

    disk = get_h3_neighbors(h3_index, k=hex_radius)
    nearby = disk & h3_index_set

    return {cell: get_h3_distance(h3_index, cell, unit="grid") for cell in nearby}


# ── Distance ──────────────────────────────────────────────────────────────────

def get_h3_distance(
    h3_from: str,
    h3_to: str,
    unit: str = "grid",
) -> int | float:
    """
    Compute the distance between two H3 cells.

    Supports two distance metrics: grid-step count and great-circle
    kilometres.

    Parameters
    ----------
    h3_from : str
        Origin H3 cell index string.
    h3_to : str
        Destination H3 cell index string.
    unit : {'grid', 'km'}, optional
        Distance metric to use:

        * ``'grid'`` *(default)* — integer count of grid steps between the
          cells.  Both cells must be at the same resolution.
        * ``'km'`` — great-circle distance in kilometres between the
          geographic centres of the two cells, computed with the
          Haversine formula.  Cells may be at different resolutions.

    Returns
    -------
    int or float
        * ``int`` when *unit* is ``'grid'``.
        * ``float`` when *unit* is ``'km'``.

    Raises
    ------
    ValueError
        If either index is invalid; if *unit* is ``'grid'`` and the cells
        are at different resolutions; if the grid distance cannot be
        computed (e.g. path crosses a pentagon or cells are too far apart);
        or if *unit* is not ``'grid'`` or ``'km'``.

    Notes
    -----
    Grid distance delegates to ``h3.grid_distance`` (v4) or
    ``h3.h3_distance`` (v3).  Kilometre distance is computed independently
    using the Haversine formula (Earth radius 6 371 km).

    Grid-step distance raises ``ValueError`` if the shortest path between
    the two cells crosses a pentagon.  Use
    :func:`h3tools.core.is_h3_pentagon` to check cells in sensitive regions
    before requesting grid-step distances.

    See Also
    --------
    get_h3_path : Return all cells along the shortest grid path.
    get_h3_nearby : Filter a cell set by hex radius from a target.
    get_h3_neighbors : Return all cells within k grid steps.

    Examples
    --------
    >>> neighbors = get_h3_neighbors("89195da49b7ffff", k=1) - {"89195da49b7ffff"}
    >>> neighbor = next(iter(neighbors))
    >>> get_h3_distance("89195da49b7ffff", neighbor, unit="grid")
    1

    >>> dist_km = get_h3_distance("89195da49b7ffff", neighbor, unit="km")
    >>> dist_km > 0
    True
    """
    _validate_h3_index(h3_from)
    _validate_h3_index(h3_to)

    if unit == "grid":
        if get_h3_resolution(h3_from) != get_h3_resolution(h3_to):
            raise ValueError(
                "Both cells must be at the same resolution for grid distance."
            )
        try:
            return (
                h3.grid_distance(h3_from, h3_to)
                if IS_H3_V4
                else h3.h3_distance(h3_from, h3_to)
            )
        except Exception as exc:
            raise ValueError(
                f"Cannot compute grid distance between {h3_from!r} and "
                f"{h3_to!r}: {exc}"
            ) from exc

    if unit == "km":
        from h3tools.geo import h3_to_point
        lat1, lon1 = h3_to_point(h3_from, return_latlon=True)
        lat2, lon2 = h3_to_point(h3_to, return_latlon=True)
        R = 6_371.0
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    raise ValueError(f"unit must be 'grid' or 'km', got {unit!r}.")


# ── Hotspot detection ─────────────────────────────────────────────────────────

def find_h3_hotspots(
    cell_counts: dict[str, int],
    k: int = 1,
    threshold: float = 1.0,
    method: str = "zscore",
) -> dict[str, float]:
    """
    Identify H3 cells with spatially elevated event counts.

    For each cell, the local neighbourhood mean (z-score) or median
    (MAD score) is computed across the cell and its *k*-ring neighbours
    that are present in *cell_counts*.  The score is then compared against
    the global distribution to produce a standardised anomaly score.
    Only cells whose score meets or exceeds *threshold* are returned.

    Parameters
    ----------
    cell_counts : dict of {str: int}
        Mapping of H3 cell index to integer event count.  Accepts a
        :class:`collections.Counter` directly.
    k : int, optional
        Neighbourhood radius in grid steps.  Default is ``1`` (immediate
        ring only).  Larger values produce spatially smoother scores.
    threshold : float, optional
        Minimum anomaly score to include a cell in the result.  Typical
        values depend on *method*:

        * ``'zscore'``  — ``1.0`` (one σ above mean) to ``2.0`` (two σ).
        * ``'mad'``     — ``3.5`` (the conventional outlier threshold for
          the modified z-score).

        Default is ``1.0``.
    method : {'zscore', 'mad'}, optional
        Scoring method:

        * ``'zscore'`` *(default)* — standardises the local neighbourhood
          mean against the global mean and standard deviation.  Sensitive
          to extreme values; best when counts are roughly symmetric.
        * ``'mad'`` — standardises the local neighbourhood median against
          the global median and Median Absolute Deviation (MAD).  Robust
          to outliers; recommended for right-skewed event-count data.

    Returns
    -------
    dict of {str: float}
        Mapping of H3 cell index to anomaly score for every cell whose
        score ≥ *threshold*.  Returns an empty dict when no cells qualify
        or the global distribution has zero variance.

    Raises
    ------
    ValueError
        If any cell index is invalid; if *k* is not a positive integer;
        if *threshold* is not a real number; or if *method* is not
        ``'zscore'`` or ``'mad'``.

    Notes
    -----
    The spatial component — averaging over the *k*-ring — mirrors the
    logic of the Getis-Ord Gi* statistic.  Only neighbours present in
    *cell_counts* contribute; cells absent from the dict are treated as
    having count zero implicitly (they are not added to the neighbourhood
    sum, which gives a conservative score for edge cells).

    When MAD is zero (all values identical or all counts equal), the
    function falls back to Mean Absolute Deviation before returning an
    empty dict if that too is zero.

    See Also
    --------
    get_h3_nearby : Filter cells by proximity to a single target cell.
    find_h3_contiguous_neighbors : Cluster cells by spatial adjacency.
    get_h3_weighted_centroid : Find the centre of mass of a distribution.

    Examples
    --------
    >>> from collections import Counter
    >>> counts = Counter({"89195da49b7ffff": 100, "897a6e42ca3ffff": 2})
    >>> hotspots = find_h3_hotspots(counts, k=1, threshold=0.5)
    >>> isinstance(hotspots, dict)
    True

    >>> hotspots_mad = find_h3_hotspots(counts, k=1, threshold=0.5, method="mad")
    >>> isinstance(hotspots_mad, dict)
    True
    """
    if not cell_counts:
        return {}
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError(f"k must be a positive integer, got {k!r}.")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError(f"threshold must be a real number, got {threshold!r}.")
    if method not in ("zscore", "mad"):
        raise ValueError(f"method must be 'zscore' or 'mad', got {method!r}.")

    for cell in cell_counts:
        _validate_h3_index(cell)

    values = np.array(list(cell_counts.values()), dtype=float)
    cell_set = set(cell_counts)

    if method == "zscore":
        global_mean = float(values.mean())
        global_std = float(values.std())
        if global_std == 0.0:
            return {}

        result = {}
        for cell, _ in cell_counts.items():
            ring = get_h3_neighbors(cell, k=k)
            local_cells = (ring & cell_set) | {cell}
            local_mean = float(np.mean([cell_counts[c] for c in local_cells]))
            score = (local_mean - global_mean) / global_std
            if score >= threshold:
                result[cell] = round(score, 4)
        return result

    # method == "mad"
    global_median = float(np.median(values))
    mad = float(np.median(np.abs(values - global_median)))
    if mad == 0.0:
        mad = float(np.mean(np.abs(values - global_median)))
    if mad == 0.0:
        return {}

    result = {}
    for cell, _ in cell_counts.items():
        ring = get_h3_neighbors(cell, k=k)
        local_cells = (ring & cell_set) | {cell}
        local_median = float(np.median([cell_counts[c] for c in local_cells]))
        score = 0.6745 * (local_median - global_median) / mad
        if score >= threshold:
            result[cell] = round(score, 4)
    return result


# ── Weighted centroid ─────────────────────────────────────────────────────────

def get_h3_weighted_centroid(cell_counts: dict[str, int]):
    """
    Return the event-weighted geographic centre of an H3 cell distribution.

    Each cell's centre point is weighted by its event count.  The result is
    the geographic *centre of mass* — the location that minimises the
    weighted sum of distances to all cells.

    Parameters
    ----------
    cell_counts : dict of {str: int}
        Mapping of H3 cell index to integer event count.  Accepts a
        :class:`collections.Counter` directly.  All counts must be
        non-negative; zero-count cells contribute no weight.

    Returns
    -------
    shapely.geometry.Point
        WGS-84 point (``x = longitude``, ``y = latitude``) representing
        the weighted centroid.

    Raises
    ------
    ValueError
        If *cell_counts* is empty, if any cell index is invalid, or if
        the total event count is zero (no weight to distribute).

    Notes
    -----
    Cell centre coordinates are obtained via
    :func:`h3tools.geo.h3_to_point`.  The weighted average is computed
    directly on raw latitude/longitude values, which introduces small
    errors near the poles and across the antimeridian.  For most
    geospatial analytics use cases the error is negligible.

    See Also
    --------
    find_h3_hotspots : Identify cells with elevated counts.
    get_h3_delta : Compare two count snapshots over time.

    Examples
    --------
    >>> from collections import Counter
    >>> from shapely.geometry import Point
    >>> counts = Counter({"89195da49b7ffff": 10, "897a6e42ca3ffff": 10})
    >>> centroid = get_h3_weighted_centroid(counts)
    >>> isinstance(centroid, Point)
    True
    """
    if not cell_counts:
        raise ValueError("cell_counts is empty — cannot compute centroid.")

    for cell in cell_counts:
        _validate_h3_index(cell)

    total = sum(cell_counts.values())
    if total == 0:
        raise ValueError(
            "Total event count is zero — cannot compute weighted centroid."
        )

    from h3tools.geo import h3_to_point
    from shapely.geometry import Point

    w_lat = w_lon = 0.0
    for cell, count in cell_counts.items():
        lat, lon = h3_to_point(cell, return_latlon=True)
        w_lat += lat * count
        w_lon += lon * count

    return Point(w_lon / total, w_lat / total)


# ── Snapshot delta ────────────────────────────────────────────────────────────

def get_h3_delta(
    snapshot_a: dict[str, int],
    snapshot_b: dict[str, int],
) -> dict:
    """
    Compare two H3 cell-count snapshots and return what changed.

    Uses :class:`collections.Counter` arithmetic to compute per-cell
    count changes between two points in time.  Cells that grew or appeared
    land in ``'gained'``; cells that shrank or disappeared land in
    ``'lost'``; cells with identical counts in both snapshots are
    ``'stable'``.

    Parameters
    ----------
    snapshot_a : dict of {str: int}
        Earlier snapshot.  Accepts a :class:`collections.Counter`.
    snapshot_b : dict of {str: int}
        Later snapshot.  Accepts a :class:`collections.Counter`.

    Returns
    -------
    dict
        A dictionary with the following keys:

        ==================  ================================================
        Key                 Value
        ==================  ================================================
        ``'gained'``        dict — ``{cell: count_increase}`` for cells
                            where *b* > *a* (new cells or grown cells).
        ``'lost'``          dict — ``{cell: count_decrease}`` for cells
                            where *a* > *b* (removed or shrunk cells).
        ``'stable'``        set — cell indices with identical counts in
                            both snapshots.
        ``'net_change'``    int — total event count in *b* minus total in
                            *a*.  Positive means overall growth.
        ==================  ================================================

    Raises
    ------
    ValueError
        If any cell index in either snapshot is invalid.

    Notes
    -----
    Counter subtraction clips at zero: ``Counter(b) - Counter(a)`` keeps
    only keys where ``b[key] > a[key]``, returning the positive difference.
    This means a cell that goes from count 5 to count 2 appears in
    ``'lost'`` with value ``3``, not ``-3``.

    Cells absent from a snapshot are treated as having count zero,
    consistent with Counter semantics.

    See Also
    --------
    find_h3_hotspots : Detect elevated cells within a single snapshot.
    get_h3_weighted_centroid : Find the centre of mass of a snapshot.

    Examples
    --------
    >>> from collections import Counter
    >>> a = Counter({"89195da49b7ffff": 5, "897a6e42ca3ffff": 3})
    >>> b = Counter({"89195da49b7ffff": 5, "89426516823ffff": 4})
    >>> delta = get_h3_delta(a, b)
    >>> "89426516823ffff" in delta["gained"]   # new cell
    True
    >>> "897a6e42ca3ffff" in delta["lost"]     # removed cell
    True
    >>> "89195da49b7ffff" in delta["stable"]   # unchanged cell
    True
    >>> delta["net_change"]
    1
    """
    for cell in snapshot_a:
        _validate_h3_index(cell)
    for cell in snapshot_b:
        _validate_h3_index(cell)

    a = Counter(snapshot_a)
    b = Counter(snapshot_b)

    gained = dict(b - a)
    lost   = dict(a - b)
    stable = {c for c in a if c in b and a[c] == b[c]}

    return {
        "gained":     gained,
        "lost":       lost,
        "stable":     stable,
        "net_change": sum(b.values()) - sum(a.values()),
    }


# ── Summary statistics ────────────────────────────────────────────────────────

def get_h3_stats(cell_counts: dict[str, int | float]) -> dict:
    """
    Return descriptive statistics for a cell-count distribution.

    Accepts any mapping from H3 cell index to a numeric count or weight,
    and returns a summary dict covering total events, spatial coverage,
    basic distributional statistics, and the highest-activity cells.

    Parameters
    ----------
    cell_counts : dict[str, int | float]
        Mapping of H3 cell index → count (or weight).  All keys must be
        valid H3 cell indices at the same resolution; counts may be int or
        float but must be non-negative.

    Returns
    -------
    dict
        A dictionary with the following keys:

        ``"total_events"`` : int | float
            Sum of all counts.
        ``"unique_cells"`` : int
            Number of cells with a non-zero count.
        ``"mean"`` : float
            Arithmetic mean of counts across all cells.
        ``"median"`` : float
            Median count.
        ``"std"`` : float
            Population standard deviation of counts.
        ``"min"`` : int | float
            Minimum count.
        ``"max"`` : int | float
            Maximum count.
        ``"p25"`` : float
            25th percentile (first quartile).
        ``"p75"`` : float
            75th percentile (third quartile).
        ``"p95"`` : float
            95th percentile.
        ``"top_cells"`` : dict[str, int | float]
            Up to 5 cells with the highest counts, ordered from highest to
            lowest.

    Raises
    ------
    ValueError
        If *cell_counts* is empty, or if any key is not a valid H3 cell
        index, or if any count is negative.
    TypeError
        If *cell_counts* is not a mapping.

    Notes
    -----
    Statistics are computed with :mod:`numpy` over the *values* of
    *cell_counts*, so the percentile values reflect the distribution of
    per-cell counts, not geographic spread.

    Examples
    --------
    >>> from collections import Counter
    >>> counts = Counter({
    ...     "89195da49b7ffff": 10,
    ...     "89195da49b3ffff": 5,
    ...     "89195da49bbffff": 2,
    ... })
    >>> stats = get_h3_stats(counts)
    >>> stats["total_events"]
    17
    >>> stats["unique_cells"]
    3
    >>> stats["top_cells"]  # doctest: +SKIP
    {"89195da49b7ffff": 10, "89195da49b3ffff": 5, "89195da49bbffff": 2}
    """
    if not hasattr(cell_counts, "items"):
        raise TypeError(
            f"cell_counts must be a dict-like mapping, got {type(cell_counts).__name__!r}."
        )
    if not cell_counts:
        raise ValueError("get_h3_stats() requires at least one cell.")

    for cell, count in cell_counts.items():
        _validate_h3_index(cell)
        if count < 0:
            raise ValueError(
                f"Count for cell {cell!r} is negative ({count}); counts must be >= 0."
            )

    values = np.array(list(cell_counts.values()), dtype=float)
    sorted_cells = sorted(cell_counts.items(), key=lambda kv: kv[1], reverse=True)

    return {
        "total_events": float(values.sum()) if values.dtype == float else int(values.sum()),
        "unique_cells": int((values > 0).sum()),
        "mean":         float(np.mean(values)),
        "median":       float(np.median(values)),
        "std":          float(np.std(values)),
        "min":          float(np.min(values)),
        "max":          float(np.max(values)),
        "p25":          float(np.percentile(values, 25)),
        "p75":          float(np.percentile(values, 75)),
        "p95":          float(np.percentile(values, 95)),
        "top_cells":    dict(sorted_cells[:5]),
    }


# ── Compaction ────────────────────────────────────────────────────────────────

def compact_h3_cells(cells) -> set[str]:
    """
    Compress a set of H3 cells to the coarsest mixed-resolution representation.

    Replaces groups of seven sibling cells (cells sharing the same parent)
    with their common parent cell wherever possible, recursively, producing
    the smallest set of cells that covers the same area.  The result may
    contain cells at different resolutions.

    Compaction is particularly useful when working with large cell sets
    covering broad areas — filling a country at resolution 9 produces
    millions of cells, but the compacted form may be orders of magnitude
    smaller.

    Parameters
    ----------
    cells : iterable of str
        H3 cell index strings to compact.  All cells must be valid H3
        indices.  Mixed resolutions are accepted.

    Returns
    -------
    set[str]
        Compacted set of H3 cell indices at mixed resolutions.  Returns an
        empty set if *cells* is empty.

    Raises
    ------
    ValueError
        If any cell index is not a valid H3 cell.

    See Also
    --------
    uncompact_h3_cells : Expand a compacted set back to a uniform resolution.
    polygon_to_h3 : Fill a polygon with H3 cells (produces compactable output).

    Examples
    --------
    >>> import h3
    >>> # Fill a k-ring and compact — siblings collapse to their parent
    >>> cells = set(h3.grid_disk("89195da49b7ffff", 1))
    >>> compacted = compact_h3_cells(cells)
    >>> len(compacted) <= len(cells)
    True
    """
    cells = list(cells)
    if not cells:
        return set()
    for cell in cells:
        _validate_h3_index(cell)
    result = h3.compact_cells(cells) if IS_H3_V4 else h3.compact(cells)
    return set(result)


def uncompact_h3_cells(cells, resolution: int) -> set[str]:
    """
    Expand a compact set of H3 cells to a uniform target resolution.

    The inverse of :func:`compact_h3_cells`.  Each cell in *cells* is
    expanded to all of its descendants at *resolution*.  Cells already at
    *resolution* are passed through unchanged.

    Parameters
    ----------
    cells : iterable of str
        H3 cell index strings to expand.  May contain cells at mixed
        resolutions, as produced by :func:`compact_h3_cells`.
    resolution : int
        Target resolution (0–15).  Must be >= the resolution of every cell
        in *cells*.

    Returns
    -------
    set[str]
        Flat set of H3 cell indices all at *resolution*.  Returns an empty
        set if *cells* is empty.

    Raises
    ------
    ValueError
        If any cell index is invalid, if *resolution* is outside [0, 15],
        or if *resolution* is coarser than any cell in *cells*.

    See Also
    --------
    compact_h3_cells : Compress cells to mixed-resolution form.

    Examples
    --------
    >>> import h3
    >>> cells = set(h3.grid_disk("89195da49b7ffff", 1))
    >>> compacted   = compact_h3_cells(cells)
    >>> uncompacted = uncompact_h3_cells(compacted, resolution=9)
    >>> uncompacted == cells
    True
    """
    cells = list(cells)
    if not cells:
        return set()
    _validate_h3_resolution(resolution)
    for cell in cells:
        _validate_h3_index(cell)
    result = (
        h3.uncompact_cells(cells, resolution)
        if IS_H3_V4
        else h3.uncompact(cells, resolution)
    )
    return set(result)
