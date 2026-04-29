"""
h3tools test suite
==================
Run with:  pytest tests/
"""
from __future__ import annotations

import pytest
from collections import Counter
from datetime import datetime, timezone, timedelta
from shapely.geometry import LineString, Point, Polygon

# ─────────────────────────────────────────────────────────────────────────────
# Shared test locations & constants
# ─────────────────────────────────────────────────────────────────────────────

# London, Trafalgar Square — Europe/London, BST/GMT
LONDON_LON, LONDON_LAT = -0.1278, 51.5074
LONDON_PT = Point(LONDON_LON, LONDON_LAT)

# Disney Paris, Marne-la-Vallée — Europe/Paris, CET/CEST
DISNEY_LON, DISNEY_LAT = 2.7836, 48.8674
DISNEY_PT = Point(DISNEY_LON, DISNEY_LAT)

# Nairobi, Kenya — Africa/Nairobi, UTC+3, no DST
NAIROBI_LON, NAIROBI_LAT = 36.8219, -1.2921
NAIROBI_PT = Point(NAIROBI_LON, NAIROBI_LAT)

RESOLUTION = 9
CELL_9 = "89195da49b7ffff"   # London, Trafalgar Square, resolution 9

# Simple square polygon centred on London
POLY = Polygon([
    (-0.14, 51.49), (-0.11, 51.49),
    (-0.11, 51.52), (-0.14, 51.52),
    (-0.14, 51.49),
])


# ─────────────────────────────────────────────────────────────────────────────
# _validators
# ─────────────────────────────────────────────────────────────────────────────

class TestValidators:

    # ── _validate_h3_resolution ────────────────────────────────────────────────

    def test_valid_resolutions(self):
        from h3tools._validators import _validate_h3_resolution
        for r in (0, 7, 15):
            _validate_h3_resolution(r)

    def test_resolution_too_high(self):
        from h3tools._validators import _validate_h3_resolution
        with pytest.raises(ValueError):
            _validate_h3_resolution(16)

    def test_resolution_negative(self):
        from h3tools._validators import _validate_h3_resolution
        with pytest.raises(ValueError):
            _validate_h3_resolution(-1)

    def test_resolution_rejects_bool_true(self):
        from h3tools._validators import _validate_h3_resolution
        with pytest.raises(ValueError, match="bool"):
            _validate_h3_resolution(True)

    def test_resolution_rejects_bool_false(self):
        from h3tools._validators import _validate_h3_resolution
        with pytest.raises(ValueError, match="bool"):
            _validate_h3_resolution(False)

    def test_resolution_rejects_float(self):
        from h3tools._validators import _validate_h3_resolution
        with pytest.raises(ValueError):
            _validate_h3_resolution(9.0)

    def test_resolution_rejects_string(self):
        from h3tools._validators import _validate_h3_resolution
        with pytest.raises(ValueError):
            _validate_h3_resolution("9")

    # ── _validate_latitude / _validate_longitude ────────────────────────────────

    def test_validate_latitude_bounds(self):
        from h3tools._validators import _validate_latitude
        _validate_latitude(0.0)
        _validate_latitude(90.0)
        _validate_latitude(-90.0)
        with pytest.raises(ValueError):
            _validate_latitude(91.0)

    def test_validate_longitude_bounds(self):
        from h3tools._validators import _validate_longitude
        _validate_longitude(0.0)
        _validate_longitude(180.0)
        with pytest.raises(ValueError):
            _validate_longitude(181.0)

    # ── _validate_mgrs ─────────────────────────────────────────────────────────

    def test_validate_mgrs_valid(self):
        from h3tools._validators import _validate_mgrs
        _validate_mgrs("30UXC0000000000")

    def test_validate_mgrs_invalid(self):
        from h3tools._validators import _validate_mgrs
        with pytest.raises((ValueError, TypeError)):
            _validate_mgrs("ZZ9999999")

    def test_validate_mgrs_empty_string(self):
        from h3tools._validators import _validate_mgrs
        with pytest.raises(TypeError):
            _validate_mgrs("")

    # ── _validate_dms ──────────────────────────────────────────────────────────

    def test_validate_dms_valid(self):
        from h3tools._validators import _validate_dms
        _validate_dms("39°48'18\" N 089°38'42\" W")

    def test_validate_dms_missing_direction(self):
        from h3tools._validators import _validate_dms
        with pytest.raises(ValueError):
            _validate_dms("39 48 18 089 38 42")

    def test_validate_dms_rejects_non_string(self):
        from h3tools._validators import _validate_dms
        with pytest.raises(TypeError):
            _validate_dms(123)

    # ── _validate_point ────────────────────────────────────────────────────────

    def test_validate_point_out_of_bounds(self):
        from h3tools._validators import _validate_point
        with pytest.raises(ValueError):
            _validate_point(Point(200, 0))

    def test_validate_point_rejects_non_point(self):
        from h3tools._validators import _validate_point
        with pytest.raises(TypeError):
            _validate_point((51.5, -0.1))

    def test_validate_point_rejects_empty(self):
        from h3tools._validators import _validate_point
        with pytest.raises(ValueError):
            _validate_point(Point())


# ─────────────────────────────────────────────────────────────────────────────
# core
# ─────────────────────────────────────────────────────────────────────────────

class TestCore:

    def test_is_h3_valid_good(self):
        from h3tools.core import is_h3_valid
        from h3tools.geo import point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert is_h3_valid(cell)

    def test_is_h3_valid_bad_string(self):
        from h3tools.core import is_h3_valid
        assert not is_h3_valid("not_a_cell")

    def test_is_h3_valid_non_string(self):
        from h3tools.core import is_h3_valid
        assert not is_h3_valid(12345)

    def test_get_h3_resolution(self):
        from h3tools.core import get_h3_resolution
        from h3tools.geo import point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert get_h3_resolution(cell) == RESOLUTION

    def test_get_h3_cell_area_positive(self):
        from h3tools.core import get_h3_cell_area
        from h3tools.geo import point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert get_h3_cell_area(cell) > 0

    def test_get_h3_cell_edge_length_positive(self):
        from h3tools.core import get_h3_cell_edge_length
        from h3tools.geo import point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert get_h3_cell_edge_length(cell) > 0

    def test_get_h3_resolution_invalid_raises(self):
        from h3tools.core import get_h3_resolution
        with pytest.raises(ValueError):
            get_h3_resolution("not_a_cell")

    # ── is_h3_pentagon ────────────────────────────────────────────────────────

    def test_is_h3_pentagon_returns_false_for_hexagon(self):
        from h3tools.core import is_h3_pentagon
        from h3tools.geo import point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert not is_h3_pentagon(cell)

    def test_is_h3_pentagon_returns_true_for_pentagon(self):
        from h3tools.core import is_h3_pentagon
        import h3
        pentagons = h3.get_pentagons(5)
        assert all(is_h3_pentagon(p) for p in pentagons)

    def test_is_h3_pentagon_exactly_12_per_resolution(self):
        from h3tools.core import is_h3_pentagon
        import h3
        pentagons = h3.get_pentagons(9)
        assert len(list(pentagons)) == 12

    def test_is_h3_pentagon_invalid_index_raises(self):
        from h3tools.core import is_h3_pentagon
        with pytest.raises(ValueError):
            is_h3_pentagon("not_a_cell")

    def test_is_h3_pentagon_exported(self):
        from h3tools import is_h3_pentagon
        assert callable(is_h3_pentagon)


# ─────────────────────────────────────────────────────────────────────────────
# geo
# ─────────────────────────────────────────────────────────────────────────────

