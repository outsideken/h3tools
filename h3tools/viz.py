"""
h3tools.viz
============
Matplotlib helpers for plotting H3 hexagonal cells.

Provides functions for rendering individual cells, heatmaps, styled axes
overlays, and choropleth maps.  All plotting functions operate on existing
:class:`matplotlib.axes.Axes` objects and modify them in place, so they
integrate naturally with any Matplotlib figure layout.

:func:`plot_h3_choropleth` additionally requires ``geopandas``, which is a
soft dependency and is only imported when the function is called.

Functions
---------
plot_hex
    Draw H3 cells as filled polygons on a Matplotlib axis.
plot_hex_heatmap
    Draw H3 cells colour-mapped to numeric values (heatmap).
format_plot
    Apply minimal, clean spine/tick styling to a Matplotlib axis.
plot_h3_choropleth
    Plot a publication-ready choropleth of H3 cell counts on a Matplotlib axis.
"""

from __future__ import annotations

from collections.abc import Iterable

import matplotlib
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

from h3tools._validators import _validate_h3_index

__all__ = [
    "plot_hex",
    "plot_hex_heatmap",
    "format_plot",
    "plot_h3_choropleth",
]


# ── Core cell plotter ─────────────────────────────────────────────────────────

def plot_hex(
    ax: plt.Axes,
    cells: str | Iterable[str],
    config: dict | None = None,
) -> None:
    """
    Draw H3 hexagonal cells as filled polygons on *ax*.

    Each cell is rendered as a filled :class:`matplotlib.patches.Polygon`
    whose vertices are derived from the H3 cell boundary.  Duplicate cells
    in *cells* are silently deduplicated.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The target axis on which to draw.
    cells : str or iterable of str
        One or more H3 cell index strings.  A bare string is treated as a
        single cell.
    config : dict, optional
        Visual configuration dictionary.  Recognised keys and their defaults:

        ============  =========  ===============================================
        Key           Default    Description
        ============  =========  ===============================================
        ``Facecolor`` ``None``   Fill colour.  ``None`` gives a transparent fill.
        ``Edgecolor`` ``'red'``  Polygon edge colour.
        ``Line Width``  ``1.0``  Edge line width in points.
        ``Line Style``  ``'-'``  Edge line style (``'-'``, ``'--'``, etc.).
        ``Alpha``       ``1.0``  Polygon opacity in [0, 1].
        ``zorder``      ``0``    Z-order for layering multiple artists.
        ``Label``       ``None`` Legend label.  Applied to the first cell only
                                 to avoid duplicate legend entries.
        ============  =========  ===============================================

        Any unrecognised keys are silently ignored.

    Returns
    -------
    None
        Modifies *ax* in place.

    Raises
    ------
    ValueError
        If any element of *cells* is not a valid H3 cell index.

    See Also
    --------
    plot_hex_heatmap : Colour-map cells by a numeric value instead.
    format_plot : Apply axis styling after plotting.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> fig, ax = plt.subplots()
    >>> plot_hex(ax, ["89195da49b7ffff"], {"Facecolor": "steelblue", "Alpha": 0.5})
    >>> plt.close()

    >>> # Multiple cells with a legend label:
    >>> from h3tools import get_h3_neighbors
    >>> ring = get_h3_neighbors("89195da49b7ffff", k=1)
    >>> plot_hex(ax, ring, {"Facecolor": "orange", "Label": "k=1 ring"})
    >>> plt.close()
    """
    from h3tools.geo import h3_to_polygon

    if isinstance(cells, str):
        cells = [cells]

    cfg = config or {}
    facecolor = cfg.get("Facecolor", None)
    edgecolor  = cfg.get("Edgecolor", "red")
    lw         = cfg.get("Line Width", 1.0)
    ls         = cfg.get("Line Style", "-")
    alpha      = cfg.get("Alpha", 1.0)
    zorder     = cfg.get("zorder", 0)
    label      = cfg.get("Label", None)

    first = True
    for h3_index in set(cells):
        poly = h3_to_polygon(h3_index)
        x, y = poly.exterior.xy
        ax.fill(
            x, y,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=lw,
            linestyle=ls,
            alpha=alpha,
            zorder=zorder,
            label=label if first else None,
        )
        first = False


