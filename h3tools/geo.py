"""
h3tools.geo
============
Geometry and coordinate ↔ H3 cell conversion functions.

Covers:

* Shapely ``Point`` / ``Polygon`` / ``MultiPolygon`` / ``LineString`` → H3
* ``(lat, lon)`` tuple → H3
* DMS and DDM string → H3
* MGRS string → H3
* H3 → Shapely ``Point`` / ``Polygon``
* H3 → DMS / DDM coordinate strings
* H3 → MGRS string
* H3 cell set → dissolved Shapely ``Polygon`` / ``MultiPolygon``
* H3 cells ↔ GeoJSON
* Unified dispatcher :func:`geometry_to_h3` that auto-detects input format

All functions handle h3-py v3/v4 API differences via
:data:`h3tools.core.IS_H3_V4`.

Functions
---------
latlon_to_point
    Convert a ``(lat, lon)`` tuple to a Shapely ``Point``.
point_to_h3
    Convert a Shapely ``Point`` to an H3 cell index.
latlon_to_h3
    Convert a ``(lat, lon)`` tuple directly to an H3 cell index.
mgrs_to_point
    Convert an MGRS string to a Shapely ``Point``.
mgrs_to_h3
    Convert an MGRS string to an H3 cell index.
dms_to_point
    Parse a DMS lat/lon pair string to a Shapely ``Point``.
dms_to_h3
    Convert a DMS pair string to an H3 cell index.
ddm_to_point
    Parse a DDM lat/lon pair string to a Shapely ``Point``.
coordinate_to_point
    Unified dispatcher: any supported coordinate format → Shapely ``Point``.
coordinate_to_h3
    Unified dispatcher: any supported coordinate format → H3 cell index.
linestring_to_h3
    Convert a Shapely ``LineString`` / ``MultiLineString`` to H3 cells.
polygon_to_h3
    Convert a Shapely ``Polygon`` to a set of H3 cell indices.
multipolygon_to_h3
    Convert a Shapely ``MultiPolygon`` to a set of H3 cell indices.
geometry_to_h3
    Universal dispatcher: many input formats → set of H3 cell indices.
h3_to_point
    Return the centre of an H3 cell as a Shapely ``Point``.
h3_to_polygon
    Return the boundary of an H3 cell as a Shapely ``Polygon``.
h3_to_dms
    Return the centre of an H3 cell as a (lat, lon) DMS string pair.
h3_to_ddm
    Return the centre of an H3 cell as a (lat, lon) DDM string pair.
h3_to_mgrs
    Return the MGRS coordinate for the centre of an H3 cell.
dissolve_h3_cells
    Merge a collection of H3 cells into a single dissolved Shapely geometry.
cells_to_geojson
    Serialise H3 cells to a GeoJSON FeatureCollection dict.
geojson_to_cells
    Convert a GeoJSON geometry, Feature, or FeatureCollection to H3 cells.
"""

from __future__ import annotations

__all__ = [
    "latlon_to_point",
    "point_to_h3",
    "latlon_to_h3",
    "mgrs_to_point",
    "mgrs_to_h3",
    "dms_to_point",
    "dms_to_h3",
    "ddm_to_point",
    "ddm_to_h3",
    "coordinate_to_point",
    "coordinate_to_h3",
    "linestring_to_h3",
    "polygon_to_h3",
    "multipolygon_to_h3",
    "geometry_to_h3",
    "h3_to_point",
    "h3_to_polygon",
    "h3_to_dms",
    "h3_to_ddm",
    "h3_to_mgrs",
    "dissolve_h3_cells",
    "cells_to_geojson",
    "geojson_to_cells",
    "points_to_h3_path",
    "geometry_to_box",
]

import json
import re

import h3
import mgrs as mgrs_lib
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

import shapely.geometry

from h3tools.core import IS_H3_V4, is_h3_valid, get_h3_resolution
from h3tools._validators import (
    _validate_h3_index,
    _validate_h3_resolution,
    _validate_latitude,
    _validate_longitude,
    _validate_mgrs,
    _validate_mgrs_precision,
    _validate_point,
    _validate_polygon,
    _validate_dms,
    _validate_ddm_pair,
    _VALID_CONTAIN_MODES,
)

# ── Internal helpers ──────────────────────────────────────────────────────────

