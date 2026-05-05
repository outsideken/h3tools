"""
h3tools.temporal
=================
Datetime, timezone, and solar-event utilities.

Provides helpers for parsing and normalising datetime objects, looking up
IANA timezone names and UTC offsets from geographic points, and computing
solar events (sunrise, sunset, and all three twilight phases) for any
location on a given date.

Soft dependencies — ``astral`` and ``timezonefinder`` — are detected at
import time.  Functions that require them raise :class:`ImportError` with
an installation hint if they are unavailable.

Module Attributes
-----------------
ASTRAL_DEPRESSION_ANGLES : dict of {str: float}
    Solar depression angles in degrees for the three recognised twilight
    phases: ``'Civil'`` (6°), ``'Nautical'`` (12°), and
    ``'Astronomical'`` (18°).

Functions
---------
convert_to_datetime
    Parse a string or pass-through a datetime object.
ensure_utc
    Make a datetime timezone-aware and convert it to UTC.
is_dt_naive
    Check whether a datetime lacks timezone information.
start_of_day
    Truncate a datetime to midnight (00:00:00.000000).
end_of_day
    Set a datetime to the last microsecond of the day (23:59:59.999999).
shift_tz_by_name
    Convert a datetime to a named IANA timezone.
point_to_tz_offset
    Return the IANA timezone name and UTC offset (hours) for a location.
get_solar_data
    Compute solar events and twilight phases for a location on a given date.
get_lunar_data
    Return moon phase, illumination percentage, and rise/set times for a
    location on a given date.
"""

from __future__ import annotations


import math
import warnings
from datetime import datetime, timedelta, timezone

from dateutil import parser as dateutil_parser
from shapely.geometry import Point

from h3tools._validators import (
    _validate_datetime,
    _validate_h3_index,
    _validate_point,
    _validate_string,
)

__all__ = [
    "ASTRAL_DEPRESSION_ANGLES",
    "convert_to_datetime",
    "is_dt_naive",
    "ensure_utc",
    "start_of_day",
    "end_of_day",
    "shift_tz_by_name",
    "point_to_tz_offset",
    "get_solar_data",
    "get_lunar_data",
]

# ── Optional-dependency guard ─────────────────────────────────────────────────
try:
    import astral
    from astral import Observer
    from astral.moon import phase as _astral_moon_phase
    from astral.sun import dawn, dusk, sun
    _ASTRAL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ASTRAL_AVAILABLE = False

try:
    import ephem as _ephem
    _EPHEM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _EPHEM_AVAILABLE = False

try:
    from timezonefinder import TimezoneFinder as _TF
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    _TF_INSTANCE = _TF()
    _TZ_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TZ_AVAILABLE = False

# ── Constants ─────────────────────────────────────────────────────────────────
ASTRAL_DEPRESSION_ANGLES: dict[str, float] = {
    "Civil": 6.0,
    "Nautical": 12.0,
    "Astronomical": 18.0,
}

# astral.moon.phase() returns a value in [0, 27] where 0 = new moon,
# ~7 = first quarter, ~14 = full moon, ~21 = last quarter.
_ASTRAL_LUNAR_SCALE: float = 27.0

# Phase name boundaries on the 0-27 scale (±0.5-day tolerance for named phases).
_PHASE_BOUNDARIES = [
    (1.0,  "New Moon"),
    (6.5,  "Waxing Crescent"),
    (7.5,  "First Quarter"),
    (13.5, "Waxing Gibbous"),
    (14.5, "Full Moon"),
    (20.5, "Waning Gibbous"),
    (21.5, "Last Quarter"),
    (26.5, "Waning Crescent"),
]


def _lunar_phase_name(phase_day: float) -> str:
    """Return a human-readable moon phase name for an astral phase value."""
    p = phase_day % _ASTRAL_LUNAR_SCALE
    for threshold, name in _PHASE_BOUNDARIES:
        if p < threshold:
            return name
    return "New Moon"


