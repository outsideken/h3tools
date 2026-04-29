# Changelog

All notable changes to h3tools will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
h3tools uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-04-26

Initial release.

### Added

#### `h3tools.core` — cell properties
- `is_h3_valid` — validate an H3 cell index string.
- `is_h3_pentagon` — identify pentagon cells (12 per resolution).
- `get_h3_resolution` — return the resolution (0–15) of a cell.
- `get_h3_cell_area` — average area in km² for a cell's resolution.
- `get_h3_cell_edge_length` — average edge length in km for a cell's resolution.
- `IS_H3_V4` module flag for h3-py v3/v4 API branching.

#### `h3tools.geo` — coordinate and geometry conversions
- `point_to_h3` — Shapely Point → H3 cell index.
- `latlon_to_h3` — (lat, lon) tuple → H3 cell index.
- `latlon_to_point` — (lat, lon) tuple → Shapely Point.
- `mgrs_to_h3` — MGRS string → H3 cell index.
- `mgrs_to_point` — MGRS string → Shapely Point.
- `dms_to_h3` — DMS coordinate string → H3 cell index.
- `dms_to_point` — DMS coordinate string → Shapely Point.
- `ddm_to_point` — DDM coordinate string → Shapely Point.
- `coordinate_to_h3` — auto-detect coordinate format → H3 cell index.
- `coordinate_to_point` — auto-detect coordinate format → Shapely Point.
- `linestring_to_h3` — Shapely LineString / MultiLineString → set of H3 cells.
- `polygon_to_h3` — Shapely Polygon → set of H3 cells.
- `multipolygon_to_h3` — Shapely MultiPolygon → set of H3 cells.
- `geometry_to_h3` — universal dispatcher accepting Point, Polygon, GeoJSON,
  WKT, MGRS, DMS, DDM, and (lat, lon) inputs.
- `h3_to_point` — H3 cell → Shapely Point at the cell centre.
- `h3_to_polygon` — H3 cell → Shapely Polygon of the cell boundary.
- `h3_to_dms` — H3 cell → (lat, lon) DMS string pair.
- `h3_to_ddm` — H3 cell → (lat, lon) DDM string pair.
- `h3_to_mgrs` — H3 cell → MGRS coordinate string.
- `dissolve_h3_cells` — merge a collection of cells into a single Shapely
  Polygon or MultiPolygon via `shapely.ops.unary_union`.
- `points_to_h3_path` — ordered sequence of Points → H3 cells traversed.
- `cells_to_geojson` — H3 cells → GeoJSON FeatureCollection dict, with each
  Feature carrying an `h3_index` property.
- `geojson_to_cells` — GeoJSON Polygon, MultiPolygon, Feature, or
  FeatureCollection → set of H3 cells at a given resolution.

#### `h3tools.analytics` — spatial analytics
- `get_h3_parent` — return the parent cell at a coarser resolution.
- `get_h3_children` — return all child cells at a finer resolution.
- `get_h3_siblings` — return all cells sharing the same parent.
- `get_h3_family` — return the parent and all sibling cells together.
- `get_h3_neighbors` — return the k-ring of cells within k grid steps.
- `find_h3_contiguous_neighbors` — cluster cells into spatially contiguous
  groups.
- `get_h3_path` — ordered grid path between two cells; automatically routes
  around pentagon cells via a detour search when the direct path fails.
- `get_h3_nearby` — filter cells to those within a radius of a target cell.
- `get_h3_distance` — grid-step or kilometre distance between two cells.
- `find_h3_hotspots` — identify elevated cells using z-score or MAD scoring.
- `get_h3_weighted_centroid` — event-weighted geographic centroid of a
  cell-count distribution.
- `get_h3_delta` — compare two cell-count snapshots; return gained, lost,
  stable cells, and net change.
- `get_h3_stats` — descriptive statistics for a cell-count distribution:
  total events, unique cells, mean, median, std, min, max, p25, p75, p95,
  and top 5 cells by count.

#### `h3tools.viz` — visualisation
- `plot_hex` — draw H3 cells as filled polygons on a Matplotlib axis.
- `plot_hex_heatmap` — draw H3 cells colour-mapped to numeric values.
- `format_plot` — apply clean spine/tick styling to a Matplotlib axis.
- `plot_h3_choropleth` — plot a publication-ready choropleth of H3 cell counts
  on a Matplotlib axis using GeoPandas (soft dependency).

#### `h3tools.temporal` — datetime and solar utilities
- `convert_to_datetime` — parse an ISO-8601 string or pass a datetime through.
- `ensure_utc` — make a datetime timezone-aware in UTC.
- `is_dt_naive` — check whether a datetime lacks timezone information.
- `start_of_day` — truncate a datetime to midnight.
- `end_of_day` — set a datetime to the last microsecond of the day.
- `shift_tz_by_name` — convert a datetime to a named IANA timezone.
- `point_to_tz_offset` — return (IANA timezone name, UTC offset hours) for a
  Shapely Point or H3 cell index.
- `get_solar_data` — solar events (sunrise, sunset, all three twilight phases,
  day length) and timezone info for a location on a given date.
- `get_lunar_data` — moon phase name, phase number, illumination percentage,
  and moonrise/moonset times for a location on a given date.

#### `h3tools.dataframe` — pandas integration
- `add_h3_column` — add an H3 cell index column to a DataFrame from a Shapely
  Point geometry column.
- `h3_count` — return a cell→count Series from an H3 column.
- `h3_stats_df` — wrap `get_h3_stats` and return scalar statistics as a
  single-row DataFrame.  Accepts dict, Counter, or Series directly.
- `h3_to_geodataframe` — convert H3 cells to a GeoPandas GeoDataFrame with
  optional count column.  Requires `geopandas` (soft dependency).
- `h3_timeseries` — aggregate event counts (or values) by H3 cell and time
  period; returns a long-format DataFrame with columns h3_index, period, value.

#### `h3tools.analytics` — compaction
- `compact_h3_cells` — compress a set of H3 cells to the coarsest
  mixed-resolution representation by replacing complete sibling groups with
  their parent cell, recursively.
- `uncompact_h3_cells` — expand a compact mixed-resolution cell set back to
  a uniform target resolution.  Roundtrip with `compact_h3_cells` is exact.

#### General
- Full h3-py v3.x and v4.x API compatibility via `IS_H3_V4` flag.
- `py.typed` marker for PEP 561 type-checker support.
- 298 tests covering all public functions.
- `help(h3tools)` quick-reference docstring listing every public function
  with signature and one-line description.

[0.1.0]: https://github.com/KChadwick/h3tools/releases/tag/v0.1.0

---

## [Unreleased] — Backlog

Items tracked here are confirmed improvements not yet scheduled to a release.

### Planned for v0.2.0
- `get_h3_ring` — k-ring without the centre cell, for buffer/annulus analysis.
- `get_h3_weighted_centroid` — add `as_cell` option to return the H3 cell containing the centroid alongside the Shapely Point.
- `plot_hex` config dict — replace with keyword arguments or a typed dataclass to enable IDE autocomplete and catch invalid keys at call time.
- Add scale/performance guidance to documentation (expected throughput at each resolution on representative hardware).

### Technical debt
- **Doctests** — `>>>` examples exist throughout all submodules but are not executed by the test suite. Requires adding `--doctest-modules` to pytest config and auditing every example block for correctness, adding `# doctest: +SKIP`, `+ELLIPSIS`, or `+NORMALIZE_WHITESPACE` directives where needed.