class TestGeo:

    def test_point_to_h3_returns_string(self):
        from h3tools.geo import point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert isinstance(cell, str) and len(cell) > 0

    def test_latlon_to_h3_matches_point_to_h3(self):
        from h3tools.geo import latlon_to_h3, point_to_h3
        assert latlon_to_h3((LONDON_LAT, LONDON_LON), RESOLUTION) == \
               point_to_h3(LONDON_PT, RESOLUTION)

    def test_h3_to_point_returns_point(self):
        from h3tools.geo import point_to_h3, h3_to_point
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert isinstance(h3_to_point(cell), Point)

    def test_h3_to_point_return_latlon(self):
        from h3tools.geo import point_to_h3, h3_to_point
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        lat, lon = h3_to_point(cell, return_latlon=True)
        assert -90 <= lat <= 90 and -180 <= lon <= 180

    def test_h3_to_polygon_is_valid(self):
        from h3tools.geo import point_to_h3, h3_to_polygon
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        poly = h3_to_polygon(cell)
        assert isinstance(poly, Polygon)
        assert not poly.is_empty
        assert poly.is_valid

    def test_h3_to_polygon_closed_has_correct_vertex_count(self):
        from h3tools.geo import point_to_h3, h3_to_polygon
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        poly = h3_to_polygon(cell, closed=True)
        coords = list(poly.exterior.coords)
        assert coords[0] == coords[-1]

    def test_h3_to_polygon_open_still_valid(self):
        from h3tools.geo import point_to_h3, h3_to_polygon
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        poly = h3_to_polygon(cell, closed=False)
        assert isinstance(poly, Polygon) and poly.is_valid

    def test_dms_to_point(self):
        from h3tools.geo import dms_to_point
        pt = dms_to_point("51°30'26\" N 0°7'40\" W")
        assert isinstance(pt, Point)
        assert abs(pt.y - 51.5) < 0.1

    def test_dms_to_point_return_latlon(self):
        from h3tools.geo import dms_to_point
        lat, lon = dms_to_point("51°30'26\" N 0°7'40\" W", return_latlon=True)
        assert abs(lat - 51.5) < 0.1

    def test_ddm_to_point(self):
        from h3tools.geo import ddm_to_point
        pt = ddm_to_point("51 30.4 N 0 7.7 W")
        assert isinstance(pt, Point)
        assert abs(pt.y - 51.5) < 0.1

    def test_linestring_to_h3(self):
        from h3tools.geo import linestring_to_h3
        line = LineString([(-0.14, 51.49), (-0.11, 51.52)])
        cells = linestring_to_h3(line, RESOLUTION)
        assert len(cells) >= 2

    def test_linestring_to_h3_rejects_wrong_type(self):
        from h3tools.geo import linestring_to_h3
        with pytest.raises(TypeError):
            linestring_to_h3(POLY, RESOLUTION)

    def test_polygon_to_h3_returns_cells(self):
        from h3tools.geo import polygon_to_h3
        cells = polygon_to_h3(POLY, h3_resolution=10)
        assert len(cells) > 0
        assert all(isinstance(c, str) for c in cells)

    def test_polygon_to_h3_invalid_contain_mode(self):
        from h3tools.geo import polygon_to_h3
        with pytest.raises(ValueError):
            polygon_to_h3(POLY, h3_resolution=10, contain_mode="invalid")

    def test_geometry_to_h3_point(self):
        from h3tools.geo import geometry_to_h3, point_to_h3
        assert geometry_to_h3(LONDON_PT, RESOLUTION) == {point_to_h3(LONDON_PT, RESOLUTION)}

    def test_geometry_to_h3_tuple(self):
        from h3tools.geo import geometry_to_h3, latlon_to_h3
        cells = geometry_to_h3((LONDON_LAT, LONDON_LON), RESOLUTION)
        assert latlon_to_h3((LONDON_LAT, LONDON_LON), RESOLUTION) in cells

    def test_geometry_to_h3_h3_index_same_resolution(self):
        from h3tools.geo import geometry_to_h3, point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert geometry_to_h3(cell, RESOLUTION) == {cell}

    def test_geometry_to_h3_h3_index_coarser(self):
        from h3tools.geo import geometry_to_h3, point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        result = geometry_to_h3(cell, RESOLUTION - 1)
        assert len(result) == 1

    def test_geometry_to_h3_h3_index_finer(self):
        from h3tools.geo import geometry_to_h3, point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        result = geometry_to_h3(cell, RESOLUTION + 1)
        assert len(result) > 1

    def test_coordinate_to_point_tuple(self):
        from h3tools.geo import coordinate_to_point
        pt = coordinate_to_point((LONDON_LAT, LONDON_LON))
        assert isinstance(pt, Point)

    def test_coordinate_to_point_unsupported_type(self):
        from h3tools.geo import coordinate_to_point
        with pytest.raises(TypeError):
            coordinate_to_point(12345)

    def test_h3_to_mgrs_returns_string(self):
        from h3tools.geo import point_to_h3, h3_to_mgrs
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        mgrs_str = h3_to_mgrs(cell)
        assert isinstance(mgrs_str, str) and len(mgrs_str) > 0

    def test_h3_to_mgrs_precision_controls_length(self):
        from h3tools.geo import point_to_h3, h3_to_mgrs
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        short = h3_to_mgrs(cell, precision=2)
        long_ = h3_to_mgrs(cell, precision=5)
        assert len(long_) > len(short)

    # ── points_to_h3_path ─────────────────────────────────────────────────────

    def test_points_to_h3_path_returns_list(self):
        from h3tools.geo import points_to_h3_path
        path = points_to_h3_path(LONDON_PT, DISNEY_PT, RESOLUTION)
        assert isinstance(path, list)
        assert len(path) >= 1

    def test_points_to_h3_path_endpoints(self):
        from h3tools.geo import points_to_h3_path, point_to_h3
        path = points_to_h3_path(LONDON_PT, DISNEY_PT, RESOLUTION)
        assert path[0] == point_to_h3(LONDON_PT, RESOLUTION)
        assert path[-1] == point_to_h3(DISNEY_PT, RESOLUTION)

    def test_points_to_h3_path_is_ordered(self):
        from h3tools.geo import points_to_h3_path
        from h3tools.analytics import get_h3_distance
        nearby = Point(-0.13, 51.51)
        path = points_to_h3_path(LONDON_PT, nearby, RESOLUTION)
        for a, b in zip(path, path[1:]):
            assert get_h3_distance(a, b, unit="grid") == 1

    def test_points_to_h3_path_same_point_returns_single_cell(self):
        from h3tools.geo import points_to_h3_path
        path = points_to_h3_path(LONDON_PT, LONDON_PT, RESOLUTION)
        assert len(path) == 1

    def test_points_to_h3_path_coarse_resolution(self):
        from h3tools.geo import points_to_h3_path
        path = points_to_h3_path(LONDON_PT, Point(-0.13, 51.51), h3_resolution=1)
        assert len(path) >= 1

    def test_points_to_h3_path_rejects_non_point(self):
        from h3tools.geo import points_to_h3_path
        with pytest.raises(TypeError):
            points_to_h3_path((51.5, -0.1), DISNEY_PT, RESOLUTION)

    def test_points_to_h3_path_rejects_invalid_resolution(self):
        from h3tools.geo import points_to_h3_path
        with pytest.raises(ValueError):
            points_to_h3_path(LONDON_PT, DISNEY_PT, h3_resolution=16)

    # ── h3_to_dms ─────────────────────────────────────────────────────────────

    def test_h3_to_dms_returns_tuple_of_strings(self):
        from h3tools.geo import point_to_h3, h3_to_dms
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        result = h3_to_dms(cell)
        assert isinstance(result, tuple) and len(result) == 2
        assert all(isinstance(s, str) for s in result)

    def test_h3_to_dms_lat_has_hemisphere(self):
        from h3tools.geo import point_to_h3, h3_to_dms
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        lat_dms, _ = h3_to_dms(cell)
        assert lat_dms.endswith("N") or lat_dms.endswith("S")

    def test_h3_to_dms_lon_has_hemisphere(self):
        from h3tools.geo import point_to_h3, h3_to_dms
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        _, lon_dms = h3_to_dms(cell)
        assert lon_dms.endswith("E") or lon_dms.endswith("W")

    def test_h3_to_dms_london_is_north(self):
        from h3tools.geo import point_to_h3, h3_to_dms
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        lat_dms, _ = h3_to_dms(cell)
        assert lat_dms.endswith("N")

    def test_h3_to_dms_london_is_west(self):
        from h3tools.geo import point_to_h3, h3_to_dms
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        _, lon_dms = h3_to_dms(cell)
        assert lon_dms.endswith("W")

    def test_h3_to_dms_nairobi_is_south(self):
        from h3tools.geo import point_to_h3, h3_to_dms
        cell = point_to_h3(NAIROBI_PT, RESOLUTION)
        lat_dms, _ = h3_to_dms(cell)
        assert lat_dms.endswith("S")

    def test_h3_to_dms_roundtrip_via_dms_to_point(self):
        from h3tools.geo import point_to_h3, h3_to_dms, dms_to_point
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        lat_dms, lon_dms = h3_to_dms(cell)
        recovered = dms_to_point(f"{lat_dms} {lon_dms}")
        assert abs(recovered.y - LONDON_LAT) < 0.01
        assert abs(recovered.x - LONDON_LON) < 0.01

    def test_h3_to_dms_invalid_index_raises(self):
        from h3tools.geo import h3_to_dms
        with pytest.raises(ValueError):
            h3_to_dms("not_valid")

    # ── h3_to_ddm ─────────────────────────────────────────────────────────────

    def test_h3_to_ddm_returns_tuple_of_strings(self):
        from h3tools.geo import point_to_h3, h3_to_ddm
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        result = h3_to_ddm(cell)
        assert isinstance(result, tuple) and len(result) == 2
        assert all(isinstance(s, str) for s in result)

    def test_h3_to_ddm_lat_has_hemisphere(self):
        from h3tools.geo import point_to_h3, h3_to_ddm
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        lat_ddm, _ = h3_to_ddm(cell)
        assert lat_ddm.endswith("N") or lat_ddm.endswith("S")

    def test_h3_to_ddm_lon_has_hemisphere(self):
        from h3tools.geo import point_to_h3, h3_to_ddm
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        _, lon_ddm = h3_to_ddm(cell)
        assert lon_ddm.endswith("E") or lon_ddm.endswith("W")

    def test_h3_to_ddm_london_is_north(self):
        from h3tools.geo import point_to_h3, h3_to_ddm
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        lat_ddm, _ = h3_to_ddm(cell)
        assert lat_ddm.endswith("N")

    def test_h3_to_ddm_nairobi_is_south(self):
        from h3tools.geo import point_to_h3, h3_to_ddm
        cell = point_to_h3(NAIROBI_PT, RESOLUTION)
        lat_ddm, _ = h3_to_ddm(cell)
        assert lat_ddm.endswith("S")

    def test_h3_to_ddm_invalid_index_raises(self):
        from h3tools.geo import h3_to_ddm
        with pytest.raises(ValueError):
            h3_to_ddm("not_valid")

    # ── dissolve_h3_cells ─────────────────────────────────────────────────────

    def test_dissolve_returns_valid_geometry(self):
        from h3tools.geo import point_to_h3, dissolve_h3_cells
        from h3tools.analytics import get_h3_neighbors
        disk = get_h3_neighbors(point_to_h3(LONDON_PT, RESOLUTION), k=1)
        geom = dissolve_h3_cells(disk)
        assert geom.is_valid and not geom.is_empty

    def test_dissolve_single_cell_is_polygon(self):
        from h3tools.geo import point_to_h3, dissolve_h3_cells
        from shapely.geometry import Polygon
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        geom = dissolve_h3_cells(cell)
        assert isinstance(geom, Polygon)

    def test_dissolve_single_cell_matches_h3_to_polygon(self):
        from h3tools.geo import point_to_h3, dissolve_h3_cells, h3_to_polygon
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        assert dissolve_h3_cells(cell).equals(h3_to_polygon(cell))

    def test_dissolve_contiguous_disk_is_polygon(self):
        from h3tools.geo import point_to_h3, dissolve_h3_cells
        from shapely.geometry import Polygon
        from h3tools.analytics import get_h3_neighbors
        disk = get_h3_neighbors(point_to_h3(LONDON_PT, RESOLUTION), k=1)
        geom = dissolve_h3_cells(disk)
        assert isinstance(geom, Polygon)

    def test_dissolve_deduplicates_cells(self):
        from h3tools.geo import point_to_h3, dissolve_h3_cells
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        geom_single = dissolve_h3_cells(cell)
        geom_duped = dissolve_h3_cells([cell, cell, cell])
        assert geom_single.equals(geom_duped)

    def test_dissolve_empty_raises(self):
        from h3tools.geo import dissolve_h3_cells
        with pytest.raises(ValueError):
            dissolve_h3_cells([])

    def test_dissolve_invalid_cell_raises(self):
        from h3tools.geo import dissolve_h3_cells
        with pytest.raises(ValueError):
            dissolve_h3_cells(["not_a_valid_cell"])