def _ephem_moon_riseset(
    pt, target_date, local_tz
) -> Tuple[datetime | None, datetime | None]:
    """Return (moonrise, moonset) for *target_date* at *pt* using ephem."""
    obs = _ephem.Observer()
    obs.lat = str(pt.y)
    obs.lon = str(pt.x)
    obs.elevation = 0
    obs.horizon = "0"
    obs.pressure = 0  # suppress atmospheric refraction correction

    local_midnight = datetime(
        target_date.year, target_date.month, target_date.day,
        tzinfo=local_tz,
    )
    utc_midnight = local_midnight.astimezone(timezone.utc)
    obs.date = utc_midnight.strftime("%Y/%m/%d %H:%M:%S")

    moon = _ephem.Moon()

    def _safe(fn):
        try:
            raw = fn(moon)
            return raw.datetime().replace(tzinfo=timezone.utc).astimezone(local_tz)
        except (_ephem.NeverUpError, _ephem.AlwaysUpError):
            return None

    return _safe(obs.next_rising), _safe(obs.next_setting)


# ── Datetime helpers ──────────────────────────────────────────────────────────

def convert_to_datetime(dt_input, ensure_utc: bool = False) -> datetime:
    """
    Parse a date/time string or pass through a :class:`datetime` object.

    Parameters
    ----------
    dt_input : str or datetime
        The value to convert.  Strings are parsed with
        :func:`dateutil.parser.parse`, which accepts a wide range of
        formats including ISO 8601, RFC 2822, and many natural-language
        date strings.
    ensure_utc : bool, optional
        If ``True``, a *naive* datetime (one with no ``tzinfo``) is
        assumed to represent UTC and is made timezone-aware by attaching
        :data:`datetime.timezone.utc`.  Aware datetimes are returned
        unchanged.  Default is ``False``.

    Returns
    -------
    datetime
        A :class:`datetime` object.  May be naive or aware depending on
        the input and *ensure_utc*.

    Raises
    ------
    TypeError
        If *dt_input* is neither a ``str`` nor a ``datetime``.
    ValueError
        If the string cannot be parsed as a recognisable date/time.

    See Also
    --------
    ensure_utc : Convert any datetime to a UTC-aware datetime.
    is_dt_naive : Check whether a datetime lacks timezone information.

    Examples
    --------
    >>> from datetime import datetime
    >>> dt = convert_to_datetime("2026-04-24T12:00:00")
    >>> isinstance(dt, datetime)
    True

    >>> dt_utc = convert_to_datetime("2026-04-24", ensure_utc=True)
    >>> dt_utc.tzinfo is not None
    True

    >>> convert_to_datetime(datetime(2026, 4, 24))
    datetime.datetime(2026, 4, 24, 0, 0)
    """
    if isinstance(dt_input, datetime):
        dt = dt_input
    elif isinstance(dt_input, str):
        try:
            dt = dateutil_parser.parse(dt_input)
        except (ValueError, OverflowError) as exc:
            raise ValueError(
                f"Invalid date format: {dt_input!r}. "
                "Ensure the string contains a recognisable date."
            ) from exc
    else:
        raise TypeError(
            f"Unsupported input type: {type(dt_input).__name__}. "
            "convert_to_datetime() accepts str or datetime only."
        )

    if ensure_utc:
        if is_dt_naive(dt):
            dt = dt.replace(tzinfo=timezone.utc)

    return dt


def is_dt_naive(dt: datetime) -> bool:
    """
    Return ``True`` if *dt* has no timezone information.

    A datetime is considered naive if its ``tzinfo`` attribute is ``None``
    or if ``dt.tzinfo.utcoffset(dt)`` returns ``None``.

    Parameters
    ----------
    dt : datetime
        The datetime object to inspect.

    Returns
    -------
    bool
        ``True`` if *dt* is naive (no timezone); ``False`` if it is
        timezone-aware.

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime` instance.

    See Also
    --------
    ensure_utc : Attach UTC timezone info to a naive datetime.
    convert_to_datetime : Parse strings into datetime objects.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> is_dt_naive(datetime(2026, 1, 1))
    True
    >>> is_dt_naive(datetime(2026, 1, 1, tzinfo=timezone.utc))
    False
    """
    if not isinstance(dt, datetime):
        raise TypeError(
            f"is_dt_naive() expected datetime, got {type(dt).__name__}."
        )
    return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None