def plot_hex_heatmap(
    ax: plt.Axes,
    cell_values: dict[str, float],
    cmap: str = "YlOrRd",
    vmin: float | None = None,
    vmax: float | None = None,
    edgecolor: str = "none",
    linewidth: float = 0.3,
    alpha: float = 0.85,
    zorder: int = 0,
) -> mcolors.Normalize:
    """
    Draw H3 cells colour-mapped to numeric values (heatmap).

    Each cell is filled with a colour derived by mapping its value through
    the chosen Matplotlib colourmap.  Returns the normaliser so the caller
    can attach a colourbar.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The target axis on which to draw.
    cell_values : dict of {str: float}
        Mapping of ``{h3_index: numeric_value}`` for each cell to plot.
        An empty dict is handled gracefully (a default normaliser is
        returned and nothing is drawn).
    cmap : str, optional
        Name of any Matplotlib colourmap.  Default is ``'YlOrRd'``.
    vmin : float, optional
        Lower bound of the colour scale.  When omitted, defaults to the
        minimum value in *cell_values*.
    vmax : float, optional
        Upper bound of the colour scale.  When omitted, defaults to the
        maximum value in *cell_values*.
    edgecolor : str, optional
        Cell edge colour.  Default is ``'none'`` (no visible border).
    linewidth : float, optional
        Cell edge line width in points.  Default is ``0.3``.
    alpha : float, optional
        Cell fill opacity in [0, 1].  Default is ``0.85``.
    zorder : int, optional
        Z-order for layering.  Default is ``0``.

    Returns
    -------
    matplotlib.colors.Normalize
        The normaliser used to map values to colours.  Pass it to
        :class:`matplotlib.cm.ScalarMappable` to create a colourbar:

        .. code-block:: python

            norm = plot_hex_heatmap(ax, data)
            sm = matplotlib.cm.ScalarMappable(cmap="YlOrRd", norm=norm)
            plt.colorbar(sm, ax=ax)

    See Also
    --------
    plot_hex : Draw cells with a uniform colour instead.
    format_plot : Apply axis styling after plotting.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> fig, ax = plt.subplots()
    >>> data = {"89195da49b7ffff": 42.0, "897a6e42ca3ffff": 17.5}
    >>> norm = plot_hex_heatmap(ax, data, cmap="plasma")
    >>> sm = plt.cm.ScalarMappable(cmap="plasma", norm=norm)
    >>> plt.colorbar(sm, ax=ax)  # doctest: +ELLIPSIS
    <matplotlib.colorbar.Colorbar object at ...>
    >>> plt.close()
    """
    from h3tools.geo import h3_to_polygon

    if not cell_values:
        return mcolors.Normalize(vmin=0, vmax=1)

    values = np.array(list(cell_values.values()), dtype=float)
    norm = mcolors.Normalize(
        vmin=vmin if vmin is not None else values.min(),
        vmax=vmax if vmax is not None else values.max(),
    )
    colour_map = matplotlib.colormaps[cmap]

    for h3_index, value in cell_values.items():
        poly = h3_to_polygon(h3_index)
        x, y = poly.exterior.xy
        rgba = colour_map(norm(value))
        ax.fill(
            x, y,
            facecolor=rgba,
            edgecolor=edgecolor,
            linewidth=linewidth,
            alpha=alpha,
            zorder=zorder,
        )

    return norm


# ── Axis styling ──────────────────────────────────────────────────────────────

