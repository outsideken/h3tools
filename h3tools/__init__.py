"""
h3tools  v0.1.0
================
H3 Geospatial Helper Library — quick reference.

A collection of utility functions for working with the Uber H3 hierarchical
hexagonal grid system, compatible with h3-py v3.x and v4.x.  Integrates
cleanly with shapely, matplotlib, and pandas.

Quick start
-----------
>>> from shapely.geometry import Point
>>> from h3tools import point_to_h3, h3_to_polygon, get_solar_data
>>> from datetime import datetime
>>> pt = Point(-0.1278, 51.5074)            # London, Trafalgar Square
>>> cell = point_to_h3(pt, h3_resolution=9)
>>> poly  = h3_to_polygon(cell)
>>> solar = get_solar_data(pt, datetime(2026, 4, 24))
>>> solar["Timezone Name"]
'Europe/London'

─────────────────────────────────────────────────────────────────────────────
CORE  (h3tools.core)
─────────────────────────────────────────────────────────────────────────────
is_h3_valid(h3_index)
    Return True if h3_index is a valid H3 cell string.
is_h3_pentagon(h3_index)
    Return True if the cell is one of the 12 pentagon cells at its resolution.
get_h3_resolution(h3_index)
    Return the resolution (0–15) of a cell.
get_h3_cell_area(h3_index)
    Return the average area in km² for the cell's resolution.
get_h3_cell_edge_length(h3_index)
    Return the average edge length in km for the cell's resolution.
get_cluster_area_km2(hexagons)
    Return the total area in km² of a cluster of H3 cells.

─────────────────────────────────────────────────────────────────────────────
GEO  (h3tools.geo)  —  coordinate → H3
─────────────────────────────────────────────────────────────────────────────
point_to_h3(point, h3_resolution)
    Shapely Point → H3 cell index.
latlon_to_h3(latlon, h3_resolution)
    (lat, lon) tuple → H3 cell index.
latlon_to_point(latlon)
    (lat, lon) tuple → Shapely Point.
mgrs_to_h3(mgrs_str, h3_resolution)
    MGRS string → H3 cell index.
mgrs_to_point(mgrs_str)
    MGRS string → Shapely Point.
dms_to_h3(dms_str, h3_resolution)
    DMS coordinate string → H3 cell index.
dms_to_point(dms_str)
    DMS coordinate string → Shapely Point.
ddm_to_point(ddm_str)
    DDM coordinate string → Shapely Point.
ddm_to_h3(ddm_str, h3_resolution)
    DDM coordinate string → H3 cell index.
coordinate_to_h3(coord_input, h3_resolution)
    Auto-detect coordinate format and return H3 cell index.
coordinate_to_point(coord_input)
    Auto-detect coordinate format and return Shapely Point.
linestring_to_h3(linestring, h3_resolution)
    Shapely LineString / MultiLineString → set of H3 cell indices.
polygon_to_h3(polygon, h3_resolution)
    Shapely Polygon → set of H3 cell indices.
multipolygon_to_h3(multipolygon, h3_resolution)
    Shapely MultiPolygon → set of H3 cell indices.
geometry_to_h3(geometry, h3_resolution)
    Universal dispatcher — Point, Polygon, GeoJSON dict, WKT, or coordinate
    string → set of H3 cell indices (or a single index for point inputs).

GEO  —  H3 → geometry / coordinates
─────────────────────────────────────────────────────────────────────────────
h3_to_point(h3_index)
    H3 cell → Shapely Point at the cell centre.
h3_to_polygon(h3_index)
    H3 cell → Shapely Polygon of the cell boundary.
h3_to_dms(h3_index)
    H3 cell → (lat_dms, lon_dms) string pair, e.g. ('51°30′26.42"N', ...).
h3_to_ddm(h3_index)
    H3 cell → (lat_ddm, lon_ddm) string pair, e.g. ('51°30.440′N', ...).
h3_to_mgrs(h3_index, precision=None)
    H3 cell → MGRS coordinate string for the cell centre.
dissolve_h3_cells(cells)
    Merge a collection of H3 cells into a single Shapely Polygon/MultiPolygon.
points_to_h3_path(points, h3_resolution)
    Convert an ordered sequence of Shapely Points to the H3 cells they pass
    through.

GEO  —  GeoJSON I/O
─────────────────────────────────────────────────────────────────────────────
cells_to_geojson(cells)
    H3 cell index or iterable of indices → GeoJSON FeatureCollection dict.
    Each Feature carries an "h3_index" property.
geojson_to_cells(geojson, resolution)
    GeoJSON dict or JSON string (Polygon, MultiPolygon, Feature, or
    FeatureCollection) → set of H3 cell indices at the given resolution.

─────────────────────────────────────────────────────────────────────────────
ANALYTICS  (h3tools.analytics)  —  hierarchy & neighbours
─────────────────────────────────────────────────────────────────────────────
get_h3_parent(h3_index, parent_resolution)
    Return the parent cell at a coarser resolution.
get_h3_children(h3_index, child_resolution)
    Return all child cells at a finer resolution.
get_h3_siblings(h3_index)
    Return all cells sharing the same parent (i.e. at the same resolution).
get_h3_family(h3_index)
    Return the parent and all sibling cells together.
get_h3_neighbors(h3_index, k=1)
    Return the k-ring of cells within k grid steps (excludes the centre).
find_h3_contiguous_neighbors(cells)
    Cluster a set of H3 cells into spatially contiguous groups (list of sets).

ANALYTICS  —  paths & distance
─────────────────────────────────────────────────────────────────────────────
get_h3_path(start_h3, end_h3)
    Return the ordered list of cells on the grid path between two cells.
    Automatically routes around pentagon cells when necessary.
get_h3_nearby(cells, target_h3, radius)
    Filter a collection of H3 cells to those within radius grid steps of
    target_h3.
get_h3_distance(h3_index_a, h3_index_b, unit="steps")
    Grid-step distance between two cells (unit="steps") or approximate
    great-circle distance in kilometres (unit="km").

ANALYTICS  —  event / count analysis
─────────────────────────────────────────────────────────────────────────────
find_h3_hotspots(cell_counts, threshold=1.0, method="zscore")
    Return cells whose counts are statistically elevated using z-score or
    MAD scoring.  threshold controls sensitivity.
get_h3_weighted_centroid(cell_counts)
    Return the event-weighted geographic centroid (Shapely Point) of a
    cell-count distribution.
get_h3_delta(snapshot_a, snapshot_b)
    Compare two cell-count dicts; return gained, lost, stable cells and
    net_change.
get_h3_stats(cell_counts)
    Return descriptive statistics for a cell-count distribution:
    total_events, unique_cells, mean, median, std, min, max, p25, p75, p95,
    and top_cells (top 5 by count).
compact_h3_cells(cells)
    Compress a set of H3 cells to the coarsest mixed-resolution representation.
    Seven sibling cells are replaced by their parent wherever possible.
uncompact_h3_cells(cells, resolution)
    Expand a compact mixed-resolution cell set to a uniform target resolution.

─────────────────────────────────────────────────────────────────────────────
VIZ  (h3tools.viz)
─────────────────────────────────────────────────────────────────────────────
plot_hex(ax, cells, config=None)
    Draw H3 cells as filled polygons on a Matplotlib axis.
plot_hex_heatmap(ax, cell_counts, config=None)
    Draw H3 cells colour-mapped to numeric values (heatmap).
format_plot(ax)
    Apply minimal, clean spine/tick styling to a Matplotlib axis.
plot_h3_choropleth(ax, cell_counts, cmap="YlOrRd", legend=True, ...)
    Plot a publication-ready choropleth of H3 cell counts on a Matplotlib
    axis.  Requires geopandas (soft dependency).

─────────────────────────────────────────────────────────────────────────────
TEMPORAL  (h3tools.temporal)
─────────────────────────────────────────────────────────────────────────────
convert_to_datetime(value)
    Parse an ISO-8601 string to a datetime, or pass a datetime through.
ensure_utc(dt)
    Make a datetime timezone-aware in UTC (localises naive datetimes).
is_dt_naive(dt)
    Return True if the datetime has no timezone information.
start_of_day(dt)
    Truncate a datetime to midnight (00:00:00.000000) in its timezone.
end_of_day(dt)
    Set a datetime to the last microsecond of the day (23:59:59.999999).
shift_tz_by_name(dt, tz_name)
    Convert a datetime to a named IANA timezone.
point_to_tz_offset(point)
    Return (tz_name, utc_offset_hours) for a Shapely Point or H3 cell.
get_solar_data(location, date)
    Return a dict of solar events (sunrise, sunset, all three twilight
    phases, day length) and timezone info for a location on a given date.
    location may be a Shapely Point or H3 cell index.
get_lunar_data(location, date)
    Return moon phase name, phase number (0–27), illumination percentage,
    and moonrise/moonset times for a location on a given date.

─────────────────────────────────────────────────────────────────────────────
DATAFRAME  (h3tools.dataframe)  —  pandas integration (soft dependency)
─────────────────────────────────────────────────────────────────────────────
add_h3_column(df, geometry_col, resolution, h3_col="h3_index")
    Add an H3 cell index column derived from a Shapely Point geometry column.
    Returns a new DataFrame; the original is not modified.
h3_count(df, h3_col="h3_index")
    Return a cell→count Series from an H3 index column, sorted most to least
    frequent.
h3_stats_df(cell_counts)
    Wrap get_h3_stats() and return scalar statistics as a single-row DataFrame.
    Accepts a dict, Counter, or Series directly.  top_cells is omitted (call
    get_h3_stats() directly to access it).
h3_to_geodataframe(cells, cell_counts=None, crs="EPSG:4326")
    Convert H3 cells to a GeoPandas GeoDataFrame (requires geopandas).
    Each cell becomes a row with h3_index and Polygon geometry columns.
    Optionally attach a count column via cell_counts.
h3_timeseries(df, h3_col="h3_index", time_col="timestamp", freq="D", ...)
    Aggregate event counts (or values) by H3 cell and time period.  Returns
    a long-format DataFrame with columns: h3_index, period, value.
"""