def ensure_utc(dt: datetime) -> datetime:
    """
    Return a timezone-aware :class:`datetime` in UTC.

    If *dt* is naive, it is assumed to represent UTC and ``tzinfo`` is
    attached.  If *dt* is already timezone-aware, it is converted to UTC.

    Parameters
    ----------
    dt : datetime
        The datetime to make UTC-aware.  May be naive or aware.

    Returns
    -------
    datetime
        A timezone-aware datetime in UTC (``tzinfo == timezone.utc``).

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime` instance.

    See Also
    --------
    is_dt_naive : Check whether a datetime lacks timezone information.
    shift_tz_by_name : Convert a datetime to a different named timezone.

    Examples
    --------
    >>> from datetime import datetime
    >>> naive = datetime(2026, 4, 24, 12, 0, 0)
    >>> aware = ensure_utc(naive)
    >>> aware.tzinfo is not None
    True

    >>> from datetime import timezone
    >>> aware_bst = datetime(2026, 4, 24, 13, 0, 0,
    ...                      tzinfo=timezone(timedelta(hours=1)))
    >>> ensure_utc(aware_bst).hour
    12
    """
    _validate_datetime(dt)
    if is_dt_naive(dt):
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def start_of_day(dt: datetime) -> datetime:
    """
    Return *dt* with the time component set to midnight (``00:00:00.000000``).

    Preserves the ``tzinfo`` of the input datetime unchanged.

    Parameters
    ----------
    dt : datetime
        The reference datetime.  May be naive or timezone-aware.

    Returns
    -------
    datetime
        A copy of *dt* with ``hour=0``, ``minute=0``, ``second=0``,
        and ``microsecond=0``.

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime` instance.

    See Also
    --------
    end_of_day : Return the last microsecond of the same day.

    Examples
    --------
    >>> from datetime import datetime
    >>> dt = datetime(2026, 4, 24, 15, 30, 45, 123456)
    >>> start_of_day(dt)
    datetime.datetime(2026, 4, 24, 0, 0)
    """
    _validate_datetime(dt)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    """
    Return *dt* with the time component set to ``23:59:59.999999``.

    Preserves the ``tzinfo`` of the input datetime unchanged.

    Parameters
    ----------
    dt : datetime
        The reference datetime.  May be naive or timezone-aware.

    Returns
    -------
    datetime
        A copy of *dt* with ``hour=23``, ``minute=59``, ``second=59``,
        and ``microsecond=999999``.

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime` instance.

    See Also
    --------
    start_of_day : Return midnight of the same day.

    Examples
    --------
    >>> from datetime import datetime
    >>> dt = datetime(2026, 4, 24, 0, 0, 0)
    >>> eod = end_of_day(dt)
    >>> eod.hour, eod.minute, eod.second, eod.microsecond
    (23, 59, 59, 999999)
    """
    _validate_datetime(dt)
    return dt.replace(hour=23, minute=59, second=59, microsecond=999_999)


def shift_tz_by_name(dt: datetime, tz_name: str) -> datetime:
    """
    Convert *dt* to the named IANA timezone.

    The datetime is first anchored to UTC (via :func:`ensure_utc`), then
    converted to the target timezone, ensuring the absolute point-in-time
    is preserved regardless of the input timezone.

    Parameters
    ----------
    dt : datetime
        The datetime to convert.  May be naive (assumed UTC) or
        timezone-aware.
    tz_name : str
        A valid IANA timezone name string, e.g. ``'America/New_York'``,
        ``'Asia/Tehran'``, ``'Europe/London'``.

    Returns
    -------
    datetime
        A timezone-aware datetime in the target IANA timezone.

    Raises
    ------
    ImportError
        If ``timezonefinder`` or ``zoneinfo`` is not installed.
    TypeError
        If *dt* is not a :class:`datetime` instance, or *tz_name* is not
        a ``str``.
    ValueError
        If *tz_name* is an empty string.
    ZoneInfoNotFoundError
        If *tz_name* is not a recognised IANA timezone identifier.

    See Also
    --------
    point_to_tz_offset : Look up the IANA timezone name from a location.
    ensure_utc : Convert a datetime to UTC without changing timezone.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> utc_dt = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)
    >>> local = shift_tz_by_name(utc_dt, "America/New_York")
    >>> local.hour   # UTC-4 in April (EDT)
    8
    """
    if not _TZ_AVAILABLE:
        raise ImportError(
            "timezonefinder and/or zoneinfo are required for timezone helpers. "
            "Install them with: pip install timezonefinder"
        )
    _validate_datetime(dt)
    _validate_string(tz_name)
    dt_utc = ensure_utc(dt)
    try:
        return dt_utc.astimezone(ZoneInfo(tz_name))
    except ZoneInfoNotFoundError:
        raise ZoneInfoNotFoundError(
            f"Timezone {tz_name!r} not recognised. "
            "Use a valid IANA name such as 'Europe/London' or 'Asia/Tehran'."
        )