# ─────────────────────────────────────────────────────────────────────────────
# analytics
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalytics:

    @pytest.fixture(autouse=True)
    def _cells(self):
        from h3tools.geo import point_to_h3
        self.london_cell  = point_to_h3(LONDON_PT,  RESOLUTION)
        self.disney_cell  = point_to_h3(DISNEY_PT,  RESOLUTION)
        self.nairobi_cell = point_to_h3(NAIROBI_PT, RESOLUTION)
        self.cell = self.london_cell  # convenience alias

    # ── Hierarchy ─────────────────────────────────────────────────────────────

    def test_get_h3_parent(self):
        from h3tools.analytics import get_h3_parent
        from h3tools.core import get_h3_resolution
        parent = get_h3_parent(self.cell)
        assert get_h3_resolution(parent) == RESOLUTION - 1

    def test_get_h3_parent_explicit_resolution(self):
        from h3tools.analytics import get_h3_parent
        from h3tools.core import get_h3_resolution
        grandparent = get_h3_parent(self.cell, parent_resolution=RESOLUTION - 2)
        assert get_h3_resolution(grandparent) == RESOLUTION - 2

    def test_get_h3_parent_res0_raises(self):
        from h3tools.analytics import get_h3_parent
        from h3tools.geo import point_to_h3
        cell_r0 = point_to_h3(LONDON_PT, 0)
        with pytest.raises(ValueError):
            get_h3_parent(cell_r0)

    def test_get_h3_children_resolution(self):
        from h3tools.analytics import get_h3_children
        from h3tools.core import get_h3_resolution
        children = get_h3_children(self.cell)
        assert all(get_h3_resolution(c) == RESOLUTION + 1 for c in children)

    def test_get_h3_children_count(self):
        from h3tools.analytics import get_h3_children
        assert len(get_h3_children(self.cell)) == 7

    def test_get_h3_children_res15_raises(self):
        from h3tools.analytics import get_h3_children
        from h3tools.geo import point_to_h3
        cell_r15 = point_to_h3(LONDON_PT, 15)
        with pytest.raises(ValueError):
            get_h3_children(cell_r15)

    def test_get_h3_siblings_includes_self(self):
        from h3tools.analytics import get_h3_siblings
        siblings = get_h3_siblings(self.cell)
        assert self.cell in siblings

    def test_get_h3_siblings_count(self):
        from h3tools.analytics import get_h3_siblings
        assert len(get_h3_siblings(self.cell)) == 7

    def test_get_h3_family_keys(self):
        from h3tools.analytics import get_h3_family
        family = get_h3_family(self.cell)
        assert "parent" in family and "siblings" in family

    # ── Neighbors ─────────────────────────────────────────────────────────────

    def test_get_h3_neighbors_k1_includes_self(self):
        from h3tools.analytics import get_h3_neighbors
        neighbors = get_h3_neighbors(self.cell, k=1)
        assert self.cell in neighbors
        assert 1 < len(neighbors) <= 7

    def test_get_h3_neighbors_k0_is_self_only(self):
        from h3tools.analytics import get_h3_neighbors
        assert get_h3_neighbors(self.cell, k=0) == {self.cell}

    def test_get_h3_neighbors_k2_larger_than_k1(self):
        from h3tools.analytics import get_h3_neighbors
        assert len(get_h3_neighbors(self.cell, k=2)) > \
               len(get_h3_neighbors(self.cell, k=1))

    def test_get_h3_neighbors_rejects_bool(self):
        from h3tools.analytics import get_h3_neighbors
        with pytest.raises(ValueError):
            get_h3_neighbors(self.cell, k=True)

    def test_get_h3_neighbors_rejects_negative(self):
        from h3tools.analytics import get_h3_neighbors
        with pytest.raises(ValueError):
            get_h3_neighbors(self.cell, k=-1)

    # ── find_h3_contiguous_neighbors ──────────────────────────────────────────

    def test_find_contiguous_two_clusters(self):
        from h3tools.analytics import find_h3_contiguous_neighbors
        clusters = find_h3_contiguous_neighbors({self.london_cell, self.nairobi_cell})
        assert len(clusters) == 2

    def test_find_contiguous_one_cluster_from_disk(self):
        from h3tools.analytics import find_h3_contiguous_neighbors, get_h3_neighbors
        disk = get_h3_neighbors(self.cell, k=1)
        clusters = find_h3_contiguous_neighbors(disk)
        assert len(clusters) == 1

    def test_find_contiguous_empty_input(self):
        from h3tools.analytics import find_h3_contiguous_neighbors
        assert find_h3_contiguous_neighbors(set()) == []

    def test_find_contiguous_invalid_cell_raises(self):
        from h3tools.analytics import find_h3_contiguous_neighbors
        with pytest.raises(ValueError):
            find_h3_contiguous_neighbors({self.cell, "not_a_cell"})

    # ── get_h3_path ───────────────────────────────────────────────────────────

    def test_get_h3_path_same_cell(self):
        from h3tools.analytics import get_h3_path
        path = get_h3_path(self.cell, self.cell)
        assert path == [self.cell]

    def test_get_h3_path_returns_list(self):
        from h3tools.analytics import get_h3_path, get_h3_neighbors
        neighbor = next(iter(get_h3_neighbors(self.cell, k=1) - {self.cell}))
        path = get_h3_path(self.cell, neighbor)
        assert isinstance(path, list)

    def test_get_h3_path_ordered_endpoints(self):
        from h3tools.analytics import get_h3_path, get_h3_neighbors
        neighbor = next(iter(get_h3_neighbors(self.cell, k=1) - {self.cell}))
        path = get_h3_path(self.cell, neighbor)
        assert path[0] == self.cell
        assert path[-1] == neighbor

    def test_get_h3_path_adjacent_has_length_two(self):
        from h3tools.analytics import get_h3_path, get_h3_neighbors
        neighbor = next(iter(get_h3_neighbors(self.cell, k=1) - {self.cell}))
        assert len(get_h3_path(self.cell, neighbor)) == 2

    def test_get_h3_path_mismatched_resolution_raises(self):
        from h3tools.analytics import get_h3_path
        from h3tools.geo import point_to_h3
        cell_r8 = point_to_h3(LONDON_PT, RESOLUTION - 1)
        with pytest.raises(ValueError):
            get_h3_path(self.cell, cell_r8)

    def test_get_h3_path_pentagon_detour(self):
        # Neighbours on opposite sides of a pentagon cannot be connected by a
        # direct grid path — the detour logic must kick in.
        # '8908000000bffff' and '89080000017ffff' are opposite neighbours of
        # pentagon '89080000003ffff' at resolution 9 (confirmed via h3 library).
        from h3tools.analytics import get_h3_path
        from h3tools.core import is_h3_pentagon
        start = "8908000000bffff"
        end   = "89080000017ffff"
        path  = get_h3_path(start, end)
        assert isinstance(path, list)
        assert path[0] == start
        assert path[-1] == end
        assert not any(is_h3_pentagon(c) for c in path)

    # ── get_h3_nearby ─────────────────────────────────────────────────────────

    def test_get_h3_nearby_returns_dict(self):
        from h3tools.analytics import get_h3_nearby, get_h3_neighbors
        pool = get_h3_neighbors(self.cell, k=3)
        result = get_h3_nearby(self.cell, pool, hex_radius=1)
        assert isinstance(result, dict)

    def test_get_h3_nearby_target_in_pool_distance_zero(self):
        from h3tools.analytics import get_h3_nearby, get_h3_neighbors
        pool = get_h3_neighbors(self.cell, k=2)
        result = get_h3_nearby(self.cell, pool, hex_radius=2)
        assert self.cell in result
        assert result[self.cell] == 0

    def test_get_h3_nearby_respects_radius(self):
        from h3tools.analytics import get_h3_nearby, get_h3_neighbors
        pool = get_h3_neighbors(self.cell, k=3)
        result = get_h3_nearby(self.cell, pool, hex_radius=1)
        assert all(v <= 1 for v in result.values())
        assert len(result) <= 7

    def test_get_h3_nearby_radius_zero_returns_only_target(self):
        from h3tools.analytics import get_h3_nearby, get_h3_neighbors
        pool = get_h3_neighbors(self.cell, k=2)
        result = get_h3_nearby(self.cell, pool, hex_radius=0)
        assert list(result.keys()) == [self.cell]
        assert result[self.cell] == 0

    def test_get_h3_nearby_empty_pool_returns_empty(self):
        from h3tools.analytics import get_h3_nearby
        assert get_h3_nearby(self.cell, set(), hex_radius=2) == {}

    def test_get_h3_nearby_pool_outside_radius_returns_empty(self):
        from h3tools.analytics import get_h3_nearby
        result = get_h3_nearby(self.cell, {self.nairobi_cell}, hex_radius=1)
        assert result == {}

    def test_get_h3_nearby_rejects_bool_radius(self):
        from h3tools.analytics import get_h3_nearby
        with pytest.raises(ValueError):
            get_h3_nearby(self.cell, {self.cell}, hex_radius=True)

    def test_get_h3_nearby_rejects_negative_radius(self):
        from h3tools.analytics import get_h3_nearby
        with pytest.raises(ValueError):
            get_h3_nearby(self.cell, {self.cell}, hex_radius=-1)

    def test_get_h3_nearby_rejects_mixed_resolution_pool(self):
        from h3tools.analytics import get_h3_nearby
        from h3tools.geo import point_to_h3
        wrong_res_cell = point_to_h3(LONDON_PT, RESOLUTION - 1)
        with pytest.raises(ValueError, match="resolution"):
            get_h3_nearby(self.cell, {wrong_res_cell}, hex_radius=1)

    def test_get_h3_nearby_rejects_invalid_pool_cell(self):
        from h3tools.analytics import get_h3_nearby
        with pytest.raises(ValueError):
            get_h3_nearby(self.cell, {"not_a_cell"}, hex_radius=1)

    # ── get_h3_distance ───────────────────────────────────────────────────────

    def test_get_h3_distance_grid_adjacent(self):
        from h3tools.analytics import get_h3_neighbors, get_h3_distance
        neighbor = next(iter(get_h3_neighbors(self.cell, k=1) - {self.cell}))
        assert get_h3_distance(self.cell, neighbor, unit="grid") == 1

    def test_get_h3_distance_grid_self(self):
        from h3tools.analytics import get_h3_distance
        assert get_h3_distance(self.cell, self.cell, unit="grid") == 0

    def test_get_h3_distance_km_positive(self):
        from h3tools.analytics import get_h3_neighbors, get_h3_distance
        neighbor = next(iter(get_h3_neighbors(self.cell, k=1) - {self.cell}))
        assert get_h3_distance(self.cell, neighbor, unit="km") > 0

    def test_get_h3_distance_km_london_to_disney(self):
        from h3tools.analytics import get_h3_distance
        dist = get_h3_distance(self.london_cell, self.disney_cell, unit="km")
        assert dist > 300  # London–Disney Paris ~340 km

    def test_get_h3_distance_km_different_resolutions_allowed(self):
        from h3tools.analytics import get_h3_distance
        from h3tools.geo import point_to_h3
        nairobi_r8 = point_to_h3(NAIROBI_PT, RESOLUTION - 1)
        dist = get_h3_distance(self.london_cell, nairobi_r8, unit="km")
        assert dist > 6000  # London–Nairobi ~6800 km

    def test_get_h3_distance_grid_mismatched_resolution_raises(self):
        from h3tools.analytics import get_h3_distance
        from h3tools.geo import point_to_h3
        cell_r8 = point_to_h3(LONDON_PT, RESOLUTION - 1)
        with pytest.raises(ValueError):
            get_h3_distance(self.cell, cell_r8, unit="grid")

    def test_get_h3_distance_invalid_unit_raises(self):
        from h3tools.analytics import get_h3_distance
        with pytest.raises(ValueError):
            get_h3_distance(self.cell, self.cell, unit="miles")

    # ── find_h3_hotspots ──────────────────────────────────────────────────────

    def test_find_h3_hotspots_returns_dict(self):
        from h3tools.analytics import find_h3_hotspots, get_h3_neighbors
        disk = get_h3_neighbors(self.cell, k=2)
        counts = Counter({c: 1 for c in disk})
        counts[self.cell] = 100
        result = find_h3_hotspots(counts, k=1, threshold=0.5)
        assert isinstance(result, dict)

    def test_find_h3_hotspots_detects_hotspot(self):
        from h3tools.analytics import find_h3_hotspots, get_h3_neighbors
        disk = get_h3_neighbors(self.cell, k=2)
        counts = Counter({c: 1 for c in disk})
        counts[self.cell] = 1000
        hotspots = find_h3_hotspots(counts, k=1, threshold=0.35)
        assert self.cell in hotspots

    def test_find_h3_hotspots_empty_returns_empty(self):
        from h3tools.analytics import find_h3_hotspots
        assert find_h3_hotspots(Counter()) == {}

    def test_find_h3_hotspots_uniform_returns_empty(self):
        from h3tools.analytics import find_h3_hotspots, get_h3_neighbors
        disk = get_h3_neighbors(self.cell, k=1)
        counts = Counter({c: 10 for c in disk})
        assert find_h3_hotspots(counts, k=1, threshold=1.0) == {}

    def test_find_h3_hotspots_zscore_method(self):
        from h3tools.analytics import find_h3_hotspots, get_h3_neighbors
        disk = get_h3_neighbors(self.cell, k=2)
        counts = Counter({c: 1 for c in disk})
        counts[self.cell] = 500
        result = find_h3_hotspots(counts, k=1, threshold=0.5, method="zscore")
        assert isinstance(result, dict)

    def test_find_h3_hotspots_mad_method(self):
        from h3tools.analytics import find_h3_hotspots, get_h3_neighbors
        disk = get_h3_neighbors(self.cell, k=2)
        counts = Counter({c: 1 for c in disk})
        counts[self.cell] = 500
        result = find_h3_hotspots(counts, k=1, threshold=0.5, method="mad")
        assert isinstance(result, dict)

    def test_find_h3_hotspots_invalid_method_raises(self):
        from h3tools.analytics import find_h3_hotspots
        with pytest.raises(ValueError):
            find_h3_hotspots(Counter({self.cell: 10}), method="iqr")

    def test_find_h3_hotspots_bool_k_raises(self):
        from h3tools.analytics import find_h3_hotspots
        with pytest.raises(ValueError):
            find_h3_hotspots(Counter({self.cell: 10}), k=True)

    def test_find_h3_hotspots_invalid_cell_raises(self):
        from h3tools.analytics import find_h3_hotspots
        with pytest.raises(ValueError):
            find_h3_hotspots(Counter({"not_a_cell": 10}))

    # ── get_h3_weighted_centroid ───────────────────────────────────────────────

    def test_get_h3_weighted_centroid_returns_point(self):
        from h3tools.analytics import get_h3_weighted_centroid
        counts = Counter({self.london_cell: 10, self.nairobi_cell: 10})
        centroid = get_h3_weighted_centroid(counts)
        assert isinstance(centroid, Point)

    def test_get_h3_weighted_centroid_single_cell_at_centre(self):
        from h3tools.analytics import get_h3_weighted_centroid
        from h3tools.geo import h3_to_point
        counts = Counter({self.london_cell: 50})
        centroid = get_h3_weighted_centroid(counts)
        cell_centre = h3_to_point(self.london_cell)
        assert abs(centroid.x - cell_centre.x) < 1e-6
        assert abs(centroid.y - cell_centre.y) < 1e-6

    def test_get_h3_weighted_centroid_between_two_locations(self):
        from h3tools.analytics import get_h3_weighted_centroid
        counts = Counter({self.london_cell: 1, self.nairobi_cell: 1})
        centroid = get_h3_weighted_centroid(counts)
        # centroid longitude should be between London and Nairobi
        assert LONDON_LON < centroid.x < NAIROBI_LON

    def test_get_h3_weighted_centroid_empty_raises(self):
        from h3tools.analytics import get_h3_weighted_centroid
        with pytest.raises(ValueError):
            get_h3_weighted_centroid(Counter())

    def test_get_h3_weighted_centroid_zero_total_raises(self):
        from h3tools.analytics import get_h3_weighted_centroid
        with pytest.raises(ValueError):
            get_h3_weighted_centroid(Counter({self.london_cell: 0}))

    def test_get_h3_weighted_centroid_invalid_cell_raises(self):
        from h3tools.analytics import get_h3_weighted_centroid
        with pytest.raises(ValueError):
            get_h3_weighted_centroid(Counter({"not_a_cell": 5}))

    # ── get_h3_delta ──────────────────────────────────────────────────────────

    def test_get_h3_delta_returns_dict(self):
        from h3tools.analytics import get_h3_delta
        a = Counter({self.london_cell: 5})
        b = Counter({self.london_cell: 5})
        result = get_h3_delta(a, b)
        assert isinstance(result, dict)

    def test_get_h3_delta_keys_present(self):
        from h3tools.analytics import get_h3_delta
        result = get_h3_delta(Counter(), Counter())
        assert {"gained", "lost", "stable", "net_change"} == set(result.keys())

    def test_get_h3_delta_gained(self):
        from h3tools.analytics import get_h3_delta
        a = Counter({self.london_cell: 5, self.nairobi_cell: 3})
        b = Counter({self.london_cell: 5, self.disney_cell:  4})
        delta = get_h3_delta(a, b)
        assert self.disney_cell in delta["gained"]
        assert delta["gained"][self.disney_cell] == 4

    def test_get_h3_delta_lost(self):
        from h3tools.analytics import get_h3_delta
        a = Counter({self.london_cell: 5, self.nairobi_cell: 3})
        b = Counter({self.london_cell: 5, self.disney_cell:  4})
        delta = get_h3_delta(a, b)
        assert self.nairobi_cell in delta["lost"]
        assert delta["lost"][self.nairobi_cell] == 3

    def test_get_h3_delta_stable(self):
        from h3tools.analytics import get_h3_delta
        a = Counter({self.london_cell: 5, self.nairobi_cell: 3})
        b = Counter({self.london_cell: 5, self.disney_cell:  4})
        delta = get_h3_delta(a, b)
        assert self.london_cell in delta["stable"]

    def test_get_h3_delta_net_change(self):
        from h3tools.analytics import get_h3_delta
        a = Counter({self.london_cell: 5, self.nairobi_cell: 3})
        b = Counter({self.london_cell: 5, self.disney_cell:  4})
        delta = get_h3_delta(a, b)
        assert delta["net_change"] == 1  # gained 4, lost 3

    def test_get_h3_delta_empty_snapshots(self):
        from h3tools.analytics import get_h3_delta
        delta = get_h3_delta(Counter(), Counter())
        assert delta["gained"] == {}
        assert delta["lost"]   == {}
        assert delta["stable"] == set()
        assert delta["net_change"] == 0

    def test_get_h3_delta_invalid_cell_raises(self):
        from h3tools.analytics import get_h3_delta
        with pytest.raises(ValueError):
            get_h3_delta(Counter({"not_a_cell": 5}), Counter())


