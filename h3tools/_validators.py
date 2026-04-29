"""
h3tools._validators
====================
Internal validation helpers shared across all h3tools modules.

Every function raises on invalid input and returns ``None`` on success,
so call sites can use them as simple guard clauses without inspecting a
return value.

.. note::
   This module is private to h3tools.  Do not import it directly in
   application code; use the public API exposed by each submodule instead.

Module Attributes
-----------------
H3_RESOLUTION_MIN : int
    Minimum valid H3 resolution (0).
H3_RESOLUTION_MAX : int
    Maximum valid H3 resolution (15).
_VALID_CONTAIN_MODES : tuple of str
    Accepted polygon-containment mode strings used by
    :func:`h3tools.geo.polygon_to_h3`.
"""

from __future__ import annotations

import re
from shapely.geometry import Point, Polygon

# ── Constants ─────────────────────────────────────────────────────────────────
H3_RESOLUTION_MIN: int = 0
H3_RESOLUTION_MAX: int = 15
_VALID_CONTAIN_MODES: tuple = ("center", "full", "overlap", "bbox_overlap")


# ── H3 ────────────────────────────────────────────────────────────────────────

def _validate_h3_index(h3_index: str) -> None:
    """
    Raise ``ValueError`` if *h3_index* is not a valid H3 cell index string.

    Delegates the actual validity check to :func:`h3tools.core.is_h3_valid`,
    which handles both h3-py v3.x and v4.x transparently.

    Parameters
    ----------
    h3_index : str
        The candidate H3 index string to validate (hexadecimal format).

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If *h3_index* is not a ``str``, or if it is not recognised as a
        valid H3 cell by the installed h3-py version.

    Examples
    --------
    >>> validate_h3_index("89195da49b7ffff")   # valid — returns None
    >>> validate_h3_index("not_a_cell")
    Traceback (most recent call last):
        ...
    ValueError: Invalid H3 index: 'not_a_cell'
    """
    from h3tools.core import is_h3_valid
    if not isinstance(h3_index, str) or not is_h3_valid(h3_index):
        raise ValueError(f"Invalid H3 index: {h3_index!r}")


def _validate_h3_resolution(h3_resolution: int) -> None:
    """
    Raise ``ValueError`` if *h3_resolution* is outside the valid range [0, 15].

    Parameters
    ----------
    h3_resolution : int
        The H3 resolution level to validate.

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If *h3_resolution* is not an ``int``, or if it falls outside
        ``[H3_RESOLUTION_MIN, H3_RESOLUTION_MAX]`` (i.e. outside [0, 15]).

    Examples
    --------
    >>> validate_h3_resolution(9)    # valid — returns None
    >>> validate_h3_resolution(16)
    Traceback (most recent call last):
        ...
    ValueError: H3 resolution must be between 0 and 15, got 16.
    """
    if isinstance(h3_resolution, bool):
        raise ValueError("H3 resolution must be an integer, not bool.")
    if not isinstance(h3_resolution, int):
        raise ValueError(
            f"H3 resolution must be an integer, got {type(h3_resolution).__name__}."
        )
    if not (H3_RESOLUTION_MIN <= h3_resolution <= H3_RESOLUTION_MAX):
        raise ValueError(
            f"H3 resolution must be between {H3_RESOLUTION_MIN} and "
            f"{H3_RESOLUTION_MAX}, got {h3_resolution}."
        )


# ── Coordinates ───────────────────────────────────────────────────────────────

def _validate_latitude(latitude: float) -> None:
    """
    Raise ``ValueError`` if *latitude* is not a valid WGS-84 latitude.

    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees.  Must be numeric and in [-90, 90].

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If *latitude* is not a numeric type, or falls outside [-90.0, 90.0].

    Examples
    --------
    >>> validate_latitude(51.5074)   # valid — returns None
    >>> validate_latitude(91.0)
    Traceback (most recent call last):
        ...
    ValueError: Latitude must be in [-90, 90], got 91.0.
    """
    if not isinstance(latitude, (int, float)):
        raise ValueError(
            f"Latitude must be a number, got {type(latitude).__name__}."
        )
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(
            f"Latitude must be in [-90, 90], got {latitude}."
        )