# ── Location resolver ────────────────────────────────────────────────────────

def _resolve_location(location: Point | str) -> Point:
    """Return a Shapely Point from either a Point or an H3 cell index string."""
    if isinstance(location, str):
        _validate_h3_index(location)
        from h3tools.geo import h3_to_point
        return h3_to_point(location)
    _validate_point(location)
    return location


# ── Timezone lookup ───────────────────────────────────────────────────────────

def point_to_tz_offset(pt: Point, eval_dt: datetime) -> tuple[str, float]:
    """
    Return the IANA timezone name and UTC offset (hours) for a location.

    The offset is DST-adjusted: it reflects the actual civil time offset
    in effect at *eval_dt*, not a fixed standard-time offset.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).
    eval_dt : datetime
        Reference datetime used to determine whether DST is in effect.
        Naive datetimes are assumed to be UTC.

    Returns
    -------
    tuple of (str, float)
        * ``iana_timezone_name`` : str — e.g. ``'Europe/London'``.
        * ``offset_in_hours`` : float — UTC offset in hours (e.g. ``1.0``
          for BST, ``-5.0`` for EST).

        For locations outside all mapped timezone polygons (e.g. open
        ocean), falls back to ``('UTC', 0.0)``.

    Raises
    ------
    ImportError
        If ``timezonefinder`` or ``zoneinfo`` is not installed.
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`, or *eval_dt* is
        not a :class:`datetime`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    shift_tz_by_name : Convert a datetime to a timezone name you already know.
    get_solar_data : Full solar event report (uses this function internally).

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> from datetime import datetime
    >>> tz_name, offset = point_to_tz_offset(
    ...     Point(-0.1278, 51.5074), datetime(2026, 4, 24)
    ... )
    >>> tz_name
    'Europe/London'
    >>> offset   # BST in April: UTC+1
    1.0
    """
    if not _TZ_AVAILABLE:
        raise ImportError(
            "timezonefinder is required. Install with: pip install timezonefinder"
        )
    _validate_point(pt)
    _validate_datetime(eval_dt)

    tz_name = _TF_INSTANCE.timezone_at(lng=pt.x, lat=pt.y)
    if not tz_name:
        return "UTC", 0.0

    local_dt = ensure_utc(eval_dt).astimezone(ZoneInfo(tz_name))
    offset_hours = local_dt.utcoffset().total_seconds() / 3600.0
    return tz_name, offset_hours


# ── Astro helpers ─────────────────────────────────────────────────────────────

def _astro_context(pt: Point, eval_dt: datetime):
    """Return (eval_dt_utc, tz_name, tz_offset, local_tz, target_date) for astro calculations."""
    eval_dt_utc = ensure_utc(eval_dt)
    tz_name, tz_offset = point_to_tz_offset(pt, eval_dt_utc)
    local_tz = ZoneInfo(tz_name)
    target_date = eval_dt_utc.date()
    return eval_dt_utc, tz_name, tz_offset, local_tz, target_date


# ── Solar data ────────────────────────────────────────────────────────────────

