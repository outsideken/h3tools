"""
h3tools.core
=============
H3 version compatibility shim and basic cell-property helpers.

All public functions handle the API differences between h3-py v3.x and
v4.x transparently via the module-level :data:`IS_H3_V4` flag, which is
evaluated once at import time.

Module Attributes
-----------------
IS_H3_V4 : bool
    ``True`` when the installed h3-py package is version 4.x; ``False``
    for v3.x.  Used throughout h3tools to branch between the two APIs.

Functions
---------
is_h3_valid
    Check whether a string is a valid H3 cell index.
is_h3_pentagon
    Return ``True`` if an H3 cell is one of the 12 pentagon cells per resolution.
get_h3_resolution
    Return the resolution (0–15) of an H3 cell.
get_h3_cell_area
    Return the average area (km²) for the resolution of a cell.
get_h3_cell_edge_length
    Return the average edge length (km) for the resolution of a cell.
"""

from __future__ import annotations

import h3

from h3tools._validators import _validate_h3_index, _validate_h3_resolution

__all__ = [
    "is_h3_valid",
    "is_h3_pentagon",
    "get_h3_resolution",
    "get_h3_cell_area",
    "get_h3_cell_edge_length",
]

# ── Version detection ─────────────────────────────────────────────────────────
IS_H3_V4: bool = h3.__version__.startswith("4")

# ── Public helpers ────────────────────────────────────────────────────────────

def is_h3_valid(h3_index: str) -> bool:
    """
    Return ``True`` if *h3_index* is a valid H3 cell index string.

    Provides a version-agnostic wrapper around the h3-py validation
    function, catching any unexpected exceptions and returning ``False``
    rather than propagating them.

    Parameters
    ----------
    h3_index : str
        The H3 index string to check (hexadecimal format, e.g.
        ``"89195da49b7ffff"``).

    Returns
    -------
    bool
        ``True`` if *h3_index* is recognised as a valid H3 cell by the
        installed h3-py version; ``False`` otherwise.

    Notes
    -----
    Internally delegates to ``h3.is_valid_cell`` (v4) or
    ``h3.h3_is_valid`` (v3).

    Examples
    --------
    >>> is_h3_valid("89195da49b7ffff")
    True
    >>> is_h3_valid("not_an_index")
    False
    >>> is_h3_valid(12345)
    False
    """
    try:
        return h3.is_valid_cell(h3_index) if IS_H3_V4 else h3.h3_is_valid(h3_index)
    except Exception:
        return False


def is_h3_pentagon(h3_index: str) -> bool:
    """
    Return ``True`` if *h3_index* is one of the 12 pentagon cells at its resolution.

    The H3 grid contains exactly 12 pentagon cells per resolution level,
    located at icosahedron vertices.  Pentagon cells have 5 edges and
    5 neighbours instead of the usual 6, which can affect the behaviour
    of path-finding, ring, and distance operations.

    Parameters
    ----------
    h3_index : str
        A valid H3 cell index string.

    Returns
    -------
    bool
        ``True`` if the cell is a pentagon; ``False`` otherwise.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index.

    Notes
    -----
    Internally delegates to ``h3.is_pentagon`` (v4) or
    ``h3.h3_is_pentagon`` (v3).

    See Also
    --------
    is_h3_valid : Check whether a string is a valid H3 index at all.
    get_h3_neighbors : Returns 5 neighbours for pentagon cells instead of 6.

    Examples
    --------
    >>> is_h3_pentagon("89195da49b7ffff")   # regular hexagon
    False

    >>> # Every resolution has exactly 12 pentagons:
    >>> import h3
    >>> pentagons = h3.get_pentagons(5)   # h3-py v4
    >>> all(is_h3_pentagon(p) for p in pentagons)
    True
    """
    _validate_h3_index(h3_index)
    return h3.is_pentagon(h3_index) if IS_H3_V4 else h3.h3_is_pentagon(h3_index)


def get_h3_resolution(h3_index: str) -> int:
    """
    Return the resolution (0–15) of an H3 cell.

    Parameters
    ----------
    h3_index : str
        A valid H3 cell index string.

    Returns
    -------
    int
        Resolution level of the cell, in the range [0, 15].
        Resolution 0 is the coarsest; resolution 15 is the finest.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index (delegated to
        :func:`h3tools._validators._validate_h3_index`).

    Notes
    -----
    Internally delegates to ``h3.get_resolution`` (v4) or
    ``h3.h3_get_resolution`` (v3).

    Examples
    --------
    >>> get_h3_resolution("89195da49b7ffff")
    9
    >>> get_h3_resolution("85194ad3fffffff")
    5
    """
    _validate_h3_index(h3_index)
    return h3.get_resolution(h3_index) if IS_H3_V4 else h3.h3_get_resolution(h3_index)


def get_h3_cell_area(h3_index: str) -> float:
    """
    Return the average area in km² for the resolution of *h3_index*.

    All cells at a given resolution share the same *average* area value;
    individual cell areas vary slightly due to the spherical projection of
    the H3 grid.  This function returns the resolution-level average, not
    the exact area of the specific cell.

    Parameters
    ----------
    h3_index : str
        A valid H3 cell index.  Only its resolution is used for the
        calculation; the specific cell identity does not affect the result.

    Returns
    -------
    float
        Average hexagonal cell area in square kilometres (km²) for the
        cell's resolution level.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index.

    Notes
    -----
    Internally delegates to ``h3.average_hexagon_area(res, unit="km^2")``
    (v4) or ``h3.hex_area(res, unit="km^2")`` (v3).

    Examples
    --------
    >>> area = get_h3_cell_area("85194ad3fffffff")   # resolution 5
    >>> round(area, 2)
    252.9

    >>> area = get_h3_cell_area("89195da49b7ffff")   # resolution 9
    >>> round(area, 4)
    0.1053
    """
    _validate_h3_index(h3_index)
    res = get_h3_resolution(h3_index)
    if IS_H3_V4:
        return h3.average_hexagon_area(res, unit="km^2")
    return h3.hex_area(res, unit="km^2")


def get_h3_cell_edge_length(h3_index: str) -> float:
    """
    Return the average edge length in km for the resolution of *h3_index*.

    As with :func:`get_h3_cell_area`, the returned value is the resolution-
    level average.  Individual cell edge lengths differ slightly across the
    globe.

    Parameters
    ----------
    h3_index : str
        A valid H3 cell index.  Only its resolution is used for the
        calculation.

    Returns
    -------
    float
        Average hexagonal cell edge length in kilometres (km) for the
        cell's resolution level.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index.

    Notes
    -----
    Internally delegates to
    ``h3.average_hexagon_edge_length(res, unit="km")`` (v4) or
    ``h3.edge_length(res, unit="km")`` (v3).

    Examples
    --------
    >>> length = get_h3_cell_edge_length("85194ad3fffffff")   # resolution 5
    >>> round(length, 2)
    9.83

    >>> length = get_h3_cell_edge_length("89195da49b7ffff")   # resolution 9
    >>> round(length, 4)
    0.1745
    """
    _validate_h3_index(h3_index)
    res = get_h3_resolution(h3_index)
    if IS_H3_V4:
        return h3.average_hexagon_edge_length(res, unit="km")
    return h3.edge_length(res, unit="km")
