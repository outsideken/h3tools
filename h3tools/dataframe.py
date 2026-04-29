"""
h3tools.dataframe
==================
Pandas DataFrame integration for h3tools.

Provides functions for adding H3 cell columns to DataFrames, computing
cell-count Series, summarising distributions as DataFrames, converting
cell sets to GeoPandas GeoDataFrames, and building time-series aggregations
by H3 cell.

Pandas is a soft dependency — functions in this module raise
:class:`ImportError` with an installation hint if it is unavailable.
GeoPandas is an additional soft dependency required only by
:func:`h3_to_geodataframe`.

Functions
---------
add_h3_column
    Add an H3 cell index column derived from a Point geometry column.
h3_count
    Return a cell→count Series from an H3 column.
h3_stats_df
    Return descriptive statistics for a cell-count distribution as a
    single-row DataFrame.
h3_to_geodataframe
    Convert a collection of H3 cells to a GeoPandas GeoDataFrame.
h3_timeseries
    Aggregate event counts by H3 cell and time period.
"""

from __future__ import annotations

__all__ = [
    "add_h3_column",
    "h3_count",
    "h3_stats_df",
    "h3_to_geodataframe",
    "h3_timeseries",
]

import h3 as _h3
import shapely as _shapely

from h3tools._validators import _validate_h3_resolution
from h3tools.analytics import get_h3_stats
from h3tools.core import IS_H3_V4


def _require_pandas():
    try:
        import pandas as pd
        return pd
    except ImportError as exc:
        raise ImportError(
            "h3tools.dataframe requires pandas.  Install it with: pip install pandas"
        ) from exc


def add_h3_column(
    df,
    geometry_col: str,
    resolution: int,
    h3_col: str = "h3_index",
):
    """
    Add an H3 cell index column to a DataFrame.

    For each row, converts the Shapely ``Point`` in *geometry_col* to an H3
    cell index at *resolution* and stores the result in a new column named
    *h3_col*.  The original DataFrame is not modified; a new DataFrame is
    returned.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.  Must contain a column of Shapely ``Point`` objects.
    geometry_col : str
        Name of the column containing Shapely ``Point`` geometries.
    resolution : int
        H3 resolution (0–15) to use for the cell conversion.
    h3_col : str, optional
        Name of the new H3 index column.  Defaults to ``"h3_index"``.  If
        a column with this name already exists it will be overwritten.

    Returns
    -------
    pandas.DataFrame
        A new DataFrame identical to *df* with the *h3_col* column added (or
        replaced).

    Raises
    ------
    ImportError
        If pandas is not installed.
    ValueError
        If *geometry_col* is not present in *df*, or if *resolution* is not
        in the range [0, 15].
    ValueError
        If any value in *geometry_col* is not a valid Shapely ``Point``,
        or if the column contains null geometries.

    Notes
    -----
    Coordinate extraction uses :func:`shapely.get_coordinates`, a vectorized
    C call that reads all coordinates in one pass before the H3 lookup loop.
    This is significantly faster than a row-wise ``.apply()`` for large
    DataFrames.

    Examples
    --------
    >>> import pandas as pd
    >>> from shapely.geometry import Point
    >>> from h3tools.dataframe import add_h3_column
    >>> df = pd.DataFrame({"geometry": [Point(-0.1278, 51.5074),
    ...                                  Point(2.3522, 48.8566)]})
    >>> result = add_h3_column(df, geometry_col="geometry", resolution=9)
    >>> "h3_index" in result.columns
    True
    >>> len(result) == len(df)
    True
    """
    _require_pandas()
    _validate_h3_resolution(resolution)

    if geometry_col not in df.columns:
        raise ValueError(
            f"Column {geometry_col!r} not found in DataFrame. "
            f"Available columns: {list(df.columns)}"
        )

    coords = _shapely.get_coordinates(df[geometry_col].values)  # (n, 2): lon, lat
    if IS_H3_V4:
        cells = [_h3.latlng_to_cell(float(lat), float(lon), resolution)
                 for lon, lat in coords]
    else:
        cells = [_h3.geo_to_h3(float(lat), float(lon), resolution)
                 for lon, lat in coords]

    return df.assign(**{h3_col: cells})


def h3_count(df, h3_col: str = "h3_index"):
    """
    Return a cell→count Series from an H3 index column.

    Counts the occurrences of each distinct H3 cell index in *h3_col* and
    returns the result as a :class:`pandas.Series` sorted from most to least
    frequent.  This is a thin convenience wrapper around
    :meth:`pandas.Series.value_counts`.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing an H3 index column.
    h3_col : str, optional
        Name of the column containing H3 cell indices.  Defaults to
        ``"h3_index"``.

    Returns
    -------
    pandas.Series
        Series indexed by H3 cell index, with integer count values, sorted
        in descending order.  The Series name is set to *h3_col*.

    Raises
    ------
    ImportError
        If pandas is not installed.
    ValueError
        If *h3_col* is not present in *df*.

    Examples
    --------
    >>> import pandas as pd
    >>> from shapely.geometry import Point
    >>> from h3tools.dataframe import add_h3_column, h3_count
    >>> df = pd.DataFrame({"geometry": [Point(-0.1278, 51.5074)] * 3 +
    ...                                 [Point(2.3522, 48.8566)]})
    >>> df = add_h3_column(df, "geometry", resolution=9)
    >>> counts = h3_count(df)
    >>> counts.iloc[0]   # most frequent cell
    3
    """
    _require_pandas()

    if h3_col not in df.columns:
        raise ValueError(
            f"Column {h3_col!r} not found in DataFrame. "
            f"Available columns: {list(df.columns)}"
        )

    return df[h3_col].value_counts()