__version__ = "0.1.0"
__author__  = "KChadwick"

# ── Core ──────────────────────────────────────────────────────────────────────
from h3tools.core import (
    is_h3_valid,
    is_h3_pentagon,
    get_h3_resolution,
    get_h3_cell_area,
    get_h3_cell_edge_length,
    get_cluster_area_km2,
)

# ── Geo ───────────────────────────────────────────────────────────────────────
from h3tools.geo import (
    point_to_h3,
    latlon_to_h3,
    latlon_to_point,
    coordinate_to_h3,
    coordinate_to_point,
    mgrs_to_h3,
    mgrs_to_point,
    dms_to_h3,
    dms_to_point,
    ddm_to_point,
    ddm_to_h3,
    linestring_to_h3,
    polygon_to_h3,
    multipolygon_to_h3,
    geometry_to_h3,
    h3_to_point,
    h3_to_polygon,
    h3_to_dms,
    h3_to_ddm,
    h3_to_mgrs,
    dissolve_h3_cells,
    points_to_h3_path,
    cells_to_geojson,
    geojson_to_cells,
)

# ── Analytics ─────────────────────────────────────────────────────────────────
from h3tools.analytics import (
    get_h3_parent,
    get_h3_children,
    get_h3_siblings,
    get_h3_family,
    get_h3_neighbors,
    find_h3_contiguous_neighbors,
    get_h3_path,
    get_h3_nearby,
    get_h3_distance,
    find_h3_hotspots,
    get_h3_weighted_centroid,
    get_h3_delta,
    get_h3_stats,
    compact_h3_cells,
    uncompact_h3_cells,
)