# ─────────────────────────────────────────────────────────────────────────────
# temporal
# ─────────────────────────────────────────────────────────────────────────────

class TestTemporal:

    def test_is_dt_naive_true(self):
        from h3tools.temporal import is_dt_naive
        assert is_dt_naive(datetime(2026, 1, 1)) is True

    def test_is_dt_naive_false(self):
        from h3tools.temporal import is_dt_naive
        assert is_dt_naive(datetime(2026, 1, 1, tzinfo=timezone.utc)) is False

    def test_is_dt_naive_rejects_non_datetime(self):
        from h3tools.temporal import is_dt_naive
        with pytest.raises(TypeError):
            is_dt_naive("2026-01-01")

    def test_ensure_utc_naive_input(self):
        from h3tools.temporal import ensure_utc
        aware = ensure_utc(datetime(2026, 4, 24, 12, 0, 0))
        assert aware.tzinfo is not None

    def test_ensure_utc_preserves_point_in_time(self):
        from h3tools.temporal import ensure_utc
        bst = timezone(timedelta(hours=1))
        aware_bst = datetime(2026, 4, 24, 13, 0, 0, tzinfo=bst)
        assert ensure_utc(aware_bst).hour == 12

    def test_start_of_day(self):
        from h3tools.temporal import start_of_day
        sod = start_of_day(datetime(2026, 4, 24, 15, 30, 45))
        assert sod.hour == sod.minute == sod.second == sod.microsecond == 0

    def test_end_of_day(self):
        from h3tools.temporal import end_of_day
        eod = end_of_day(datetime(2026, 4, 24))
        assert eod.hour == 23 and eod.minute == 59 and eod.microsecond == 999_999

    def test_convert_to_datetime_string(self):
        from h3tools.temporal import convert_to_datetime
        dt = convert_to_datetime("2026-04-24T12:00:00")
        assert isinstance(dt, datetime)

    def test_convert_to_datetime_passthrough(self):
        from h3tools.temporal import convert_to_datetime
        original = datetime(2026, 4, 24)
        assert convert_to_datetime(original) is original

    def test_convert_to_datetime_invalid_raises(self):
        from h3tools.temporal import convert_to_datetime
        with pytest.raises(ValueError):
            convert_to_datetime("not-a-date")

    def test_convert_to_datetime_wrong_type_raises(self):
        from h3tools.temporal import convert_to_datetime
        with pytest.raises(TypeError):
            convert_to_datetime(20260424)

    def test_point_to_tz_offset_london(self):
        from h3tools.temporal import point_to_tz_offset
        tz_name, offset = point_to_tz_offset(LONDON_PT, datetime(2026, 4, 24))
        assert "London" in tz_name or "Europe" in tz_name
        assert offset == 1.0  # BST in April

    def test_point_to_tz_offset_nairobi(self):
        from h3tools.temporal import point_to_tz_offset
        tz_name, offset = point_to_tz_offset(NAIROBI_PT, datetime(2026, 4, 24))
        assert "Nairobi" in tz_name or "Africa" in tz_name
        assert offset == 3.0  # UTC+3, no DST

    def test_point_to_tz_offset_disney_paris(self):
        from h3tools.temporal import point_to_tz_offset
        tz_name, offset = point_to_tz_offset(DISNEY_PT, datetime(2026, 4, 24))
        assert "Paris" in tz_name or "Europe" in tz_name
        assert offset == 2.0  # CEST in April

    def test_point_to_tz_offset_returns_utc_for_ocean(self):
        from h3tools.temporal import point_to_tz_offset
        tz_name, offset = point_to_tz_offset(Point(0.0, 0.0), datetime(2026, 4, 24))
        assert offset == 0.0 and ("UTC" in tz_name or "GMT" in tz_name)

    # ── get_solar_data ────────────────────────────────────────────────────────

    def test_get_solar_data_keys(self):
        from h3tools.temporal import get_solar_data
        data = get_solar_data(LONDON_PT, datetime(2026, 4, 24))
        for key in ("Sunrise", "Sunset", "Civil", "Nautical", "Astronomical"):
            assert key in data
        assert isinstance(data["Sunrise"], datetime)

    def test_get_solar_data_twilight_structure(self):
        from h3tools.temporal import get_solar_data
        data = get_solar_data(LONDON_PT, datetime(2026, 4, 24))
        for phase in ("Civil", "Nautical", "Astronomical"):
            assert "Dawn" in data[phase] and "Dusk" in data[phase]

    def test_get_solar_data_sunrise_before_sunset(self):
        from h3tools.temporal import get_solar_data
        data = get_solar_data(LONDON_PT, datetime(2026, 4, 24))
        assert data["Sunrise"] < data["Sunset"]

    def test_get_solar_data_accepts_h3_index(self):
        from h3tools.temporal import get_solar_data
        from h3tools.geo import point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        data = get_solar_data(cell, datetime(2026, 4, 24))
        assert "Sunrise" in data

    def test_get_solar_data_h3_matches_point(self):
        from h3tools.temporal import get_solar_data
        from h3tools.geo import point_to_h3, h3_to_point
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        centre = h3_to_point(cell)
        data_cell  = get_solar_data(cell,   datetime(2026, 4, 24))
        data_point = get_solar_data(centre, datetime(2026, 4, 24))
        assert data_cell["Timezone Name"] == data_point["Timezone Name"]

    def test_get_solar_data_invalid_h3_raises(self):
        from h3tools.temporal import get_solar_data
        with pytest.raises(ValueError):
            get_solar_data("not_a_cell", datetime(2026, 4, 24))

    def test_get_solar_data_nairobi_has_events(self):
        from h3tools.temporal import get_solar_data
        data = get_solar_data(NAIROBI_PT, datetime(2026, 4, 24))
        assert data["Sunrise"] is not None
        assert data["Sunset"] is not None

    # ── get_lunar_data ────────────────────────────────────────────────────────

    def test_get_lunar_data_returns_dict(self):
        from h3tools.temporal import get_lunar_data
        data = get_lunar_data(LONDON_PT, datetime(2026, 4, 24))
        assert isinstance(data, dict)

    def test_get_lunar_data_keys_present(self):
        from h3tools.temporal import get_lunar_data
        data = get_lunar_data(LONDON_PT, datetime(2026, 4, 24))
        for key in ("Phase Number", "Phase Name", "Illumination (%)",
                    "Moonrise", "Moonset", "Ephem Available"):
            assert key in data

    def test_get_lunar_data_phase_in_range(self):
        from h3tools.temporal import get_lunar_data
        data = get_lunar_data(LONDON_PT, datetime(2026, 4, 24))
        assert 0.0 <= data["Phase Number"] <= 27.0

    def test_get_lunar_data_illumination_in_range(self):
        from h3tools.temporal import get_lunar_data
        data = get_lunar_data(LONDON_PT, datetime(2026, 4, 24))
        assert 0.0 <= data["Illumination (%)"] <= 100.0

    def test_get_lunar_data_phase_name_is_string(self):
        from h3tools.temporal import get_lunar_data
        data = get_lunar_data(LONDON_PT, datetime(2026, 4, 24))
        assert isinstance(data["Phase Name"], str) and len(data["Phase Name"]) > 0

    def test_get_lunar_data_accepts_h3_index(self):
        from h3tools.temporal import get_lunar_data
        from h3tools.geo import point_to_h3
        cell = point_to_h3(LONDON_PT, RESOLUTION)
        data = get_lunar_data(cell, datetime(2026, 4, 24))
        assert "Phase Name" in data

    def test_get_lunar_data_invalid_h3_raises(self):
        from h3tools.temporal import get_lunar_data
        with pytest.raises(ValueError):
            get_lunar_data("not_a_cell", datetime(2026, 4, 24))

    def test_get_lunar_data_wrong_type_raises(self):
        from h3tools.temporal import get_lunar_data
        with pytest.raises(TypeError):
            get_lunar_data(LONDON_PT, "2026-04-24")

    def test_get_lunar_data_timezone_correct_for_nairobi(self):
        from h3tools.temporal import get_lunar_data
        data = get_lunar_data(NAIROBI_PT, datetime(2026, 4, 24))
        assert "Nairobi" in data["Timezone Name"] or "Africa" in data["Timezone Name"]