def get_solar_data(location: Point | str, eval_dt: datetime) -> dict:
    """
    Compute solar events and twilight phases for a location on a given date.

    Identifies the local IANA timezone for *location*, then calculates
    sunrise, sunset, and all three standard twilight phases (Civil, Nautical,
    Astronomical) using the ``astral`` library.  All times in the returned
    dictionary are localised to the geographic timezone of *location*.

    At extreme latitudes the sun may not cross some depression angles
    during polar day or polar night; those values are ``None``.

    Parameters
    ----------
    location : shapely.geometry.Point or str
        WGS-84 location, accepted as either a :class:`shapely.geometry.Point`
        (``x = longitude``, ``y = latitude``) or a valid H3 cell index
        string.  When an H3 index is supplied, the cell centre point is used.
    eval_dt : datetime
        Reference datetime.  Only the *date* component is used for solar
        calculations.  Naive datetimes are assumed to be UTC.

    Returns
    -------
    dict
        A dictionary with the following keys:

        ===========================  ========================================
        Key                          Value
        ===========================  ========================================
        ``'Locality Point'``         :class:`shapely.geometry.Point`
        ``'Evaluation Date'``        :class:`datetime.date`
        ``'Timezone Name'``          str — IANA timezone name
        ``'Timezone Offset (Hours)'``float — DST-adjusted UTC offset
        ``'Sunrise'``                timezone-aware :class:`datetime`
        ``'Sunset'``                 timezone-aware :class:`datetime`
        ``'Civil'``                  dict with keys ``'Dawn'`` and ``'Dusk'``
        ``'Nautical'``               dict with keys ``'Dawn'`` and ``'Dusk'``
        ``'Astronomical'``           dict with keys ``'Dawn'`` and ``'Dusk'``
        ===========================  ========================================

        Dawn/dusk values are timezone-aware :class:`datetime` objects, or
        ``None`` when the sun does not reach the required depression angle
        on *eval_dt*.

    Raises
    ------
    ImportError
        If ``astral`` or ``timezonefinder`` is not installed.
    TypeError
        If *location* is not a :class:`shapely.geometry.Point` or H3 index
        string, or *eval_dt* is not a :class:`datetime`.
    ValueError
        If *location* coordinates are outside WGS-84 bounds, or the H3
        index is invalid.

    Notes
    -----
    Elevation is fixed at 0 m (sea level) for the solar observer.

    See Also
    --------
    point_to_tz_offset : Return only the timezone name and UTC offset.
    get_lunar_data : Lunar phase and rise/set for the same location.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> from datetime import datetime
    >>> data = get_solar_data(Point(-0.1278, 51.5074), datetime(2026, 4, 24))
    >>> data["Timezone Name"]
    'Europe/London'
    >>> data = get_solar_data("871fb0962ffffff", datetime(2026, 4, 24))
    >>> isinstance(data["Sunrise"], datetime)
    True
    """
    if not _ASTRAL_AVAILABLE:
        raise ImportError(
            "astral is required for solar calculations. "
            "Install with: pip install astral"
        )
    if not _TZ_AVAILABLE:
        raise ImportError(
            "timezonefinder is required. Install with: pip install timezonefinder"
        )

    pt = _resolve_location(location)
    _validate_datetime(eval_dt)

    eval_dt_utc, tz_name, tz_offset, local_tz, target_date = _astro_context(pt, eval_dt)
    obs = Observer(latitude=pt.y, longitude=pt.x, elevation=0)

    def _safe_twilight(func, depression: float):
        """Return None if the sun never reaches the given depression angle."""
        try:
            return func(obs, date=target_date, depression=depression).astimezone(local_tz)
        except ValueError:
            return None

    s_raw = sun(obs, date=target_date)

    return {
        "Locality Point": pt,
        "Evaluation Date": target_date,
        "Timezone Name": tz_name,
        "Timezone Offset (Hours)": tz_offset,
        "Sunrise": s_raw["sunrise"].astimezone(local_tz),
        "Sunset": s_raw["sunset"].astimezone(local_tz),
        "Civil": {
            "Dawn": _safe_twilight(dawn, ASTRAL_DEPRESSION_ANGLES["Civil"]),
            "Dusk": _safe_twilight(dusk, ASTRAL_DEPRESSION_ANGLES["Civil"]),
        },
        "Nautical": {
            "Dawn": _safe_twilight(dawn, ASTRAL_DEPRESSION_ANGLES["Nautical"]),
            "Dusk": _safe_twilight(dusk, ASTRAL_DEPRESSION_ANGLES["Nautical"]),
        },
        "Astronomical": {
            "Dawn": _safe_twilight(dawn, ASTRAL_DEPRESSION_ANGLES["Astronomical"]),
            "Dusk": _safe_twilight(dusk, ASTRAL_DEPRESSION_ANGLES["Astronomical"]),
        },
    }


# ── Lunar data ────────────────────────────────────────────────────────────────