def format_plot(
    ax: plt.Axes,
    font_size: int = 10,
    color: str = "black",
) -> None:
    """
    Apply minimal, clean styling to a Matplotlib axis.

    Removes all four axis spines and adjusts tick label appearance.
    Intended to complement :func:`plot_hex` and :func:`plot_hex_heatmap`
    by producing a clean map-like frame.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axis to style.  Modified in place.
    font_size : int, optional
        Font size for tick labels in points.  Default is ``10``.
    color : str, optional
        Colour for tick labels and tick marks.  Accepts any Matplotlib
        colour specification (named colour, hex string, etc.).
        Default is ``'black'``.

    Returns
    -------
    None
        Modifies *ax* in place.

    See Also
    --------
    plot_hex : Draw H3 cells on an axis.
    plot_hex_heatmap : Draw a heatmap on an axis.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> fig, ax = plt.subplots()
    >>> format_plot(ax, font_size=9, color="#333333")
    >>> all(not spine.get_visible() for spine in ax.spines.values())
    True
    >>> plt.close()
    """
    ax.tick_params(
        direction="out",
        length=4,
        width=1,
        colors=color,
        labelsize=font_size,
        labelcolor=color,
    )
    for spine in ax.spines.values():
        spine.set_visible(False)


# ── Choropleth ────────────────────────────────────────────────────────────────

def plot_h3_choropleth(
    ax: plt.Axes,
    cell_counts: dict,
    cmap: str = "YlOrRd",
    legend: bool = True,
    legend_label: str = "Count",
    title: str | None = None,
    edgecolor: str = "white",
    linewidth: float = 0.3,
    missing_color: str = "#eeeeee",
) -> None:
    """
    Plot a choropleth of H3 cell counts on a Matplotlib axis.

    Converts *cell_counts* to a GeoPandas GeoDataFrame and renders each
    cell as a filled polygon coloured by its count value.  Produces a
    publication-ready map with a colourbar legend in a single call.

    Requires ``geopandas``, which is imported lazily and only raises
    :class:`ImportError` if the function is called without it installed.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axis on which to draw.
    cell_counts : dict[str, int | float]
        Mapping of H3 cell index → count or weight.  All keys must be
        valid H3 cell indices.
    cmap : str, optional
        Matplotlib colourmap name.  Defaults to ``"YlOrRd"`` (yellow →
        orange → red), which is intuitive for density data.
    legend : bool, optional
        Whether to draw a colourbar legend.  Default is ``True``.
    legend_label : str, optional
        Label for the colourbar axis.  Default is ``"Count"``.
    title : str, optional
        Axis title.  If ``None`` (default), no title is set.
    edgecolor : str, optional
        Colour of cell boundary lines.  Default is ``"white"``.
    linewidth : float, optional
        Width of cell boundary lines.  Default is ``0.3``.
    missing_color : str, optional
        Fill colour for cells present in the GeoDataFrame but with no
        count value.  Not typically used since all cells come from
        *cell_counts*, but exposed for completeness.  Default ``"#eeeeee"``.

    Returns
    -------
    None
        The axis *ax* is modified in place.

    Raises
    ------
    ImportError
        If ``geopandas`` is not installed.
    ValueError
        If *cell_counts* is empty or contains invalid H3 cell indices.

    See Also
    --------
    h3_to_geodataframe : Build the underlying GeoDataFrame directly.
    plot_hex_heatmap : Matplotlib-only heatmap without geopandas.

    Examples
    --------
    >>> from collections import Counter
    >>> import matplotlib.pyplot as plt
    >>> from h3tools.viz import plot_h3_choropleth
    >>> import h3
    >>> counts = Counter({c: i + 1 for i, c in
    ...                   enumerate(h3.grid_disk("89195da49b7ffff", 1))})
    >>> fig, ax = plt.subplots(figsize=(8, 6))
    >>> plot_h3_choropleth(ax, counts, title="Event density")
    >>> plt.close()
    """
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise ImportError(
            "plot_h3_choropleth requires geopandas.  "
            "Install it with: pip install geopandas"
        ) from exc

    from h3tools.dataframe import h3_to_geodataframe

    if not cell_counts:
        raise ValueError("cell_counts must not be empty.")

    gdf = h3_to_geodataframe(cell_counts.keys(), cell_counts=cell_counts)

    gdf.plot(
        ax=ax,
        column="count",
        cmap=cmap,
        legend=legend,
        legend_kwds={"label": legend_label, "orientation": "vertical"},
        edgecolor=edgecolor,
        linewidth=linewidth,
        missing_kwds={"color": missing_color},
    )

    if title:
        ax.set_title(title, fontsize=12, pad=10)

    ax.set_axis_off()