# ─────────────────────────────────────────────────────────────────────────────
# Public API surface (__init__.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestPublicAPI:
    """Smoke tests confirming every name in __all__ is importable."""

    def test_all_exports_importable(self):
        import h3tools
        for name in h3tools.__all__:
            assert hasattr(h3tools, name), f"h3tools.{name} missing from package"

    def test_plot_hex_heatmap_exported(self):
        from h3tools import plot_hex_heatmap
        assert callable(plot_hex_heatmap)

    def test_get_h3_nearby_exported(self):
        from h3tools import get_h3_nearby
        assert callable(get_h3_nearby)

    def test_points_to_h3_path_exported(self):
        from h3tools import points_to_h3_path
        assert callable(points_to_h3_path)

    def test_find_h3_hotspots_exported(self):
        from h3tools import find_h3_hotspots
        assert callable(find_h3_hotspots)

    def test_get_h3_weighted_centroid_exported(self):
        from h3tools import get_h3_weighted_centroid
        assert callable(get_h3_weighted_centroid)

    def test_get_h3_delta_exported(self):
        from h3tools import get_h3_delta
        assert callable(get_h3_delta)

    def test_get_lunar_data_exported(self):
        from h3tools import get_lunar_data
        assert callable(get_lunar_data)

    def test_get_solar_data_exported(self):
        from h3tools import get_solar_data
        assert callable(get_solar_data)

    def test_get_h3_distance_exported(self):
        from h3tools import get_h3_distance
        assert callable(get_h3_distance)

    def test_h3_to_dms_exported(self):
        from h3tools import h3_to_dms
        assert callable(h3_to_dms)

    def test_h3_to_ddm_exported(self):
        from h3tools import h3_to_ddm
        assert callable(h3_to_ddm)

    def test_dissolve_h3_cells_exported(self):
        from h3tools import dissolve_h3_cells
        assert callable(dissolve_h3_cells)

    def test_cells_to_geojson_exported(self):
        from h3tools import cells_to_geojson
        assert callable(cells_to_geojson)

    def test_geojson_to_cells_exported(self):
        from h3tools import geojson_to_cells
        assert callable(geojson_to_cells)

    def test_get_h3_stats_exported(self):
        from h3tools import get_h3_stats
        assert callable(get_h3_stats)