def _validate_longitude(longitude: float) -> None:
    """
    Raise ``ValueError`` if *longitude* is not a valid WGS-84 longitude.

    Parameters
    ----------
    longitude : float
        Longitude in decimal degrees.  Must be numeric and in [-180, 180].

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If *longitude* is not a numeric type, or falls outside [-180.0, 180.0].

    Examples
    --------
    >>> validate_longitude(-0.1278)   # valid — returns None
    >>> validate_longitude(181.0)
    Traceback (most recent call last):
        ...
    ValueError: Longitude must be in [-180, 180], got 181.0.
    """
    if not isinstance(longitude, (int, float)):
        raise ValueError(
            f"Longitude must be a number, got {type(longitude).__name__}."
        )
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(
            f"Longitude must be in [-180, 180], got {longitude}."
        )


def _validate_point(point: Point) -> None:
    """
    Raise if *point* is not a valid, non-empty, in-bounds Shapely ``Point``.

    Checks are performed in order: type, emptiness, WGS-84 coordinate bounds.

    Parameters
    ----------
    point : shapely.geometry.Point
        The point to validate.  Coordinates are expected in
        ``(longitude, latitude)`` order (i.e. Shapely's ``(x, y)``
        convention).  Valid bounds: lon ∈ [-180, 180], lat ∈ [-90, 90].

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If *point* is not an instance of :class:`shapely.geometry.Point`.
    ValueError
        If *point* is an empty geometry, or if either coordinate falls
        outside WGS-84 bounds.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> validate_point(Point(-0.1278, 51.5074))   # valid — returns None
    >>> validate_point(Point(200, 0))
    Traceback (most recent call last):
        ...
    ValueError: Point coordinates out of WGS-84 bounds: x=200, y=0.
    """
    if not isinstance(point, Point):
        raise TypeError(
            f"Expected shapely.geometry.Point, got {type(point).__name__}."
        )
    if point.is_empty:
        raise ValueError("Cannot use an empty Point.")
    if not (-180 <= point.x <= 180 and -90 <= point.y <= 90):
        raise ValueError(
            f"Point coordinates out of WGS-84 bounds: "
            f"x={point.x}, y={point.y}."
        )


def _validate_polygon(polygon: Polygon) -> None:
    """
    Raise ``TypeError`` if *polygon* is not a Shapely ``Polygon``.

    Parameters
    ----------
    polygon : shapely.geometry.Polygon
        The polygon to validate.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If *polygon* is not an instance of :class:`shapely.geometry.Polygon`.

    Notes
    -----
    This function checks the type only.  Geometric validity (e.g. self-
    intersections) is not checked here; callers that require a topologically
    valid polygon should call ``polygon.buffer(0)`` before passing the
    geometry to other functions.

    Examples
    --------
    >>> from shapely.geometry import Polygon
    >>> validate_polygon(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]))  # returns None
    >>> validate_polygon("not a polygon")
    Traceback (most recent call last):
        ...
    TypeError: Expected shapely.geometry.Polygon, got str.
    """
    if not isinstance(polygon, Polygon):
        raise TypeError(
            f"Expected shapely.geometry.Polygon, got {type(polygon).__name__}."
        )


# ── MGRS ──────────────────────────────────────────────────────────────────────