def h3_stats_df(cell_counts):
    """
    Return descriptive statistics for a cell-count distribution as a DataFrame.

    Wraps :func:`h3tools.analytics.get_h3_stats` and returns the scalar
    statistics as a single-row :class:`pandas.DataFrame`, convenient for
    display or concatenation with other summary rows.

    The ``"top_cells"`` key returned by :func:`~h3tools.analytics.get_h3_stats`
    is omitted because a dict value does not fit cleanly into a tabular column.
    Call :func:`~h3tools.analytics.get_h3_stats` directly to access it.

    Parameters
    ----------
    cell_counts : dict[str, int | float] or pandas.Series
        Mapping of H3 cell index → count.  Accepted types include plain
        :class:`dict`, :class:`collections.Counter`, and a
        :class:`pandas.Series` (e.g. the direct output of :func:`h3_count`).
        Series objects are converted automatically; calling ``.to_dict()``
        is not required.

    Returns
    -------
    pandas.DataFrame
        Single-row DataFrame with the following columns:

        ``total_events``, ``unique_cells``, ``mean``, ``median``, ``std``,
        ``min``, ``max``, ``p25``, ``p75``, ``p95``.

    Raises
    ------
    ImportError
        If pandas is not installed.
    ValueError
        If *cell_counts* is empty, contains an invalid H3 cell index, or
        contains a negative count (propagated from
        :func:`~h3tools.analytics.get_h3_stats`).
    TypeError
        If *cell_counts* is not a dict-like mapping.

    See Also
    --------
    get_h3_stats : Returns the full result including ``top_cells``.
    h3_count : Produce a cell-count Series from a DataFrame column.

    Examples
    --------
    >>> from collections import Counter
    >>> from h3tools.dataframe import h3_stats_df
    >>> counts = Counter({"89195da49b7ffff": 10, "89195da49b3ffff": 5})
    >>> stats = h3_stats_df(counts)
    >>> int(stats["total_events"].iloc[0])
    15
    >>> list(stats.columns)   # doctest: +NORMALIZE_WHITESPACE
    ['total_events', 'unique_cells', 'mean', 'median', 'std', 'min', 'max',
     'p25', 'p75', 'p95']
    """
    pd = _require_pandas()

    if hasattr(cell_counts, "to_dict"):
        cell_counts = cell_counts.to_dict()

    stats = get_h3_stats(cell_counts)
    row = {k: v for k, v in stats.items() if k != "top_cells"}
    return pd.DataFrame([row])


def h3_to_geodataframe(
    cells,
    cell_counts: dict | None = None,
    crs: str = "EPSG:4326",
):
    """
    Convert a collection of H3 cells to a GeoPandas GeoDataFrame.

    Each cell becomes a row with a ``Polygon`` geometry (the cell boundary)
    and an ``h3_index`` column.  Optionally, a count or weight value can be
    attached to each cell by supplying *cell_counts*.

    Parameters
    ----------
    cells : str or iterable of str
        One or more H3 cell index strings.  Duplicates are silently removed.
    cell_counts : dict[str, int | float], optional
        Mapping of H3 cell index → count or weight.  When provided, a
        ``"count"`` column is added to the GeoDataFrame.  Cells present in
        *cells* but absent from *cell_counts* receive a count of ``0``.
    crs : str, optional
        Coordinate reference system for the GeoDataFrame.  Defaults to
        ``"EPSG:4326"`` (WGS84 geographic coordinates).

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with columns:

        ``"h3_index"``
            H3 cell index string.
        ``"geometry"``
            Shapely ``Polygon`` of the cell boundary.
        ``"count"`` *(only when cell_counts is supplied)*
            Numeric count or weight for the cell.

    Raises
    ------
    ImportError
        If geopandas is not installed.
    ValueError
        If *cells* is empty or any cell index is invalid.

    Notes
    -----
    The returned GeoDataFrame is compatible with any tool that accepts
    GeoPandas input, including QGIS (via file export), Folium, Matplotlib,
    and the GeoPandas ``.plot()`` method.

    See Also
    --------
    cells_to_geojson : Export cells as a GeoJSON dict instead.
    dissolve_h3_cells : Merge cells into a single Shapely geometry.

    Examples
    --------
    >>> from h3tools.dataframe import h3_to_geodataframe
    >>> cells = ["89195da49b7ffff", "89195da49b3ffff"]
    >>> gdf = h3_to_geodataframe(cells)
    >>> list(gdf.columns)
    ['h3_index', 'geometry']
    >>> len(gdf)
    2

    >>> counts = {"89195da49b7ffff": 10, "89195da49b3ffff": 5}
    >>> gdf = h3_to_geodataframe(cells, cell_counts=counts)
    >>> list(gdf.columns)
    ['h3_index', 'geometry', 'count']
    """
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise ImportError(
            "h3_to_geodataframe requires geopandas.  "
            "Install it with: pip install geopandas"
        ) from exc

    from h3tools._validators import _validate_h3_index
    from h3tools.geo import h3_to_polygon

    if isinstance(cells, str):
        cells = [cells]
    else:
        cells = list(dict.fromkeys(cells))   # deduplicate, preserve order

    if not cells:
        raise ValueError("h3_to_geodataframe() requires at least one cell.")

    for cell in cells:
        _validate_h3_index(cell)

    geometries = [h3_to_polygon(cell) for cell in cells]
    data = {"h3_index": cells, "geometry": geometries}

    if cell_counts is not None:
        data["count"] = [cell_counts.get(cell, 0) for cell in cells]

    return gpd.GeoDataFrame(data, geometry="geometry", crs=crs)