def _scrub_dms(text: str) -> str:
    """
    Strip DMS symbols and normalise whitespace for regex parsing.

    Replaces the full set of degree/minute/second Unicode symbols with a
    single space, then collapses runs of whitespace into one space and
    strips leading/trailing whitespace.

    Parameters
    ----------
    text : str
        Raw DMS string that may contain ``°``, ``˚``, ``º``, ``′``,
        ``'``, ``'``, ``″``, ``"``, ``˝``, ``¨``, or ``:`` characters.

    Returns
    -------
    str
        Cleaned string with symbols replaced by spaces and whitespace
        normalised.

    Examples
    --------
    >>> _scrub_dms("39°48'18\\" N")
    '39 48 18 N'
    """
    symbols = r"°˚º′''″\"˝¨:"
    text = re.sub(rf"[{symbols}]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ── Point conversions ─────────────────────────────────────────────────────────

def latlon_to_point(latlon: tuple) -> Point:
    """
    Convert a ``(lat, lon)`` tuple to a Shapely ``Point(lon, lat)``.

    Shapely uses ``(x, y)`` ordering, which corresponds to
    ``(longitude, latitude)``.  This function handles the axis swap and
    validates coordinate bounds.

    Parameters
    ----------
    latlon : tuple of float
        ``(latitude, longitude)`` in decimal degrees.
        Latitude must be in [-90, 90]; longitude in [-180, 180].

    Returns
    -------
    shapely.geometry.Point
        Point with ``x = longitude`` and ``y = latitude``.

    Raises
    ------
    ValueError
        If latitude is outside [-90, 90] or longitude is outside [-180, 180].

    See Also
    --------
    latlon_to_h3 : Convert directly from a tuple to an H3 cell index.

    Examples
    --------
    >>> pt = latlon_to_point((51.5074, -0.1278))
    >>> pt.x, pt.y
    (-0.1278, 51.5074)
    """
    latitude, longitude = latlon
    _validate_latitude(float(latitude))
    _validate_longitude(float(longitude))
    return Point(longitude, latitude)


def point_to_h3(point: Point, h3_resolution: int) -> str:
    """
    Convert a Shapely ``Point`` to an H3 cell index string.

    Parameters
    ----------
    point : shapely.geometry.Point
        WGS-84 point with ``x = longitude`` and ``y = latitude``.
    h3_resolution : int
        Target H3 resolution level, in [0, 15].

    Returns
    -------
    str
        H3 cell index string (hexadecimal), e.g. ``"89195da49b7ffff"``.

    Raises
    ------
    TypeError
        If *point* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *point* coordinates are out of WGS-84 bounds, or if
        *h3_resolution* is outside [0, 15].

    Notes
    -----
    Internally delegates to ``h3.latlng_to_cell`` (v4) or
    ``h3.geo_to_h3`` (v3).

    See Also
    --------
    latlon_to_h3 : Convenience wrapper that accepts a ``(lat, lon)`` tuple.
    geometry_to_h3 : Universal dispatcher that accepts many input types.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> cell = point_to_h3(Point(-0.1278, 51.5074), h3_resolution=9)
    >>> len(cell) > 0
    True
    """
    _validate_point(point)
    _validate_h3_resolution(h3_resolution)
    if IS_H3_V4:
        return h3.latlng_to_cell(point.y, point.x, h3_resolution)
    return h3.geo_to_h3(point.y, point.x, h3_resolution)


def latlon_to_h3(latlon: tuple, h3_resolution: int) -> str:
    """
    Convert a ``(lat, lon)`` tuple directly to an H3 cell index.

    Convenience wrapper that combines :func:`latlon_to_point` and
    :func:`point_to_h3`.

    Parameters
    ----------
    latlon : tuple of float
        ``(latitude, longitude)`` in decimal degrees.
        Latitude must be in [-90, 90]; longitude in [-180, 180].
    h3_resolution : int
        Target H3 resolution level, in [0, 15].

    Returns
    -------
    str
        H3 cell index string.

    Raises
    ------
    ValueError
        If coordinates are out of bounds or *h3_resolution* is invalid.

    See Also
    --------
    point_to_h3 : Convert from a Shapely ``Point`` instead.

    Examples
    --------
    >>> cell = latlon_to_h3((51.5074, -0.1278), h3_resolution=9)
    >>> isinstance(cell, str)
    True
    """
    return point_to_h3(latlon_to_point(latlon), h3_resolution)


# ── MGRS conversions ──────────────────────────────────────────────────────────

def mgrs_to_point(mgrs_str: str, return_latlon: bool = False):
    """
    Convert an MGRS coordinate string to a Shapely ``Point``.

    Parameters
    ----------
    mgrs_str : str
        MGRS coordinate string, e.g. ``"18TWL8396007450"`` or
        ``"30UXC0529398803"``.
    return_latlon : bool, optional
        If ``True``, return a raw ``(lat, lon)`` tuple instead of a
        Shapely ``Point``.  Default is ``False``.

    Returns
    -------
    shapely.geometry.Point or tuple of float
        * ``Point(longitude, latitude)`` when *return_latlon* is ``False``.
        * ``(latitude, longitude)`` tuple when *return_latlon* is ``True``.

    Raises
    ------
    TypeError
        If *mgrs_str* is not a non-empty ``str``.
    ValueError
        If *mgrs_str* does not conform to the MGRS structural pattern.

    Notes
    -----
    Conversion is performed by the ``mgrs`` library's ``MGRS.toLatLon``
    method.

    See Also
    --------
    mgrs_to_h3 : Convert an MGRS string directly to an H3 cell index.

    Examples
    --------
    >>> pt = mgrs_to_point("30UXC0529398803")
    >>> round(pt.y, 4), round(pt.x, 4)   # (lat, lon)
    (51.5074, -0.1277)

    >>> lat, lon = mgrs_to_point("30UXC0529398803", return_latlon=True)
    """
    _validate_mgrs(mgrs_str)
    m = mgrs_lib.MGRS()
    lat_dd, lon_dd = m.toLatLon(mgrs_str)
    return (lat_dd, lon_dd) if return_latlon else Point(lon_dd, lat_dd)


def mgrs_to_h3(mgrs_str: str, h3_resolution: int) -> str:
    """
    Convert an MGRS coordinate string to an H3 cell index.

    Parameters
    ----------
    mgrs_str : str
        MGRS coordinate string, e.g. ``"30UXC0529398803"``.
    h3_resolution : int
        Target H3 resolution level, in [0, 15].

    Returns
    -------
    str
        H3 cell index string.

    Raises
    ------
    TypeError
        If *mgrs_str* is not a non-empty ``str``.
    ValueError
        If *mgrs_str* fails structural MGRS validation, or if
        *h3_resolution* is outside [0, 15].

    See Also
    --------
    mgrs_to_point : Convert to a Shapely ``Point`` instead.
    h3_to_mgrs : Reverse conversion — H3 cell → MGRS string.

    Examples
    --------
    >>> cell = mgrs_to_h3("30UXC0529398803", h3_resolution=9)
    >>> isinstance(cell, str)
    True
    """
    _validate_mgrs(mgrs_str)
    return point_to_h3(mgrs_to_point(mgrs_str), h3_resolution)


# ── DMS / DDM conversions ─────────────────────────────────────────────────────

def dms_to_point(
    dms_str: str,
    return_latlon: bool = False,
    debug: bool = False,
) -> Point:
    """
    Parse a DMS lat/lon pair string to a Shapely ``Point``.

    Accepts a wide variety of degree/minute/second separators and Unicode
    symbols (``°``, ``˚``, ``′``, ``'``, ``″``, ``"``, spaces, colons, …).
    Both ``N``/``S`` and ``E``/``W`` hemisphere suffixes are required.

    Parameters
    ----------
    dms_str : str
        DMS coordinate pair string.  Examples of accepted formats:

        * ``"39°48'18\\" N 089°38'42\\" W"``
        * ``"51:30:26N 000:07:40W"``
        * ``"51 30 26 N 0 07 40 W"``
    return_latlon : bool, optional
        If ``True``, return ``(lat_dd, lon_dd)`` tuple instead of a
        Shapely ``Point``.  Default is ``False``.
    debug : bool, optional
        If ``True``, print the scrubbed input and parsed regex groups to
        stdout for troubleshooting.  Default is ``False``.

    Returns
    -------
    shapely.geometry.Point or tuple of float
        * ``Point(longitude, latitude)`` when *return_latlon* is ``False``.
        * ``(latitude, longitude)`` decimal-degree tuple when
          *return_latlon* is ``True``.

    Raises
    ------
    TypeError
        If *dms_str* is not a ``str``.
    ValueError
        If the string is empty, lacks proper N/S and E/W indicators,
        cannot be parsed by the regex, or produces out-of-bounds coordinates.

    See Also
    --------
    dms_to_h3 : Convert a DMS string directly to an H3 cell index.
    ddm_to_point : Parse Degrees Decimal Minutes format instead.

    Examples
    --------
    >>> pt = dms_to_point("51°30'26\\" N 0°7'40\\" W")
    >>> round(pt.y, 4), round(pt.x, 4)   # (lat, lon)
    (51.5072, -0.1278)

    >>> lat, lon = dms_to_point("39°48'18\\" N 089°38'42\\" W", return_latlon=True)
    >>> round(lat, 4), round(lon, 4)
    (39.805, -89.645)
    """
    _validate_dms(dms_str)
    scrubbed = _scrub_dms(dms_str)

    if debug:
        print(f"[dms_to_point] scrubbed → {scrubbed!r}")

    pattern = re.compile(
        r"""
        (?P<lat_deg>[0-8]?\d)
        \s*[^\d]*\s*
        (?P<lat_min>[0-5]?\d)?
        \s*[^\d]*\s*
        (?P<lat_sec>[0-5]?\d(?:\.\d+)?)?
        \s*[^\d]*\s*
        (?P<lat_dir>[NSns])
        .*?
        (?P<lon_deg>[01]?\d{1,2})
        \s*[^\d]*\s*
        (?P<lon_min>[0-5]?\d)?
        \s*[^\d]*\s*
        (?P<lon_sec>[0-5]?\d(?:\.\d+)?)?
        \s*[^\d]*\s*
        (?P<lon_dir>[EWew])
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    match = pattern.search(scrubbed)
    if not match:
        raise ValueError(
            f"Could not parse DMS pair. Input: {dms_str!r} "
            f"(scrubbed: {scrubbed!r})"
        )

    g = match.groupdict()
    if debug:
        print(f"[dms_to_point] groups → {g}")

    lat_deg = float(g["lat_deg"])
    lat_min = float(g["lat_min"]) if g["lat_min"] else 0.0
    lat_sec = float(g["lat_sec"]) if g["lat_sec"] else 0.0
    lat_sign = 1.0 if g["lat_dir"].upper() == "N" else -1.0
    lat_dd = lat_sign * (lat_deg + lat_min / 60.0 + lat_sec / 3600.0)

    lon_deg = float(g["lon_deg"])
    lon_min = float(g["lon_min"]) if g["lon_min"] else 0.0
    lon_sec = float(g["lon_sec"]) if g["lon_sec"] else 0.0
    lon_sign = 1.0 if g["lon_dir"].upper() == "E" else -1.0
    lon_dd = lon_sign * (lon_deg + lon_min / 60.0 + lon_sec / 3600.0)

    if not (-90 <= lat_dd <= 90):
        raise ValueError(f"Latitude out of range: {lat_dd}")
    if not (-180 <= lon_dd <= 180):
        raise ValueError(f"Longitude out of range: {lon_dd}")

    return (lat_dd, lon_dd) if return_latlon else Point(lon_dd, lat_dd)


def dms_to_h3(dms_str: str, h3_resolution: int) -> str:
    """
    Convert a DMS lat/lon pair string to an H3 cell index.

    Convenience wrapper that chains :func:`dms_to_point` and
    :func:`point_to_h3`.

    Parameters
    ----------
    dms_str : str
        DMS coordinate pair string (see :func:`dms_to_point` for accepted
        formats).
    h3_resolution : int
        Target H3 resolution level, in [0, 15].

    Returns
    -------
    str
        H3 cell index string.

    Raises
    ------
    TypeError
        If *dms_str* is not a ``str``.
    ValueError
        If the DMS string cannot be parsed, produces out-of-bounds
        coordinates, or *h3_resolution* is outside [0, 15].

    See Also
    --------
    dms_to_point : Parse DMS to a Shapely ``Point`` instead.
    ddm_to_point : Parse Degrees Decimal Minutes format.

    Examples
    --------
    >>> cell = dms_to_h3("51°30'26\\" N 0°7'40\\" W", h3_resolution=9)
    >>> isinstance(cell, str)
    True
    """
    _validate_dms(dms_str)
    return point_to_h3(dms_to_point(dms_str), h3_resolution)


def ddm_to_point(ddm_str: str, return_latlon: bool = False) -> Point:
    """
    Parse a Degrees Decimal Minutes (DDM) lat/lon pair string to a Shapely ``Point``.

    DDM format expresses coordinates as integer degrees plus decimal minutes,
    e.g. ``"51 30.4 N 0 7.7 W"``, without a separate seconds component.

    Parameters
    ----------
    ddm_str : str
        DDM coordinate pair string.  Expected structure:
        ``<deg> <decimal_min> <N|S>  <deg> <decimal_min> <E|W>``.
        Various separators and symbols are tolerated.
    return_latlon : bool, optional
        If ``True``, return ``(lat_dd, lon_dd)`` tuple instead of a
        Shapely ``Point``.  Default is ``False``.

    Returns
    -------
    shapely.geometry.Point or tuple of float
        * ``Point(longitude, latitude)`` when *return_latlon* is ``False``.
        * ``(latitude, longitude)`` decimal-degree tuple when
          *return_latlon* is ``True``.

    Raises
    ------
    ValueError
        If *ddm_str* is empty, lacks proper N/S and E/W indicators,
        cannot be parsed, or produces out-of-bounds coordinates.

    See Also
    --------
    dms_to_point : Parse Degrees Minutes Seconds format.
    coordinate_to_point : Unified dispatcher that auto-detects format.

    Examples
    --------
    >>> pt = ddm_to_point("51 30.4 N 0 7.7 W")
    >>> round(pt.y, 4), round(pt.x, 4)   # (lat, lon)
    (51.5067, -0.1283)

    >>> lat, lon = ddm_to_point("39 48.3 N 089 38.7 W", return_latlon=True)
    >>> round(lat, 4), round(lon, 4)
    (39.805, -89.645)
    """
    _validate_ddm_pair(ddm_str)

    pattern = re.compile(
        r"""
        (?P<lat_deg>\d{1,3})\s*[^\d]*\s*
        (?P<lat_min>\d{1,2}(?:\.\d+)?)\s*[^\d]*\s*
        (?P<lat_dir>[NSns])
        .*?
        (?P<lon_deg>\d{1,3})\s*[^\d]*\s*
        (?P<lon_min>\d{1,2}(?:\.\d+)?)\s*[^\d]*\s*
        (?P<lon_dir>[EWew])
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    match = pattern.search(ddm_str)
    if not match:
        raise ValueError(f"Could not parse DDM pair: {ddm_str!r}")

    g = match.groupdict()
    lat_dd = (1.0 if g["lat_dir"].upper() == "N" else -1.0) * (
        float(g["lat_deg"]) + float(g["lat_min"]) / 60.0
    )
    lon_dd = (1.0 if g["lon_dir"].upper() == "E" else -1.0) * (
        float(g["lon_deg"]) + float(g["lon_min"]) / 60.0
    )

    if not (-90.0 <= lat_dd <= 90.0):
        raise ValueError(f"Latitude out of range: {lat_dd}")
    if not (-180.0 <= lon_dd <= 180.0):
        raise ValueError(f"Longitude out of range: {lon_dd}")

    return (lat_dd, lon_dd) if return_latlon else Point(lon_dd, lat_dd)


def ddm_to_h3(ddm_str: str, h3_resolution: int) -> str:
    """
    Convert a DDM lat/lon pair string to an H3 cell index.

    Convenience wrapper that chains :func:`ddm_to_point` and
    :func:`point_to_h3`.

    Parameters
    ----------
    ddm_str : str
        DDM coordinate pair string (see :func:`ddm_to_point` for accepted
        formats).
    h3_resolution : int
        Target H3 resolution level, in [0, 15].

    Returns
    -------
    str
        H3 cell index string.

    Raises
    ------
    ValueError
        If the DDM string cannot be parsed, produces out-of-bounds
        coordinates, or *h3_resolution* is outside [0, 15].

    See Also
    --------
    ddm_to_point : Parse DDM to a Shapely ``Point`` instead.
    dms_to_h3 : Convert Degrees Minutes Seconds format directly to H3.

    Examples
    --------
    >>> cell = ddm_to_h3("51 30.4 N 0 7.7 W", h3_resolution=9)
    >>> isinstance(cell, str)
    True
    """
    return point_to_h3(ddm_to_point(ddm_str), h3_resolution)


# ── Unified coordinate dispatcher ─────────────────────────────────────────────

def coordinate_to_point(coord_input: object) -> Point:
    """
    Convert any supported coordinate format to a Shapely ``Point``.

    The input format is auto-detected in the following order:

    1. ``(lat, lon)`` numeric tuple or list → decimal degrees.
    2. MGRS string (starts with 1–2 digits then a C–X band letter).
    3. DMS string (contains ``°``, ``'``, ``"`` symbols, or two
       ``N``/``S``/``E``/``W`` direction letters with digits).
    4. DDM string (decimal-minutes pattern).

    Parameters
    ----------
    coord_input : tuple, list, or str
        Supported formats:

        * ``(latitude, longitude)`` numeric tuple or list.
        * DMS string — ``"39°48'18\\" N 089°38'42\\" W"``
        * DDM string — ``"39 48.3 N 089 38.7 W"``
        * MGRS string — ``"18TWL8396007450"``

    Returns
    -------
    shapely.geometry.Point
        Point with ``x = longitude``, ``y = latitude`` in WGS-84.

    Raises
    ------
    TypeError
        If *coord_input* is not a ``str``, ``tuple``, or ``list``.
    ValueError
        If the string does not match any recognised coordinate format.

    See Also
    --------
    coordinate_to_h3 : Convert directly to an H3 cell index.
    geometry_to_h3 : Universal dispatcher that also accepts Shapely geometries.

    Examples
    --------
    >>> pt = coordinate_to_point((51.5074, -0.1278))
    >>> round(pt.x, 4)
    -0.1278

    >>> pt = coordinate_to_point("51°30'26\\" N 0°7'40\\" W")
    >>> round(pt.y, 2)
    51.51

    >>> pt = coordinate_to_point("30UXC0529398803")
    >>> isinstance(pt, Point)
    True
    """
    if isinstance(coord_input, (tuple, list)) and len(coord_input) == 2:
        return latlon_to_point(coord_input)

    if isinstance(coord_input, str):
        cleaned = coord_input.strip()
        # MGRS: starts with 1–2 digits then a C-X band letter
        if re.match(r"^\d{1,2}[C-X]", cleaned.upper()):
            return mgrs_to_point(cleaned)
        # DMS: explicit degree/minute/second symbols OR 2× N/S/E/W + digits
        if re.search(r"[°\'\"]", cleaned) or (
            len(re.findall(r"[NSEWnsew]", cleaned)) == 2
            and re.search(r"\d", cleaned)
        ):
            return dms_to_point(cleaned)
        # DDM: decimal minutes pattern
        if re.search(r"\d+\.?\d*\s*[′\']?\s*[NSEWnsew]", cleaned):
            return ddm_to_point(cleaned)
        raise ValueError(f"Unrecognised coordinate string: {coord_input!r}")

    raise TypeError(
        f"coordinate_to_point() received unsupported type: "
        f"{type(coord_input).__name__}. Expected str or (lat, lon) tuple."
    )


def coordinate_to_h3(coord_input: object, h3_resolution: int = 10) -> str:
    """
    Convert any supported coordinate format to an H3 cell index.

    Convenience wrapper that chains :func:`coordinate_to_point` and
    :func:`point_to_h3`.

    Parameters
    ----------
    coord_input : tuple, list, or str
        Any format accepted by :func:`coordinate_to_point`:

        * ``(latitude, longitude)`` numeric tuple or list.
        * DMS string — ``"39°48'18\\" N 089°38'42\\" W"``
        * DDM string — ``"39 48.3 N 089 38.7 W"``
        * MGRS string — ``"18TWL8396007450"``
    h3_resolution : int, optional
        Target H3 resolution level, in [0, 15].  Default is ``10``.

    Returns
    -------
    str
        H3 cell index string.

    Raises
    ------
    TypeError
        If *coord_input* is an unsupported type.
    ValueError
        If the coordinate cannot be parsed or *h3_resolution* is invalid.

    See Also
    --------
    coordinate_to_point : Convert to a Shapely ``Point`` instead.
    geometry_to_h3 : Universal dispatcher that also accepts Shapely geometries.

    Examples
    --------
    >>> cell = coordinate_to_h3((51.5074, -0.1278), h3_resolution=9)
    >>> isinstance(cell, str)
    True

    >>> cell = coordinate_to_h3("30UXC0529398803", h3_resolution=9)
    >>> isinstance(cell, str)
    True
    """
    return point_to_h3(coordinate_to_point(coord_input), h3_resolution)


# ── LineString → H3 ──────────────────────────────────────────────────────────

def linestring_to_h3(
    geom: LineString | MultiLineString,
    resolution: int,
) -> set[str]:
    """
    Convert a Shapely ``LineString`` or ``MultiLineString`` to a set of H3 cells.

    Produces a contiguous 'tube' of hexagons by tracing H3 grid paths
    between consecutive vertices of the geometry.  Each segment
    ``[vertex_i, vertex_{i+1}]`` is filled using the H3 grid-path
    algorithm; cells from all segments are unioned into a single set.

    Parameters
    ----------
    geom : shapely.geometry.LineString or shapely.geometry.MultiLineString
        Input geometry.  For ``MultiLineString``, each component line is
        processed independently and the results are unioned.
    resolution : int
        H3 resolution level, in [0, 15].

    Returns
    -------
    set of str
        Unique H3 cell index strings intersecting the geometry.

    Raises
    ------
    TypeError
        If *geom* is not a ``LineString`` or ``MultiLineString``.
    ValueError
        If *resolution* is outside [0, 15].

    Notes
    -----
    If the H3 grid-path computation fails for a segment (e.g. due to a
    pentagon crossing or excessive distance), the segment's start and end
    cells are added individually rather than aborting.

    Internally delegates to ``h3.grid_path_cells`` (v4) or
    ``h3.h3_line`` (v3).

    Examples
    --------
    >>> from shapely.geometry import LineString
    >>> line = LineString([(-0.14, 51.49), (-0.11, 51.52)])
    >>> cells = linestring_to_h3(line, resolution=9)
    >>> len(cells) >= 2
    True
    """
    if not isinstance(geom, (LineString, MultiLineString)):
        raise TypeError(
            f"Expected LineString or MultiLineString, got {type(geom).__name__}."
        )
    _validate_h3_resolution(resolution)

    lines = geom.geoms if isinstance(geom, MultiLineString) else [geom]
    h3_cells: set[str] = set()

    for line in lines:
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        for i in range(len(coords) - 1):
            start_lon, start_lat = coords[i]
            end_lon, end_lat = coords[i + 1]
            if IS_H3_V4:
                start_cell = h3.latlng_to_cell(start_lat, start_lon, resolution)
                end_cell = h3.latlng_to_cell(end_lat, end_lon, resolution)
                try:
                    h3_cells.update(h3.grid_path_cells(start_cell, end_cell))
                except Exception:
                    h3_cells.update({start_cell, end_cell})
            else:
                start_cell = h3.geo_to_h3(start_lat, start_lon, resolution)
                end_cell = h3.geo_to_h3(end_lat, end_lon, resolution)
                try:
                    h3_cells.update(h3.h3_line(start_cell, end_cell))
                except Exception:
                    h3_cells.update({start_cell, end_cell})

    return h3_cells


# ── Polygon → H3 ─────────────────────────────────────────────────────────────

def polygon_to_h3(
    shapely_poly: Polygon,
    h3_resolution: int,
    contain_mode: str = "center",
) -> set[str]:
    """
    Convert a Shapely ``Polygon`` to a set of H3 cell indices.

    Polygons with holes (interior rings) are supported; each interior ring
    is passed to H3 as a hole in the polygon object.

    Parameters
    ----------
    shapely_poly : shapely.geometry.Polygon
        Input polygon in WGS-84.  May contain holes (interior rings).
        Topologically invalid polygons are repaired with ``buffer(0)``
        before conversion.
    h3_resolution : int
        H3 resolution level, in [0, 15].
    contain_mode : {'center', 'full', 'overlap', 'bbox_overlap'}, optional
        Determines which cells are included in the result:

        * ``'center'``       – cells whose centre point lies inside the
                               polygon *(default)*.
        * ``'full'``         – cells completely contained by the polygon.
        * ``'overlap'``      – cells that intersect the polygon at all.
        * ``'bbox_overlap'`` – cells whose bounding box intersects the
                               polygon's bounding box.

    Returns
    -------
    set of str
        Unique H3 cell index strings covering the polygon.

    Raises
    ------
    TypeError
        If *shapely_poly* is not a :class:`shapely.geometry.Polygon`.
    ValueError
        If *h3_resolution* is outside [0, 15], *contain_mode* is not
        one of the accepted values, or the H3 conversion fails.

    See Also
    --------
    multipolygon_to_h3 : Convert a ``MultiPolygon`` instead.
    geometry_to_h3 : Universal dispatcher.

    Examples
    --------
    >>> from shapely.geometry import Polygon
    >>> area = Polygon([(-0.14, 51.49), (-0.11, 51.49),
    ...                 (-0.11, 51.52), (-0.14, 51.52),
    ...                 (-0.14, 51.49)])
    >>> cells = polygon_to_h3(area, h3_resolution=10)
    >>> len(cells) > 0
    True
    """
    _validate_polygon(shapely_poly)
    _validate_h3_resolution(h3_resolution)

    if contain_mode not in _VALID_CONTAIN_MODES:
        raise ValueError(
            f"contain_mode must be one of {_VALID_CONTAIN_MODES}, "
            f"got {contain_mode!r}."
        )

    if not shapely_poly.is_valid:
        shapely_poly = shapely_poly.buffer(0)

    try:
        exterior_coords = [
            [lat, lon] for lon, lat in shapely_poly.exterior.coords[:-1]
        ]

        if IS_H3_V4:
            if shapely_poly.interiors:
                hole_polys = [
                    h3.LatLngPoly([[lat, lon] for lon, lat in interior.coords[:-1]])
                    for interior in shapely_poly.interiors
                ]
                poly_obj = h3.LatLngMultiPoly(
                    [h3.LatLngPoly(exterior_coords)], holes=hole_polys
                )
            else:
                poly_obj = h3.LatLngPoly(exterior_coords)

            if contain_mode == "center":
                cells = h3.polygon_to_cells(poly_obj, res=h3_resolution)
            else:
                cells = h3.polygon_to_cells_experimental(
                    poly_obj, res=h3_resolution, contain=contain_mode
                )
        else:
            # h3-py v3: only center-based containment via h3.polyfill
            if contain_mode != "center":
                import warnings
                warnings.warn(
                    f"contain_mode={contain_mode!r} is not supported by h3-py v3; "
                    "falling back to 'center'.",
                    stacklevel=3,
                )
            holes = [
                [[lon, lat] for lon, lat in interior.coords[:-1]]
                for interior in shapely_poly.interiors
            ]
            geojson = {
                "type": "Polygon",
                "coordinates": [exterior_coords] + holes,
            }
            cells = h3.polyfill(geojson, h3_resolution, geo_json_conformant=True)

        return set(cells)

    except Exception as exc:
        raise ValueError(
            f"Failed to convert polygon to H3 cells: {exc}"
        ) from exc


def multipolygon_to_h3(
    shapely_multipoly: shapely.geometry.MultiPolygon,
    h3_resolution: int,
    contain_mode: str = "center",
) -> set[str]:
    """
    Convert a Shapely ``MultiPolygon`` to a set of H3 cell indices.

    Iterates over each component ``Polygon`` and unions all results.
    Component polygons that raise an error are skipped with a warning
    rather than aborting the entire conversion.

    Parameters
    ----------
    shapely_multipoly : shapely.geometry.MultiPolygon
        Input multi-polygon in WGS-84.
    h3_resolution : int
        H3 resolution level, in [0, 15].
    contain_mode : {'center', 'full', 'overlap', 'bbox_overlap'}, optional
        Cell inclusion criterion.  See :func:`polygon_to_h3` for details.
        Default is ``'center'``.

    Returns
    -------
    set of str
        Unique H3 cell index strings covering all component polygons.

    Raises
    ------
    TypeError
        If *shapely_multipoly* is not a
        :class:`shapely.geometry.MultiPolygon`.
    ValueError
        If *h3_resolution* is outside [0, 15] or *contain_mode* is
        not one of the accepted values.

    See Also
    --------
    polygon_to_h3 : Convert a single ``Polygon`` instead.
    geometry_to_h3 : Universal dispatcher.

    Examples
    --------
    >>> from shapely.geometry import MultiPolygon, Polygon
    >>> p1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    >>> p2 = Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])
    >>> cells = multipolygon_to_h3(MultiPolygon([p1, p2]), h3_resolution=5)
    >>> isinstance(cells, set)
    True
    """
    if not isinstance(shapely_multipoly, shapely.geometry.MultiPolygon):
        raise TypeError(
            f"Expected MultiPolygon, got {type(shapely_multipoly).__name__}."
        )
    _validate_h3_resolution(h3_resolution)

    if contain_mode not in _VALID_CONTAIN_MODES:
        raise ValueError(
            f"contain_mode must be one of {_VALID_CONTAIN_MODES}, "
            f"got {contain_mode!r}."
        )

    all_cells: set[str] = set()
    for poly in shapely_multipoly.geoms:
        try:
            all_cells.update(polygon_to_h3(poly, h3_resolution, contain_mode))
        except Exception as exc:
            import warnings
            warnings.warn(
                f"Skipping one polygon in MultiPolygon due to error: {exc}",
                stacklevel=2,
            )
    return all_cells


# ── Unified geometry dispatcher ───────────────────────────────────────────────

def geometry_to_h3(
    geom_input: object,
    h3_resolution: int,
    contain_mode: str = "center",
) -> set[str]:
    """
    Convert many input formats to a set of H3 cell indices.

    Auto-detects the type of *geom_input* and dispatches to the appropriate
    conversion function.  For H3 index string inputs the function navigates
    the H3 hierarchy to reach the requested resolution.

    Parameters
    ----------
    geom_input : various
        Supported input types:

        * :class:`shapely.geometry.Point`
        * :class:`shapely.geometry.Polygon`
        * :class:`shapely.geometry.MultiPolygon`
        * ``(lat, lon)`` numeric tuple or list
        * DMS pair string — ``"39°48'18\\" N 089°38'42\\" W"``
        * DDM pair string — ``"39 48.3 N 089 38.7 W"``
        * MGRS string — ``"30UXC0529398803"``
        * H3 index string — returns the cell itself, its children, or its
          parent, depending on the relationship between the cell's resolution
          and *h3_resolution*.
    h3_resolution : int
        Target H3 resolution level, in [0, 15].
    contain_mode : {'center', 'full', 'overlap', 'bbox_overlap'}, optional
        Used only for ``Polygon`` / ``MultiPolygon`` inputs.
        See :func:`polygon_to_h3` for details.  Default is ``'center'``.

    Returns
    -------
    set of str
        One or more H3 cell index strings at *h3_resolution*.

    Raises
    ------
    TypeError
        If *geom_input* is not a supported type.
    ValueError
        If *h3_resolution* is outside [0, 15], or the string cannot be
        matched to any recognised format.

    See Also
    --------
    coordinate_to_h3 : Coordinate-only dispatcher (no Shapely geometry support).
    polygon_to_h3 : Direct polygon conversion.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> cells = geometry_to_h3(Point(-0.1278, 51.5074), h3_resolution=9)
    >>> len(cells) == 1
    True

    >>> cells = geometry_to_h3((51.5074, -0.1278), 9)
    >>> len(cells) == 1
    True

    >>> cells = geometry_to_h3("30UXC0529398803", 9)
    >>> isinstance(next(iter(cells)), str)
    True

    >>> # Passing an H3 index to move up the hierarchy:
    >>> cells = geometry_to_h3("89195da49b7ffff", h3_resolution=7)
    >>> len(cells) == 1
    True
    """
    _validate_h3_resolution(h3_resolution)

    if isinstance(geom_input, Point):
        return {point_to_h3(geom_input, h3_resolution)}

    if isinstance(geom_input, Polygon):
        return polygon_to_h3(geom_input, h3_resolution, contain_mode)

    if isinstance(geom_input, shapely.geometry.MultiPolygon):
        return multipolygon_to_h3(geom_input, h3_resolution, contain_mode)

    if isinstance(geom_input, (tuple, list)) and len(geom_input) == 2:
        return {point_to_h3(latlon_to_point(geom_input), h3_resolution)}

    if isinstance(geom_input, str):
        cleaned = geom_input.strip()

        # MGRS
        if re.match(r"^\d{1,2}[C-X]", cleaned.upper()):
            return {point_to_h3(mgrs_to_point(cleaned), h3_resolution)}

        # DMS / DDM
        if re.search(r"[NSEWnsew]", cleaned) and re.search(r"\d", cleaned):
            try:
                pt = dms_to_point(cleaned)
            except ValueError:
                pt = ddm_to_point(cleaned)
            return {point_to_h3(pt, h3_resolution)}

        # H3 index
        if is_h3_valid(cleaned):
            current_res = get_h3_resolution(cleaned)
            if current_res == h3_resolution:
                return {cleaned}
            if current_res < h3_resolution:
                children = (
                    h3.cell_to_children(cleaned, h3_resolution)
                    if IS_H3_V4
                    else h3.to_children(cleaned, h3_resolution)
                )
                return set(children)
            # current_res > h3_resolution → return parent
            parent = (
                h3.cell_to_parent(cleaned, h3_resolution)
                if IS_H3_V4
                else h3.h3_to_parent(cleaned, h3_resolution)
            )
            return {parent}

        raise ValueError(f"Unrecognised string format: {geom_input!r}")

    raise TypeError(
        f"Unsupported input type: {type(geom_input).__name__}. "
        "Supported: Point, Polygon, MultiPolygon, (lat,lon), "
        "DMS/DDM string, MGRS string, or H3 index."
    )


# ── H3 → geometry ────────────────────────────────────────────────────────────

def h3_to_point(h3_index: str, return_latlon: bool = False):
    """
    Return the centre of an H3 cell as a Shapely ``Point``.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.
    return_latlon : bool, optional
        If ``True``, return a ``(lat, lon)`` tuple instead of a Shapely
        ``Point``.  Default is ``False``.

    Returns
    -------
    shapely.geometry.Point or tuple of float
        * ``Point(longitude, latitude)`` when *return_latlon* is ``False``.
        * ``(latitude, longitude)`` decimal-degree tuple when
          *return_latlon* is ``True``.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index.

    Notes
    -----
    Internally delegates to ``h3.cell_to_latlng`` (v4) or
    ``h3.h3_to_geo`` (v3).

    See Also
    --------
    h3_to_polygon : Return the cell boundary as a polygon instead.
    h3_to_mgrs : Return the centre in MGRS format.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pt = h3_to_point("89195da49b7ffff")
    >>> isinstance(pt, Point)
    True

    >>> lat, lon = h3_to_point("89195da49b7ffff", return_latlon=True)
    >>> -90 <= lat <= 90 and -180 <= lon <= 180
    True
    """
    _validate_h3_index(h3_index)
    lat_dd, lon_dd = (
        h3.cell_to_latlng(h3_index) if IS_H3_V4 else h3.h3_to_geo(h3_index)
    )
    return (lat_dd, lon_dd) if return_latlon else Point(lon_dd, lat_dd)


def h3_to_polygon(h3_index: str, closed: bool = True) -> Polygon:
    """
    Return the boundary of an H3 cell as a Shapely ``Polygon``.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.
    closed : bool, optional
        If ``True`` *(default)*, the exterior ring is closed
        (first vertex == last vertex), as required by the Shapely/WKT
        convention.  Set to ``False`` to omit the repeated closing vertex.

    Returns
    -------
    shapely.geometry.Polygon
        Polygon whose exterior ring traces the H3 cell boundary.
        Coordinates are in ``(longitude, latitude)`` order.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index.

    Notes
    -----
    The H3 API returns boundary vertices in ``(lat, lon)`` order; this
    function swaps them to Shapely's ``(lon, lat)`` / ``(x, y)``
    convention.

    Internally delegates to ``h3.cell_to_boundary`` (v4) or
    ``h3.h3_to_geo_boundary`` (v3).

    See Also
    --------
    h3_to_point : Return the cell centre as a point instead.

    Examples
    --------
    >>> from shapely.geometry import Polygon
    >>> poly = h3_to_polygon("89195da49b7ffff")
    >>> isinstance(poly, Polygon)
    True
    >>> not poly.is_empty
    True
    """
    _validate_h3_index(h3_index)
    boundary = (
        h3.cell_to_boundary(h3_index) if IS_H3_V4 else h3.h3_to_geo_boundary(h3_index)
    )
    coords = [(lon, lat) for lat, lon in boundary]
    if closed and coords and coords[0] != coords[-1]:
        coords = coords + [coords[0]]
    return Polygon(coords)


def h3_to_mgrs(h3_index: str, precision: int = None) -> str:
    """
    Return the MGRS coordinate string for the centre of an H3 cell.

    The precision level is auto-selected from the cell's resolution when
    not explicitly provided:

    =========  ===========  ==========
    H3 res     Precision    Accuracy
    =========  ===========  ==========
    0 – 5      2            ~1 km
    6 – 7      3            ~100 m
    8 – 11     4            ~10 m
    12 – 15    5            ~1 m
    =========  ===========  ==========

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.
    precision : int, optional
        MGRS precision level in [0, 5].  When omitted, precision is
        automatically derived from the cell's resolution using the table
        above.

    Returns
    -------
    str
        MGRS coordinate string for the cell's centre point.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index.
    TypeError
        If *precision* is provided but is not an ``int``.
    ValueError
        If *precision* is provided but falls outside [0, 5].

    See Also
    --------
    mgrs_to_h3 : Reverse conversion — MGRS string → H3 cell index.
    h3_to_point : Return the centre as a Shapely ``Point`` or tuple.

    Examples
    --------
    >>> mgrs = h3_to_mgrs("89195da49b7ffff")
    >>> isinstance(mgrs, str) and len(mgrs) > 0
    True

    >>> mgrs_precise = h3_to_mgrs("89195da49b7ffff", precision=5)
    >>> len(mgrs_precise) > len(h3_to_mgrs("89195da49b7ffff", precision=2))
    True
    """
    _validate_h3_index(h3_index)

    lat, lon = h3_to_point(h3_index, return_latlon=True)
    res = get_h3_resolution(h3_index)

    if precision is None:
        if res <= 5:
            precision = 2
        elif res <= 7:
            precision = 3
        elif res <= 11:
            precision = 4
        else:
            precision = 5

    _validate_mgrs_precision(precision)
    m = mgrs_lib.MGRS()
    return m.toMGRS(lat, lon, MGRSPrecision=precision)


# ── Point-to-point path ───────────────────────────────────────────────────────

def points_to_h3_path(
    point1: Point,
    point2: Point,
    h3_resolution: int,
) -> list[str]:
    """
    Return the ordered H3 grid path between two geographic points.

    Converts each point to an H3 cell at *h3_resolution*, then computes
    the shortest grid path between the two cells.  This is a convenience
    wrapper that combines :func:`point_to_h3` with
    :func:`h3tools.analytics.get_h3_path`, accepting geographic coordinates
    rather than H3 indices.

    Parameters
    ----------
    point1 : shapely.geometry.Point
        Start location in WGS-84 (``x = longitude``, ``y = latitude``).
    point2 : shapely.geometry.Point
        End location in WGS-84 (``x = longitude``, ``y = latitude``).
    h3_resolution : int
        H3 resolution at which to resolve both points and trace the path.
        Must be in [0, 15].

    Returns
    -------
    list of str
        Ordered H3 cell index strings from the cell containing *point1*
        to the cell containing *point2*, inclusive of both endpoints.
        If both points resolve to the same cell at *h3_resolution*, a
        single-element list is returned.

    Raises
    ------
    TypeError
        If either *point1* or *point2* is not a
        :class:`shapely.geometry.Point`.
    ValueError
        If either point is empty or out of WGS-84 bounds; if
        *h3_resolution* is outside [0, 15]; or if the H3 grid path
        cannot be computed (e.g. the path crosses a pentagon cell).

    Notes
    -----
    The path is ordered: ``result[0]`` is always the cell containing
    *point1* and ``result[-1]`` is always the cell containing *point2*.

    At coarse resolutions both points may resolve to the same cell,
    producing a single-element list without an error.

    See Also
    --------
    get_h3_path : Compute a path directly from two H3 cell indices.
    point_to_h3 : Convert a single point to an H3 cell index.
    linestring_to_h3 : Convert a full ``LineString`` geometry to H3 cells.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> london = Point(-0.1278, 51.5074)
    >>> nearby = Point(-0.15, 51.52)
    >>> path = points_to_h3_path(london, nearby, h3_resolution=9)
    >>> isinstance(path, list) and len(path) >= 1
    True
    >>> path[0] == point_to_h3(london, 9)
    True
    """
    from h3tools.analytics import get_h3_path

    _validate_point(point1)
    _validate_point(point2)
    _validate_h3_resolution(h3_resolution)

    start_cell = point_to_h3(point1, h3_resolution)
    end_cell = point_to_h3(point2, h3_resolution)

    if start_cell == end_cell:
        return [start_cell]

    return get_h3_path(start_cell, end_cell)


# ── Decimal-degree → DMS / DDM formatters ────────────────────────────────────

def _dd_to_dms(dd: float, is_lat: bool) -> str:
    """Format a decimal-degree value as a DMS string (e.g. ``51°30'26.16"N``)."""
    direction = ("N" if dd >= 0 else "S") if is_lat else ("E" if dd >= 0 else "W")
    dd = abs(dd)
    degrees = int(dd)
    minutes_float = (dd - degrees) * 60.0
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60.0
    return f"{degrees}°{minutes:02d}'{seconds:05.2f}\"{direction}"


def _dd_to_ddm(dd: float, is_lat: bool) -> str:
    """Format a decimal-degree value as a DDM string (e.g. ``51°30.436'N``)."""
    direction = ("N" if dd >= 0 else "S") if is_lat else ("E" if dd >= 0 else "W")
    dd = abs(dd)
    degrees = int(dd)
    minutes = (dd - degrees) * 60.0
    return f"{degrees}°{minutes:06.3f}'{direction}"


# ── H3 → DMS / DDM ───────────────────────────────────────────────────────────

def h3_to_dms(h3_index: str) -> tuple[str, str]:
    """
    Return the centre of an H3 cell as a Degrees-Minutes-Seconds string pair.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.

    Returns
    -------
    tuple of (str, str)
        ``(lat_dms, lon_dms)`` where each string uses the format
        ``{deg}°{min:02d}'{sec:05.2f}"{N|S|E|W}``, for example
        ``("51°30'26.16\\"N", "0°07'40.08\\"W")``.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index.

    See Also
    --------
    h3_to_ddm : Return the centre in Degrees Decimal Minutes format.
    h3_to_point : Return the centre as a Shapely ``Point``.
    dms_to_h3 : Reverse conversion — DMS string → H3 cell index.

    Examples
    --------
    >>> lat_dms, lon_dms = h3_to_dms("89195da49b7ffff")
    >>> lat_dms.endswith("N") or lat_dms.endswith("S")
    True
    >>> lon_dms.endswith("E") or lon_dms.endswith("W")
    True
    """
    _validate_h3_index(h3_index)
    lat_dd, lon_dd = h3_to_point(h3_index, return_latlon=True)
    return _dd_to_dms(lat_dd, is_lat=True), _dd_to_dms(lon_dd, is_lat=False)


def h3_to_ddm(h3_index: str) -> tuple[str, str]:
    """
    Return the centre of an H3 cell as a Degrees-Decimal-Minutes string pair.

    Parameters
    ----------
    h3_index : str
        Valid H3 cell index string.

    Returns
    -------
    tuple of (str, str)
        ``(lat_ddm, lon_ddm)`` where each string uses the format
        ``{deg}°{min:06.3f}'{N|S|E|W}``, for example
        ``("51°30.436'N", "0°07.668'W")``.

    Raises
    ------
    ValueError
        If *h3_index* is not a valid H3 cell index.

    See Also
    --------
    h3_to_dms : Return the centre in Degrees Minutes Seconds format.
    h3_to_point : Return the centre as a Shapely ``Point``.
    ddm_to_point : Parse a DDM string back to a Shapely ``Point``.

    Examples
    --------
    >>> lat_ddm, lon_ddm = h3_to_ddm("89195da49b7ffff")
    >>> lat_ddm.endswith("N") or lat_ddm.endswith("S")
    True
    >>> lon_ddm.endswith("E") or lon_ddm.endswith("W")
    True
    """
    _validate_h3_index(h3_index)
    lat_dd, lon_dd = h3_to_point(h3_index, return_latlon=True)
    return _dd_to_ddm(lat_dd, is_lat=True), _dd_to_ddm(lon_dd, is_lat=False)


# ── Cell dissolve ─────────────────────────────────────────────────────────────

def dissolve_h3_cells(cells) -> Polygon | shapely.geometry.MultiPolygon:
    """
    Merge a collection of H3 cells into a single dissolved Shapely geometry.

    Converts each cell to its boundary polygon and applies
    :func:`shapely.ops.unary_union` to produce a merged geometry.
    Contiguous cells produce a single ``Polygon``; disconnected groups
    produce a ``MultiPolygon``.

    Parameters
    ----------
    cells : str or iterable of str
        One or more valid H3 cell index strings.  A bare string is treated
        as a single cell.  Duplicate cells are silently deduplicated.

    Returns
    -------
    shapely.geometry.Polygon or shapely.geometry.MultiPolygon
        Dissolved geometry covering all supplied cells.

    Raises
    ------
    ValueError
        If *cells* is empty, or if any element is not a valid H3 cell index.

    See Also
    --------
    h3_to_polygon : Return the boundary of a single cell.
    polygon_to_h3 : Convert a polygon back to a set of H3 cells.

    Examples
    --------
    >>> from h3tools.analytics import get_h3_neighbors
    >>> disk = get_h3_neighbors("89195da49b7ffff", k=1)
    >>> geom = dissolve_h3_cells(disk)
    >>> geom.is_valid and not geom.is_empty
    True

    >>> # Single cell dissolve equals its own boundary polygon:
    >>> single = dissolve_h3_cells("89195da49b7ffff")
    >>> isinstance(single, Polygon)
    True
    """
    from collections.abc import Iterable

    if isinstance(cells, str):
        cells = [cells]
    else:
        cells = list(cells)

    if not cells:
        raise ValueError("dissolve_h3_cells() requires at least one cell.")

    unique = list(dict.fromkeys(cells))  # deduplicate while preserving order
    for cell in unique:
        _validate_h3_index(cell)

    polys = [h3_to_polygon(cell) for cell in unique]
    return unary_union(polys)


# ── GeoJSON I/O ───────────────────────────────────────────────────────────────

def cells_to_geojson(cells) -> dict:
    """
    Serialise H3 cells to a GeoJSON FeatureCollection dict.

    Each cell is represented as a GeoJSON ``Feature`` with a ``Polygon``
    geometry (the cell boundary) and an ``h3_index`` property.  The
    returned dict is immediately serialisable with :func:`json.dumps`.

    Parameters
    ----------
    cells : str or iterable of str
        One or more valid H3 cell index strings.  A bare string is treated
        as a single cell.  Duplicate cells are silently deduplicated.

    Returns
    -------
    dict
        GeoJSON ``FeatureCollection`` with one ``Feature`` per unique cell.

    Raises
    ------
    ValueError
        If *cells* is empty or any element is not a valid H3 cell index.

    See Also
    --------
    geojson_to_cells : Reverse conversion — GeoJSON → H3 cells.
    dissolve_h3_cells : Merge cells into a single Shapely geometry instead.

    Examples
    --------
    >>> from h3tools.geo import point_to_h3, cells_to_geojson
    >>> cell = point_to_h3(__import__('shapely.geometry', fromlist=['Point']).Point(-0.1278, 51.5074), 9)
    >>> fc = cells_to_geojson(cell)
    >>> fc["type"]
    'FeatureCollection'
    >>> len(fc["features"]) == 1
    True
    >>> fc["features"][0]["properties"]["h3_index"] == cell
    True
    """
    from collections.abc import Iterable

    if isinstance(cells, str):
        cells = [cells]
    else:
        cells = list(cells)

    if not cells:
        raise ValueError("cells_to_geojson() requires at least one cell.")

    unique = list(dict.fromkeys(cells))
    features = []
    for cell in unique:
        _validate_h3_index(cell)
        poly = h3_to_polygon(cell)
        coords = [list(coord) for coord in poly.exterior.coords]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {"h3_index": cell},
        })

    return {"type": "FeatureCollection", "features": features}


def geojson_to_cells(geojson: dict | str, resolution: int) -> set[str]:
    """
    Convert a GeoJSON geometry, Feature, or FeatureCollection to H3 cells.

    Traverses the GeoJSON structure recursively and fills every
    ``Polygon`` or ``MultiPolygon`` geometry with H3 cells at
    *resolution* using centre-point containment.  ``Feature`` and
    ``FeatureCollection`` wrappers are unpacked automatically.

    Parameters
    ----------
    geojson : dict or str
        A GeoJSON object as either a Python ``dict`` or a JSON string.
        Supported ``"type"`` values:

        * ``"FeatureCollection"`` — all features are processed and unioned.
        * ``"Feature"`` — the feature's geometry is processed.
        * ``"Polygon"`` / ``"MultiPolygon"`` — converted directly.
    resolution : int
        Target H3 resolution level, in [0, 15].

    Returns
    -------
    set of str
        Unique H3 cell index strings covering all polygon geometries in
        the input.

    Raises
    ------
    TypeError
        If *geojson* is not a ``dict`` or ``str``.
    ValueError
        If *resolution* is outside [0, 15], *geojson* is not valid JSON,
        or the ``"type"`` field is absent or unsupported.

    See Also
    --------
    cells_to_geojson : Reverse conversion — H3 cells → GeoJSON.
    polygon_to_h3 : Convert a Shapely ``Polygon`` directly.

    Examples
    --------
    >>> fc = {"type": "FeatureCollection", "features": [
    ...     {"type": "Feature",
    ...      "geometry": {"type": "Polygon",
    ...                   "coordinates": [[[-0.14, 51.49], [-0.11, 51.49],
    ...                                    [-0.11, 51.52], [-0.14, 51.52],
    ...                                    [-0.14, 51.49]]]},
    ...      "properties": {}}
    ... ]}
    >>> cells = geojson_to_cells(fc, resolution=10)
    >>> len(cells) > 0
    True
    """
    from shapely.geometry import shape

    _validate_h3_resolution(resolution)

    if isinstance(geojson, str):
        try:
            geojson = json.loads(geojson)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON string: {exc}") from exc

    if not isinstance(geojson, dict):
        raise TypeError(
            f"geojson must be a dict or JSON string, got {type(geojson).__name__}."
        )

    geo_type = geojson.get("type")

    if geo_type == "FeatureCollection":
        cells: set[str] = set()
        for feature in geojson.get("features", []):
            cells |= geojson_to_cells(feature, resolution)
        return cells

    if geo_type == "Feature":
        geometry = geojson.get("geometry")
        if not geometry:
            return set()
        return geojson_to_cells(geometry, resolution)

    if geo_type == "Polygon":
        return polygon_to_h3(shape(geojson), resolution)

    if geo_type == "MultiPolygon":
        return multipolygon_to_h3(shape(geojson), resolution)

    raise ValueError(
        f"Unsupported GeoJSON type {geo_type!r}. "
        "Expected Polygon, MultiPolygon, Feature, or FeatureCollection."
    )


# ── Bounding box ──────────────────────────────────────────────────────────────

def geometry_to_box(geometry: BaseGeometry, as_polygon: bool = False) -> str | Polygon:
    """
    Convert a Shapely geometry to its axis-aligned bounding box.

    Computes the bounding box from *geometry* and returns it either as a
    PostGIS ``BOX(...)`` string (default) or as a Shapely ``Polygon`` via
    the geometry's :attr:`~shapely.geometry.base.BaseGeometry.envelope`
    property.  ``Point`` geometries are rejected because a single point
    has coincident bounds and cannot form a meaningful bounding box or
    polygon.

    Parameters
    ----------
    geometry : shapely.geometry.base.BaseGeometry
        Any Shapely geometry except ``Point`` — e.g. ``LineString``,
        ``Polygon``, ``MultiPolygon``, ``GeometryCollection``.
    as_polygon : bool, optional
        Controls the return type:

        * ``False`` (default) — return a PostGIS BOX string of the form
          ``"BOX(minx miny, maxx maxy)"``, suitable for storage or database
          queries.
        * ``True`` — return the bounding box as a Shapely ``Polygon``
          using the geometry's :attr:`envelope` property, suitable for
          spatial operations.

    Returns
    -------
    str
        PostGIS BOX string when *as_polygon* is ``False``.
    shapely.geometry.Polygon
        Axis-aligned rectangular polygon when *as_polygon* is ``True``.

    Raises
    ------
    TypeError
        If *geometry* is not a Shapely geometry object.
        If *as_polygon* is not a ``bool``.
    ValueError
        If *geometry* is a ``Point`` (degenerate zero-area bounding box).

    See Also
    --------
    dissolve_h3_cells : Merge H3 cells into a single geometry.
    h3_to_polygon : Convert an H3 cell to its boundary polygon.

    Examples
    --------
    >>> from shapely.geometry import Polygon
    >>> poly = Polygon([(-0.14, 51.49), (-0.11, 51.49), (-0.11, 51.52), (-0.14, 51.52)])
    >>> geometry_to_box(poly)
    'BOX(-0.14 51.49,-0.11 51.52)'

    >>> envelope = geometry_to_box(poly, as_polygon=True)
    >>> isinstance(envelope, Polygon)
    True
    >>> envelope.bounds == poly.bounds
    True
    """
    if not isinstance(geometry, BaseGeometry):
        raise TypeError(
            f"geometry_to_box() expected a Shapely geometry, got {type(geometry).__name__}."
        )
    if isinstance(geometry, Point):
        raise ValueError(
            "geometry_to_box() does not accept Point geometries — a single point "
            "has coincident bounds and cannot form a meaningful bounding box."
        )
    if not isinstance(as_polygon, bool):
        raise TypeError(
            f"geometry_to_box() as_polygon must be a bool, got {type(as_polygon).__name__}."
        )

    if as_polygon:
        return geometry.envelope

    minx, miny, maxx, maxy = geometry.bounds
    return f"BOX({minx} {miny},{maxx} {maxy})"