def _validate_mgrs(mgrs_str: str) -> None:
    """
    Raise if *mgrs_str* is not a structurally valid MGRS coordinate string.

    Structural checks performed (in order):

    1. Non-empty ``str``.
    2. Minimum length of 3 characters after whitespace removal.
    3. Pattern match: ``<zone><band-letter><2-letter-square><0–10 digit-pairs>``.
    4. UTM zone number in [1, 60].

    Parameters
    ----------
    mgrs_str : str
        The MGRS coordinate string to validate, e.g. ``"30UXC0529398803"``.
        Leading/trailing whitespace is stripped before validation.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If *mgrs_str* is not a non-empty ``str``.
    ValueError
        If the string is too short, does not match the MGRS pattern, or
        contains an out-of-range UTM zone number.

    Notes
    -----
    Band letters I and O are excluded by the regex (``[C-X]`` skips them)
    because they are not used in the MGRS standard.

    Examples
    --------
    >>> validate_mgrs("30UXC0529398803")   # valid — returns None
    >>> validate_mgrs("ZZ9999999")
    Traceback (most recent call last):
        ...
    ValueError: Invalid MGRS format (wrong structure or forbidden letters): 'ZZ9999999'
    """
    if not isinstance(mgrs_str, str) or not mgrs_str.strip():
        raise TypeError(
            f"MGRS coordinate must be a non-empty string, "
            f"got {type(mgrs_str).__name__}."
        )
    cleaned = re.sub(r"\s+", "", mgrs_str.strip().upper())
    if len(cleaned) < 3:
        raise ValueError(
            f"MGRS string too short (got {len(cleaned)} chars): {mgrs_str!r}"
        )
    if not re.match(r"^\d{1,2}[C-X][A-Z]{2}(\d{0,10})$", cleaned):
        raise ValueError(
            f"Invalid MGRS format (wrong structure or forbidden letters): "
            f"{mgrs_str!r}"
        )
    zone = int(re.match(r"^(\d{1,2})", cleaned).group(1))
    if not (1 <= zone <= 60):
        raise ValueError(f"Invalid UTM zone {zone} (must be 1–60).")


def _validate_mgrs_precision(precision: int) -> None:
    """
    Raise if *precision* is not a valid MGRS precision level.

    MGRS precision controls the number of easting/northing digit pairs and
    corresponds to a positional accuracy:

    =========  ====================
    Precision  Approximate accuracy
    =========  ====================
    0          100 km
    1          10 km
    2          1 km
    3          100 m
    4          10 m
    5          1 m
    =========  ====================

    Parameters
    ----------
    precision : int
        MGRS precision level.  Must be an integer in [0, 5].

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If *precision* is not an ``int``.
    ValueError
        If *precision* falls outside [0, 5].

    Examples
    --------
    >>> validate_mgrs_precision(4)   # valid — returns None
    >>> validate_mgrs_precision(6)
    Traceback (most recent call last):
        ...
    ValueError: MGRS precision must be in [0, 5], got 6.
    """
    if not isinstance(precision, int):
        raise TypeError(
            f"MGRS precision must be an integer, got {type(precision).__name__}."
        )
    if not (0 <= precision <= 5):
        raise ValueError(
            f"MGRS precision must be in [0, 5], got {precision}."
        )


# ── DMS / DDM ─────────────────────────────────────────────────────────────────

def _validate_dms(dms_str: str) -> None:
    """
    Perform basic structural validation on a DMS lat/lon pair string.

    Checks that the string contains exactly one N/S hemisphere indicator,
    exactly one E/W hemisphere indicator, and at least one digit.
    Symbol choice (``°``, ``˚``, ``'``, ``"``, etc.) is deliberately
    permissive to accommodate the wide variety of DMS formats encountered
    in practice.

    Parameters
    ----------
    dms_str : str
        DMS coordinate pair string, e.g.
        ``"39°48'18\\" N 089°38'42\\" W"``.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If *dms_str* is not a ``str``.
    ValueError
        If the string is empty or whitespace, contains no digit, or does
        not have exactly one N/S and one E/W direction indicator.

    Notes
    -----
    Full parsing of degrees, minutes, and seconds — including fractional
    seconds — is performed by :func:`h3tools.geo.dms_to_point`.  This
    function only confirms that the string has the expected directional
    structure before parsing is attempted.

    Examples
    --------
    >>> validate_dms("39°48'18\\" N 089°38'42\\" W")   # valid — returns None
    >>> validate_dms("39 48 18 089 38 42")
    Traceback (most recent call last):
        ...
    ValueError: DMS pair must contain exactly one N/S direction, found 0.
    """
    if not isinstance(dms_str, str):
        raise TypeError(
            f"DMS string must be str, got {type(dms_str).__name__}."
        )
    if not dms_str.strip():
        raise ValueError("DMS string cannot be empty or whitespace.")
    scrubbed = re.sub(r"[°˚º′''″\"˝¨:\s]", "", dms_str).upper()
    ns = len(re.findall(r"[NS]", scrubbed))
    ew = len(re.findall(r"[EW]", scrubbed))
    if ns != 1:
        raise ValueError(
            f"DMS pair must contain exactly one N/S direction, found {ns}."
        )
    if ew != 1:
        raise ValueError(
            f"DMS pair must contain exactly one E/W direction, found {ew}."
        )
    if not re.search(r"\d", dms_str):
        raise ValueError("DMS string must contain at least one digit.")