# ── Viz ───────────────────────────────────────────────────────────────────────
from h3tools.viz import (
    plot_hex,
    plot_hex_heatmap,
    format_plot,
    plot_h3_choropleth,
)

# ── Temporal ──────────────────────────────────────────────────────────────────
from h3tools.temporal import (
    convert_to_datetime,
    point_to_tz_offset,
    get_solar_data,
    get_lunar_data,
    ensure_utc,
    is_dt_naive,
    start_of_day,
    end_of_day,
    shift_tz_by_name,
)

# ── DataFrame ─────────────────────────────────────────────────────────────────
from h3tools.dataframe import (
    add_h3_column,
    h3_count,
    h3_stats_df,
    h3_to_geodataframe,
    h3_timeseries,
)

__all__ = [
    # core
    "is_h3_valid", "is_h3_pentagon",
    "get_h3_resolution", "get_h3_cell_area",
    "get_h3_cell_edge_length", "get_cluster_area_km2",
    # geo
    "point_to_h3", "latlon_to_h3", "latlon_to_point",
    "coordinate_to_h3", "coordinate_to_point",
    "mgrs_to_h3", "mgrs_to_point",
    "dms_to_h3", "dms_to_point", "ddm_to_point", "ddm_to_h3",
    "linestring_to_h3", "polygon_to_h3", "multipolygon_to_h3",
    "geometry_to_h3",
    "h3_to_point", "h3_to_polygon",
    "h3_to_dms", "h3_to_ddm",
    "h3_to_mgrs", "dissolve_h3_cells",
    "points_to_h3_path",
    "cells_to_geojson", "geojson_to_cells",
    # analytics
    "get_h3_parent", "get_h3_children", "get_h3_siblings",
    "get_h3_family", "get_h3_neighbors",
    "find_h3_contiguous_neighbors", "get_h3_path", "get_h3_nearby",
    "get_h3_distance", "find_h3_hotspots",
    "get_h3_weighted_centroid", "get_h3_delta", "get_h3_stats",
    "compact_h3_cells", "uncompact_h3_cells",
    # viz
    "plot_hex", "plot_hex_heatmap", "format_plot", "plot_h3_choropleth",
    # temporal
    "convert_to_datetime", "point_to_tz_offset", "get_solar_data",
    "get_lunar_data",
    "ensure_utc", "is_dt_naive", "start_of_day", "end_of_day",
    "shift_tz_by_name",
    # dataframe
    "add_h3_column", "h3_count", "h3_stats_df", "h3_to_geodataframe",
    "h3_timeseries",
]