# ─────────────────────────────────────────────────────────────────────────────
# GeoJSON I/O
# ─────────────────────────────────────────────────────────────────────────────

class TestCellsToGeoJSON:
    def test_single_cell_returns_feature_collection(self):
        from h3tools.geo import cells_to_geojson
        result = cells_to_geojson(CELL_9)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1

    def test_feature_has_correct_h3_index(self):
        from h3tools.geo import cells_to_geojson
        result = cells_to_geojson(CELL_9)
        assert result["features"][0]["properties"]["h3_index"] == CELL_9

    def test_feature_geometry_is_polygon(self):
        from h3tools.geo import cells_to_geojson
        result = cells_to_geojson(CELL_9)
        assert result["features"][0]["geometry"]["type"] == "Polygon"

    def test_multiple_cells(self):
        from h3tools.geo import cells_to_geojson
        import h3 as _h3
        neighbors = list(_h3.grid_disk(CELL_9, 1))
        result = cells_to_geojson(neighbors)
        assert len(result["features"]) == len(set(neighbors))

    def test_deduplicates_cells(self):
        from h3tools.geo import cells_to_geojson
        result = cells_to_geojson([CELL_9, CELL_9, CELL_9])
        assert len(result["features"]) == 1

    def test_invalid_cell_raises(self):
        from h3tools.geo import cells_to_geojson
        with pytest.raises(ValueError):
            cells_to_geojson(["not_a_cell"])

    def test_empty_raises(self):
        from h3tools.geo import cells_to_geojson
        with pytest.raises(ValueError):
            cells_to_geojson([])

    def test_coordinates_are_lon_lat(self):
        from h3tools.geo import cells_to_geojson
        result = cells_to_geojson(CELL_9)
        coords = result["features"][0]["geometry"]["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        assert all(-180 <= lon <= 180 for lon in lons)
        assert all(-90 <= lat <= 90 for lat in lats)


class TestGeoJSONToCells:
    def test_polygon_geojson(self):
        from h3tools.geo import cells_to_geojson, geojson_to_cells
        geojson = cells_to_geojson(CELL_9)
        cells = geojson_to_cells(geojson, RESOLUTION)
        assert isinstance(cells, set)
        assert CELL_9 in cells

    def test_feature_collection_roundtrip(self):
        from h3tools.geo import cells_to_geojson, geojson_to_cells
        import h3 as _h3
        source = set(_h3.grid_disk(CELL_9, 1))
        geojson = cells_to_geojson(source)
        recovered = geojson_to_cells(geojson, RESOLUTION)
        assert source <= recovered

    def test_json_string_input(self):
        import json
        from h3tools.geo import cells_to_geojson, geojson_to_cells
        geojson = cells_to_geojson(CELL_9)
        cells = geojson_to_cells(json.dumps(geojson), RESOLUTION)
        assert CELL_9 in cells

    def test_invalid_resolution_raises(self):
        from h3tools.geo import cells_to_geojson, geojson_to_cells
        geojson = cells_to_geojson(CELL_9)
        with pytest.raises(ValueError):
            geojson_to_cells(geojson, 99)

    def test_invalid_json_string_raises(self):
        from h3tools.geo import geojson_to_cells
        with pytest.raises(ValueError):
            geojson_to_cells("not json", RESOLUTION)

    def test_non_dict_raises(self):
        from h3tools.geo import geojson_to_cells
        with pytest.raises(TypeError):
            geojson_to_cells(["not", "a", "dict"], RESOLUTION)

    def test_unsupported_geojson_type_raises(self):
        from h3tools.geo import geojson_to_cells
        with pytest.raises(ValueError):
            geojson_to_cells({"type": "GeometryCollection", "geometries": []}, RESOLUTION)

    def test_empty_feature_collection(self):
        from h3tools.geo import geojson_to_cells
        result = geojson_to_cells({"type": "FeatureCollection", "features": []}, RESOLUTION)
        assert result == set()


# ─────────────────────────────────────────────────────────────────────────────
# Summary statistics
# ─────────────────────────────────────────────────────────────────────────────

class TestGetH3Stats:
    COUNTS = {
        "89195da49b7ffff": 10,
        "89195da49b3ffff": 5,
        "89195da49bbffff": 2,
        "89195da498fffff": 8,
        "89195da4983ffff": 1,
    }

    def test_total_events(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        assert stats["total_events"] == 26

    def test_unique_cells(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        assert stats["unique_cells"] == 5

    def test_mean(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        assert abs(stats["mean"] - 5.2) < 0.01

    def test_median(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        assert stats["median"] == 5.0

    def test_min_max(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        assert stats["min"] == 1.0
        assert stats["max"] == 10.0

    def test_percentiles_ordered(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        assert stats["p25"] <= stats["median"] <= stats["p75"] <= stats["p95"]

    def test_top_cells_length(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        assert len(stats["top_cells"]) == 5

    def test_top_cells_highest_first(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        values = list(stats["top_cells"].values())
        assert values == sorted(values, reverse=True)

    def test_top_cells_top_cell_correct(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats(self.COUNTS)
        top = next(iter(stats["top_cells"]))
        assert top == "89195da49b7ffff"

    def test_top_cells_capped_at_five(self):
        from h3tools.analytics import get_h3_stats
        import h3 as _h3
        big = {c: i + 1 for i, c in enumerate(_h3.grid_disk(CELL_9, 1))}
        stats = get_h3_stats(big)
        assert len(stats["top_cells"]) == 5

    def test_single_cell(self):
        from h3tools.analytics import get_h3_stats
        stats = get_h3_stats({CELL_9: 42})
        assert stats["total_events"] == 42
        assert stats["unique_cells"] == 1
        assert stats["std"] == 0.0

    def test_empty_raises(self):
        from h3tools.analytics import get_h3_stats
        with pytest.raises(ValueError):
            get_h3_stats({})

    def test_invalid_cell_raises(self):
        from h3tools.analytics import get_h3_stats
        with pytest.raises(ValueError):
            get_h3_stats({"not_a_cell": 5})

    def test_negative_count_raises(self):
        from h3tools.analytics import get_h3_stats
        with pytest.raises(ValueError):
            get_h3_stats({CELL_9: -1})

    def test_non_mapping_raises(self):
        from h3tools.analytics import get_h3_stats
        with pytest.raises(TypeError):
            get_h3_stats([CELL_9, CELL_9])


# ─────────────────────────────────────────────────────────────────────────────
# DataFrame integration  (h3tools.dataframe)
# ─────────────────────────────────────────────────────────────────────────────

class TestAddH3Column:
    def _make_df(self):
        import pandas as pd
        return pd.DataFrame({
            "geometry": [
                LONDON_PT,
                DISNEY_PT,
                LONDON_PT,
                NAIROBI_PT,
            ]
        })

    def test_returns_new_dataframe(self):
        from h3tools.dataframe import add_h3_column
        df = self._make_df()
        result = add_h3_column(df, "geometry", RESOLUTION)
        assert result is not df

    def test_original_unchanged(self):
        from h3tools.dataframe import add_h3_column
        df = self._make_df()
        add_h3_column(df, "geometry", RESOLUTION)
        assert "h3_index" not in df.columns

    def test_default_column_name(self):
        from h3tools.dataframe import add_h3_column
        result = add_h3_column(self._make_df(), "geometry", RESOLUTION)
        assert "h3_index" in result.columns

    def test_custom_column_name(self):
        from h3tools.dataframe import add_h3_column
        result = add_h3_column(self._make_df(), "geometry", RESOLUTION, h3_col="cell")
        assert "cell" in result.columns

    def test_row_count_preserved(self):
        from h3tools.dataframe import add_h3_column
        df = self._make_df()
        result = add_h3_column(df, "geometry", RESOLUTION)
        assert len(result) == len(df)

    def test_cell_values_are_valid_h3(self):
        from h3tools.dataframe import add_h3_column
        from h3tools import is_h3_valid
        result = add_h3_column(self._make_df(), "geometry", RESOLUTION)
        assert result["h3_index"].apply(is_h3_valid).all()

    def test_london_cell_correct(self):
        from h3tools.dataframe import add_h3_column
        result = add_h3_column(self._make_df(), "geometry", RESOLUTION)
        assert result.iloc[0]["h3_index"] == CELL_9

    def test_invalid_geometry_col_raises(self):
        from h3tools.dataframe import add_h3_column
        with pytest.raises(ValueError):
            add_h3_column(self._make_df(), "no_such_col", RESOLUTION)

    def test_invalid_resolution_raises(self):
        from h3tools.dataframe import add_h3_column
        with pytest.raises(ValueError):
            add_h3_column(self._make_df(), "geometry", 99)

    def test_overwrites_existing_column(self):
        from h3tools.dataframe import add_h3_column
        import pandas as pd
        df = self._make_df()
        df["h3_index"] = "old_value"
        result = add_h3_column(df, "geometry", RESOLUTION)
        assert result["h3_index"].iloc[0] != "old_value"


class TestH3Count:
    def _make_counted_df(self):
        import pandas as pd
        from h3tools.dataframe import add_h3_column
        df = add_h3_column(
            pd.DataFrame({"geometry": [LONDON_PT, LONDON_PT, DISNEY_PT]}),
            "geometry", RESOLUTION,
        )
        return df

    def test_returns_series(self):
        import pandas as pd
        from h3tools.dataframe import h3_count
        result = h3_count(self._make_counted_df())
        assert isinstance(result, pd.Series)

    def test_most_frequent_first(self):
        from h3tools.dataframe import h3_count
        result = h3_count(self._make_counted_df())
        assert result.iloc[0] == 2

    def test_total_counts_match_rows(self):
        from h3tools.dataframe import h3_count
        df = self._make_counted_df()
        result = h3_count(df)
        assert result.sum() == len(df)

    def test_custom_h3_col(self):
        import pandas as pd
        from h3tools.dataframe import add_h3_column, h3_count
        df = add_h3_column(
            pd.DataFrame({"geometry": [LONDON_PT]}),
            "geometry", RESOLUTION, h3_col="cell",
        )
        result = h3_count(df, h3_col="cell")
        assert result.sum() == 1

    def test_missing_column_raises(self):
        import pandas as pd
        from h3tools.dataframe import h3_count
        with pytest.raises(ValueError):
            h3_count(pd.DataFrame({"a": [1, 2]}), h3_col="h3_index")


class TestH3StatsDf:
    COUNTS = {
        "89195da49b7ffff": 10,
        "89195da49b3ffff": 5,
        "89195da49bbffff": 2,
    }

    def test_returns_dataframe(self):
        import pandas as pd
        from h3tools.dataframe import h3_stats_df
        result = h3_stats_df(self.COUNTS)
        assert isinstance(result, pd.DataFrame)

    def test_single_row(self):
        from h3tools.dataframe import h3_stats_df
        result = h3_stats_df(self.COUNTS)
        assert len(result) == 1

    def test_expected_columns_present(self):
        from h3tools.dataframe import h3_stats_df
        result = h3_stats_df(self.COUNTS)
        for col in ("total_events", "unique_cells", "mean", "median",
                    "std", "min", "max", "p25", "p75", "p95"):
            assert col in result.columns

    def test_top_cells_excluded(self):
        from h3tools.dataframe import h3_stats_df
        result = h3_stats_df(self.COUNTS)
        assert "top_cells" not in result.columns

    def test_total_events_correct(self):
        from h3tools.dataframe import h3_stats_df
        result = h3_stats_df(self.COUNTS)
        assert result["total_events"].iloc[0] == 17

    def test_accepts_counter(self):
        from collections import Counter
        from h3tools.dataframe import h3_stats_df
        result = h3_stats_df(Counter(self.COUNTS))
        assert result["total_events"].iloc[0] == 17

    def test_accepts_series_to_dict(self):
        from h3tools.dataframe import add_h3_column, h3_count, h3_stats_df
        import pandas as pd
        df = add_h3_column(
            pd.DataFrame({"geometry": [LONDON_PT, LONDON_PT, DISNEY_PT]}),
            "geometry", RESOLUTION,
        )
        counts = h3_count(df).to_dict()
        result = h3_stats_df(counts)
        assert result["total_events"].iloc[0] == 3

    def test_accepts_series_directly(self):
        from h3tools.dataframe import add_h3_column, h3_count, h3_stats_df
        import pandas as pd
        df = add_h3_column(
            pd.DataFrame({"geometry": [LONDON_PT, LONDON_PT, DISNEY_PT]}),
            "geometry", RESOLUTION,
        )
        counts = h3_count(df)   # Series — no .to_dict() needed
        result = h3_stats_df(counts)
        assert result["total_events"].iloc[0] == 3

    def test_empty_raises(self):
        from h3tools.dataframe import h3_stats_df
        with pytest.raises(ValueError):
            h3_stats_df({})


# ─────────────────────────────────────────────────────────────────────────────
# ddm_to_h3
# ─────────────────────────────────────────────────────────────────────────────

class TestDdmToH3:
    def test_returns_valid_h3_index(self):
        from h3tools.geo import ddm_to_h3
        from h3tools import is_h3_valid
        cell = ddm_to_h3("51 30.4 N 0 7.7 W", h3_resolution=9)
        assert is_h3_valid(cell)

    def test_matches_latlon_equivalent(self):
        from h3tools.geo import ddm_to_h3, ddm_to_point
        from h3tools import point_to_h3
        pt   = ddm_to_point("51 30.4 N 0 7.7 W")
        cell = ddm_to_h3("51 30.4 N 0 7.7 W", h3_resolution=9)
        assert cell == point_to_h3(pt, h3_resolution=9)

    def test_resolution_respected(self):
        from h3tools.geo import ddm_to_h3
        from h3tools import get_h3_resolution
        cell = ddm_to_h3("51 30.4 N 0 7.7 W", h3_resolution=7)
        assert get_h3_resolution(cell) == 7

    def test_invalid_ddm_raises(self):
        from h3tools.geo import ddm_to_h3
        with pytest.raises(ValueError):
            ddm_to_h3("not a ddm string", h3_resolution=9)

    def test_invalid_resolution_raises(self):
        from h3tools.geo import ddm_to_h3
        with pytest.raises(ValueError):
            ddm_to_h3("51 30.4 N 0 7.7 W", h3_resolution=99)

    def test_exported_from_package(self):
        from h3tools import ddm_to_h3
        assert callable(ddm_to_h3)


# ─────────────────────────────────────────────────────────────────────────────
# compact / uncompact
# ─────────────────────────────────────────────────────────────────────────────

class TestCompactH3Cells:
    def _ring(self):
        import h3 as _h3
        return set(_h3.grid_disk(CELL_9, 1))

    def test_returns_set(self):
        from h3tools import compact_h3_cells
        result = compact_h3_cells(self._ring())
        assert isinstance(result, set)

    def test_compacted_smaller_or_equal(self):
        from h3tools import compact_h3_cells
        cells = self._ring()
        assert len(compact_h3_cells(cells)) <= len(cells)

    def test_empty_returns_empty(self):
        from h3tools import compact_h3_cells
        assert compact_h3_cells([]) == set()

    def test_single_cell_unchanged(self):
        from h3tools import compact_h3_cells
        assert compact_h3_cells([CELL_9]) == {CELL_9}

    def test_invalid_cell_raises(self):
        from h3tools import compact_h3_cells
        with pytest.raises(ValueError):
            compact_h3_cells(["not_a_cell"])

    def test_exported_from_package(self):
        from h3tools import compact_h3_cells
        assert callable(compact_h3_cells)


class TestUncompactH3Cells:
    def _compacted(self):
        import h3 as _h3
        from h3tools import compact_h3_cells
        return compact_h3_cells(set(_h3.grid_disk(CELL_9, 1)))

    def test_returns_set(self):
        from h3tools import uncompact_h3_cells
        result = uncompact_h3_cells(self._compacted(), RESOLUTION)
        assert isinstance(result, set)

    def test_roundtrip(self):
        import h3 as _h3
        from h3tools import compact_h3_cells, uncompact_h3_cells
        original = set(_h3.grid_disk(CELL_9, 1))
        compacted   = compact_h3_cells(original)
        uncompacted = uncompact_h3_cells(compacted, RESOLUTION)
        assert uncompacted == original

    def test_empty_returns_empty(self):
        from h3tools import uncompact_h3_cells
        assert uncompact_h3_cells([], RESOLUTION) == set()

    def test_invalid_resolution_raises(self):
        from h3tools import uncompact_h3_cells
        with pytest.raises(ValueError):
            uncompact_h3_cells([CELL_9], 99)

    def test_invalid_cell_raises(self):
        from h3tools import uncompact_h3_cells
        with pytest.raises(ValueError):
            uncompact_h3_cells(["not_a_cell"], RESOLUTION)

    def test_exported_from_package(self):
        from h3tools import uncompact_h3_cells
        assert callable(uncompact_h3_cells)


# ─────────────────────────────────────────────────────────────────────────────
# h3_to_geodataframe
# ─────────────────────────────────────────────────────────────────────────────

geopandas = pytest.importorskip("geopandas", reason="geopandas not installed")


class TestH3ToGeoDataFrame:
    CELLS = ["89195da49b7ffff", "89195da49b3ffff", "89195da49bbffff"]

    def test_returns_geodataframe(self):
        from h3tools import h3_to_geodataframe
        result = h3_to_geodataframe(self.CELLS)
        assert type(result).__name__ == "GeoDataFrame"

    def test_row_count(self):
        from h3tools import h3_to_geodataframe
        assert len(h3_to_geodataframe(self.CELLS)) == 3

    def test_has_h3_index_column(self):
        from h3tools import h3_to_geodataframe
        assert "h3_index" in h3_to_geodataframe(self.CELLS).columns

    def test_has_geometry_column(self):
        from h3tools import h3_to_geodataframe
        assert "geometry" in h3_to_geodataframe(self.CELLS).columns

    def test_geometry_is_polygon(self):
        from h3tools import h3_to_geodataframe
        from shapely.geometry import Polygon
        gdf = h3_to_geodataframe(self.CELLS)
        assert all(isinstance(g, Polygon) for g in gdf.geometry)

    def test_crs_default(self):
        from h3tools import h3_to_geodataframe
        gdf = h3_to_geodataframe(self.CELLS)
        assert gdf.crs.to_epsg() == 4326

    def test_custom_crs(self):
        from h3tools import h3_to_geodataframe
        gdf = h3_to_geodataframe(self.CELLS, crs="EPSG:3857")
        assert gdf.crs.to_epsg() == 3857

    def test_with_cell_counts(self):
        from h3tools import h3_to_geodataframe
        counts = {c: i + 1 for i, c in enumerate(self.CELLS)}
        gdf = h3_to_geodataframe(self.CELLS, cell_counts=counts)
        assert "count" in gdf.columns
        assert gdf["count"].sum() == sum(counts.values())

    def test_missing_count_defaults_to_zero(self):
        from h3tools import h3_to_geodataframe
        counts = {self.CELLS[0]: 5}   # only first cell has a count
        gdf = h3_to_geodataframe(self.CELLS, cell_counts=counts)
        assert gdf.loc[gdf["h3_index"] == self.CELLS[1], "count"].iloc[0] == 0

    def test_deduplicates_cells(self):
        from h3tools import h3_to_geodataframe
        gdf = h3_to_geodataframe(self.CELLS * 3)
        assert len(gdf) == 3

    def test_single_string_input(self):
        from h3tools import h3_to_geodataframe
        gdf = h3_to_geodataframe(CELL_9)
        assert len(gdf) == 1

    def test_empty_raises(self):
        from h3tools import h3_to_geodataframe
        with pytest.raises(ValueError):
            h3_to_geodataframe([])

    def test_invalid_cell_raises(self):
        from h3tools import h3_to_geodataframe
        with pytest.raises(ValueError):
            h3_to_geodataframe(["not_a_cell"])

    def test_exported_from_package(self):
        from h3tools import h3_to_geodataframe
        assert callable(h3_to_geodataframe)


# ─────────────────────────────────────────────────────────────────────────────
# h3_timeseries
# ─────────────────────────────────────────────────────────────────────────────

class TestH3Timeseries:
    """Tests for h3_timeseries."""

    @pytest.fixture
    def sample_df(self):
        pd = pytest.importorskip("pandas")
        from shapely.geometry import Point
        from h3tools import add_h3_column
        df = pd.DataFrame({
            "geometry": [Point(-0.1278, 51.5074)] * 4 + [Point(2.3522, 48.8566)] * 2,
            "timestamp": pd.date_range("2026-01-01", periods=6, freq="D"),
        })
        return add_h3_column(df, "geometry", resolution=9)

    def test_returns_dataframe(self, sample_df):
        pd = pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        result = h3_timeseries(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_columns(self, sample_df):
        from h3tools import h3_timeseries
        pytest.importorskip("pandas")
        result = h3_timeseries(sample_df)
        assert list(result.columns) == ["h3_index", "period", "value"]

    def test_daily_count(self, sample_df):
        from h3tools import h3_timeseries
        pytest.importorskip("pandas")
        result = h3_timeseries(sample_df, freq="D")
        assert result["value"].sum() == len(sample_df)

    def test_weekly_bucketing(self, sample_df):
        from h3tools import h3_timeseries
        pytest.importorskip("pandas")
        result = h3_timeseries(sample_df, freq="W")
        assert len(result) >= 1

    def test_custom_h3_col(self, sample_df):
        pd = pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        df2 = sample_df.rename(columns={"h3_index": "cell"})
        result = h3_timeseries(df2, h3_col="cell")
        assert "h3_index" in result.columns

    def test_custom_time_col(self, sample_df):
        pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        df2 = sample_df.rename(columns={"timestamp": "ts"})
        result = h3_timeseries(df2, time_col="ts")
        assert "period" in result.columns

    def test_value_col_sum(self, sample_df):
        pd = pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        sample_df = sample_df.copy()
        sample_df["weight"] = 2.0
        result = h3_timeseries(sample_df, value_col="weight", agg="sum")
        assert result["value"].sum() == pytest.approx(2.0 * len(sample_df))

    def test_value_col_mean(self, sample_df):
        pd = pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        sample_df = sample_df.copy()
        sample_df["weight"] = 3.0
        result = h3_timeseries(sample_df, value_col="weight", agg="mean")
        assert (result["value"] == 3.0).all()

    def test_missing_h3_col_raises(self, sample_df):
        pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        with pytest.raises(ValueError, match="h3_index"):
            h3_timeseries(sample_df, h3_col="no_such_col")

    def test_missing_time_col_raises(self, sample_df):
        pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        with pytest.raises(ValueError, match="timestamp"):
            h3_timeseries(sample_df, time_col="no_such_col")

    def test_missing_value_col_raises(self, sample_df):
        pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        with pytest.raises(ValueError, match="missing_col"):
            h3_timeseries(sample_df, value_col="missing_col")

    def test_string_timestamps_coerced(self):
        pd = pytest.importorskip("pandas")
        from h3tools import h3_timeseries
        from h3tools import add_h3_column
        from shapely.geometry import Point
        df = pd.DataFrame({
            "geometry": [Point(-0.1278, 51.5074)] * 3,
            "timestamp": ["2026-01-01", "2026-01-02", "2026-01-03"],
        })
        df = add_h3_column(df, "geometry", resolution=9)
        result = h3_timeseries(df, freq="D")
        assert result["value"].sum() == 3

    def test_exported_from_package(self):
        from h3tools import h3_timeseries
        assert callable(h3_timeseries)


# ─────────────────────────────────────────────────────────────────────────────
# plot_h3_choropleth
# ─────────────────────────────────────────────────────────────────────────────

class TestPlotH3Choropleth:
    """Tests for plot_h3_choropleth."""

    COUNTS = {CELL_9: 10, "89195da49b3ffff": 5, "89195da493bffff": 3}

    def test_runs_without_error(self):
        pytest.importorskip("geopandas")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from h3tools.viz import plot_h3_choropleth
        fig, ax = plt.subplots()
        plot_h3_choropleth(ax, self.COUNTS)
        plt.close(fig)

    def test_with_title(self):
        pytest.importorskip("geopandas")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from h3tools.viz import plot_h3_choropleth
        fig, ax = plt.subplots()
        plot_h3_choropleth(ax, self.COUNTS, title="Test choropleth")
        assert ax.get_title() == "Test choropleth"
        plt.close(fig)

    def test_legend_false(self):
        pytest.importorskip("geopandas")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from h3tools.viz import plot_h3_choropleth
        fig, ax = plt.subplots()
        plot_h3_choropleth(ax, self.COUNTS, legend=False)
        plt.close(fig)

    def test_empty_counts_raises(self):
        pytest.importorskip("geopandas")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from h3tools.viz import plot_h3_choropleth
        fig, ax = plt.subplots()
        with pytest.raises(ValueError):
            plot_h3_choropleth(ax, {})
        plt.close(fig)

    def test_custom_cmap(self):
        pytest.importorskip("geopandas")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from h3tools.viz import plot_h3_choropleth
        fig, ax = plt.subplots()
        plot_h3_choropleth(ax, self.COUNTS, cmap="viridis")
        plt.close(fig)

    def test_exported_from_package(self):
        from h3tools import plot_h3_choropleth
        assert callable(plot_h3_choropleth)