def _validate_ddm_pair(ddm_str: str) -> None:
    """
    Perform basic structural validation on a DDM lat/lon pair string.

    Checks that the string contains exactly one N/S hemisphere indicator,
    exactly one E/W hemisphere indicator, and at least one digit.

    Parameters
    ----------
    ddm_str : str
        DDM coordinate pair string, e.g. ``"39 48.3 N 089 38.7 W"``.

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If *ddm_str* is empty or whitespace, contains no digit, or does not
        have exactly one N/S and one E/W direction indicator.

    Notes
    -----
    Full parsing of degrees and decimal minutes is performed by
    :func:`h3tools.geo.ddm_to_point`.  This function only confirms the
    directional structure.

    Examples
    --------
    >>> validate_ddm_pair("51 30.4 N 0 7.7 W")   # valid — returns None
    >>> validate_ddm_pair("51 30.4 N")
    Traceback (most recent call last):
        ...
    ValueError: DDM pair must contain exactly one E/W direction, found 0.
    """
    if not isinstance(ddm_str, str) or not ddm_str.strip():
        raise ValueError("DDM string cannot be empty.")
    scrubbed = re.sub(r"[^NSEW0-9.\s]", "", ddm_str.upper())
    ns = len(re.findall(r"[NS]", scrubbed))
    ew = len(re.findall(r"[EW]", scrubbed))
    if ns != 1:
        raise ValueError(
            f"DDM pair must contain exactly one N/S direction, found {ns}."
        )
    if ew != 1:
        raise ValueError(
            f"DDM pair must contain exactly one E/W direction, found {ew}."
        )
    if not re.search(r"\d", ddm_str):
        raise ValueError(f"DDM string must contain numeric values: {ddm_str!r}")


# ── Datetime ──────────────────────────────────────────────────────────────────

def _validate_datetime(dt) -> None:
    """
    Raise ``TypeError`` if *dt* is not a :class:`datetime.datetime` object.

    Parameters
    ----------
    dt : object
        The value to validate.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If *dt* is not an instance of :class:`datetime.datetime`.

    Notes
    -----
    Both naive (no ``tzinfo``) and aware (with ``tzinfo``) datetimes are
    accepted.  Functions that require timezone-aware input perform their own
    additional checks.

    Examples
    --------
    >>> from datetime import datetime
    >>> validate_datetime(datetime(2026, 4, 24))   # valid — returns None
    >>> validate_datetime("2026-04-24")
    Traceback (most recent call last):
        ...
    TypeError: Expected datetime, got str.
    """
    from datetime import datetime
    if not isinstance(dt, datetime):
        raise TypeError(
            f"Expected datetime, got {type(dt).__name__}."
        )


def _validate_string(value: str) -> None:
    """
    Raise if *value* is not a non-empty ``str``.

    Parameters
    ----------
    value : str
        The value to validate.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If *value* is not a ``str``.
    ValueError
        If *value* is an empty string.

    Examples
    --------
    >>> validate_string("Europe/London")   # valid — returns None
    >>> validate_string("")
    Traceback (most recent call last):
        ...
    ValueError: String must be non-empty.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"Expected str, got {type(value).__name__}."
        )
    if not value:
        raise ValueError("String must be non-empty.")