def h3_timeseries(
    df,
    h3_col: str = "h3_index",
    time_col: str = "timestamp",
    freq: str = "D",
    value_col: str | None = None,
    agg: str = "count",
):
    """
    Aggregate event counts (or values) by H3 cell and time period.

    Groups *df* by H3 cell and a time-based period derived from *time_col*
    at the requested *freq* frequency, returning a long-format DataFrame
    with one row per (cell, period) combination.  This is the foundation
    for pattern-of-life analysis, trend detection, and animated choropleth
    workflows.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.  Must contain an H3 index column and a datetime
        column.
    h3_col : str, optional
        Name of the H3 cell index column.  Default is ``"h3_index"``.
    time_col : str, optional
        Name of the datetime column.  Values are coerced to
        :class:`pandas.Timestamp` via ``pd.to_datetime`` if they are not
        already datetime-typed.  Default is ``"timestamp"``.
    freq : str, optional
        Pandas offset alias controlling the time bucket size.  Common
        values:

        * ``"h"``  — hourly  (use for AIS / CTD data)
        * ``"D"``  — daily   *(default)*
        * ``"W"``  — weekly
        * ``"ME"`` — month end
        * ``"YE"`` — year end

        Any valid :func:`pandas.Grouper` frequency string is accepted.
    value_col : str, optional
        Column to aggregate instead of counting rows.  When ``None``
        (default), rows are counted.  When provided, the column is
        aggregated using *agg*.
    agg : str, optional
        Aggregation function applied to *value_col* when it is provided.
        Ignored when *value_col* is ``None``.  Common values:
        ``"sum"``, ``"mean"``, ``"max"``, ``"min"``.  Default is
        ``"count"``.

    Returns
    -------
    pandas.DataFrame
        Long-format DataFrame with three columns:

        ``h3_index``
            H3 cell index string.
        ``period``
            Start of the time bucket as a :class:`pandas.Timestamp`.
        ``value``
            Aggregated count or value for that cell in that period.

    Raises
    ------
    ImportError
        If pandas is not installed.
    ValueError
        If *h3_col* or *time_col* are not present in *df*, or if
        *value_col* is provided but not present in *df*.

    Notes
    -----
    The returned DataFrame is in long (tidy) format, which is the most
    flexible for downstream use.  To pivot to wide format (cells as columns,
    periods as rows):

    .. code-block:: python

        ts.pivot(index="period", columns="h3_index", values="value")

    See Also
    --------
    add_h3_column : Add an H3 column to a DataFrame before calling this.
    h3_count : Single-period cell counts without time dimension.

    Examples
    --------
    >>> import pandas as pd
    >>> from shapely.geometry import Point
    >>> from h3tools.dataframe import add_h3_column, h3_timeseries
    >>> df = pd.DataFrame({
    ...     "geometry":  [Point(-0.1278, 51.5074)] * 4,
    ...     "timestamp": pd.date_range("2026-01-01", periods=4, freq="D"),
    ... })
    >>> df = add_h3_column(df, "geometry", resolution=9)
    >>> ts = h3_timeseries(df, freq="D")
    >>> list(ts.columns)
    ['h3_index', 'period', 'value']
    >>> len(ts) == 4
    True
    """
    pd = _require_pandas()

    for col in (h3_col, time_col):
        if col not in df.columns:
            raise ValueError(
                f"Column {col!r} not found in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )
    if value_col is not None and value_col not in df.columns:
        raise ValueError(
            f"value_col {value_col!r} not found in DataFrame. "
            f"Available columns: {list(df.columns)}"
        )

    work = df.copy()
    work[time_col] = pd.to_datetime(work[time_col])

    grouper = [h3_col, pd.Grouper(key=time_col, freq=freq)]

    if value_col is None:
        result = (
            work.groupby(grouper)
            .size()
            .reset_index(name="value")
        )
    else:
        result = (
            work.groupby(grouper)[value_col]
            .agg(agg)
            .reset_index(name="value")
        )

    result = result.rename(columns={time_col: "period"})
    return result[[h3_col, "period", "value"]].rename(
        columns={h3_col: "h3_index"}
    )