def get_lunar_data(location: Point | str, eval_dt: datetime) -> dict:
    """
    Return lunar phase, illumination, and rise/set times for a location.

    Phase and illumination are computed with ``astral`` (a core dependency).
    Moonrise and moonset require the optional ``ephem`` package; if it is not
    installed both values are ``None`` and the ``'Ephem Available'`` flag in
    the returned dict is ``False``.

    Parameters
    ----------
    location : shapely.geometry.Point or str
        WGS-84 location, accepted as either a :class:`shapely.geometry.Point`
        (``x = longitude``, ``y = latitude``) or a valid H3 cell index
        string.  When an H3 index is supplied, the cell centre point is used.
    eval_dt : datetime
        Reference datetime.  Only the *date* component is used for lunar
        calculations.  Naive datetimes are assumed to be UTC.

    Returns
    -------
    dict
        A dictionary with the following keys:

        ==========================  ===========================================
        Key                         Value
        ==========================  ===========================================
        ``'Locality Point'``        :class:`shapely.geometry.Point`
        ``'Evaluation Date'``       :class:`datetime.date`
        ``'Timezone Name'``         str — IANA timezone name
        ``'Timezone Offset (Hours)'``float — DST-adjusted UTC offset
        ``'Phase Number'``          float in [0, 27] — 0 = New Moon,
                                    ~7 = First Quarter, ~14 = Full Moon,
                                    ~21 = Last Quarter
        ``'Phase Name'``            str — e.g. ``'Waxing Gibbous'``
        ``'Illumination (%)'``      float — approximate disc illumination
                                    percentage [0, 100]
        ``'Moonrise'``              timezone-aware :class:`datetime`, or
                                    ``None`` if ephem unavailable or moon
                                    does not rise on *eval_dt*
        ``'Moonset'``               timezone-aware :class:`datetime`, or
                                    ``None`` if ephem unavailable or moon
                                    does not set on *eval_dt*
        ``'Ephem Available'``       bool — ``True`` when moonrise/moonset
                                    were computed via ``ephem``
        ==========================  ===========================================

    Raises
    ------
    ImportError
        If ``astral`` is not installed (phase and illumination require it).
        Install with ``pip install astral``.
    TypeError
        If *location* is not a :class:`shapely.geometry.Point` or H3 index
        string, or *eval_dt* is not a :class:`datetime`.
    ValueError
        If *location* coordinates are outside WGS-84 bounds, or the H3
        index is invalid.

    Notes
    -----
    Phase number is taken from :func:`astral.moon.phase`, which returns a
    value on an internal [0, 27] scale rather than the true synodic period
    (29.53 days).  Illumination is approximated as
    ``(1 − cos(2π × phase / 27)) / 2 × 100 %``, which is exact at the
    four named phases and within ~3 % elsewhere.

    For moonrise and moonset at extreme latitudes (polar day/night), the
    moon may never rise or never set.  In those cases the value is ``None``.

    Install ``ephem`` to enable rise/set times::

        pip install ephem
        # or, if you installed h3tools with extras:
        pip install "h3tools[lunar]"

    See Also
    --------
    get_solar_data : Analogous function for solar events.
    point_to_tz_offset : Return only timezone name and UTC offset.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> from datetime import datetime
    >>> data = get_lunar_data(Point(-0.1278, 51.5074), datetime(2026, 4, 24))
    >>> data["Evaluation Date"].isoformat()
    '2026-04-24'
    >>> 0 <= data["Phase Number"] <= 27
    True
    >>> 0.0 <= data["Illumination (%)"] <= 100.0
    True
    >>> isinstance(data["Phase Name"], str)
    True
    """
    if not _ASTRAL_AVAILABLE:
        raise ImportError(
            "astral is required for lunar calculations. "
            "Install with: pip install astral"
        )
    if not _TZ_AVAILABLE:
        raise ImportError(
            "timezonefinder is required. Install with: pip install timezonefinder"
        )

    pt = _resolve_location(location)
    _validate_datetime(eval_dt)

    eval_dt_utc, tz_name, tz_offset, local_tz, target_date = _astro_context(pt, eval_dt)

    phase_day = _astral_moon_phase(target_date)
    illumination = (1.0 - math.cos(2.0 * math.pi * phase_day / _ASTRAL_LUNAR_SCALE)) / 2.0 * 100.0

    moonrise = moonset = None
    if _EPHEM_AVAILABLE:
        moonrise, moonset = _ephem_moon_riseset(pt, target_date, local_tz)

    return {
        "Locality Point": pt,
        "Evaluation Date": target_date,
        "Timezone Name": tz_name,
        "Timezone Offset (Hours)": tz_offset,
        "Phase Number": round(phase_day, 2),
        "Phase Name": _lunar_phase_name(phase_day),
        "Illumination (%)": round(illumination, 1),
        "Moonrise": moonrise,
        "Moonset": moonset,
        "Ephem Available": _EPHEM_AVAILABLE,
    }
