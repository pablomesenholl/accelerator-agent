"""Lightweight Matplotlib styling and figure export for the Beam Analyzer.

Call apply_style() before creating figures. Use a noninteractive backend (such as
Agg) for headless scripts; configure it before importing matplotlib.pyplot.
The caller chooses all output paths, data, units, and plot layouts.
"""

from pathlib import Path
import warnings

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.image import imread


COLORS = {
    "x": "#0072B2",        # horizontal: blue
    "y": "#D55E00",        # vertical: vermilion
    "z": "#009E73",        # longitudinal: bluish green
}
FIGSIZE_SINGLE = (3.4, 2.3)  # inches
FIGSIZE_WIDE = (7.0, 4.2)    # inches
_LOGO = Path(__file__).resolve().parent.parent / "assets" / "OPALX-logo.png"


def apply_style() -> None:
    """Set publication-oriented defaults; callers may override any rcParam."""
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "lines.linewidth": 1.7,
        "lines.markersize": 4,
        "axes.prop_cycle": mpl.cycler(color=list(COLORS.values())),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#B7BEC7",
        "grid.alpha": 0.30,
        "grid.linewidth": 0.6,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "text.usetex": False,
        "pdf.fonttype": 42,
    })


def _add_logo(fig: Figure, logo: bool | None):
    """Attach a temporary logo above the plotting area, if available."""
    if logo is False:
        return None
    if not _LOGO.is_file():
        if logo is True:
            warnings.warn(f"OPALX logo not found: {_LOGO}", stacklevel=2)
        return None
    try:
        image = imread(_LOGO)
    except (OSError, ValueError, SyntaxError) as exc:
        warnings.warn(f"Could not read OPALX logo: {exc}", stacklevel=2)
        return None

    width, height = fig.get_size_inches()
    image_height, image_width = image.shape[:2]
    logo_width_inches = min(0.75, 0.55 * image_width / image_height, 0.8 * width)
    logo_width = logo_width_inches / width
    logo_height = logo_width_inches * image_height / image_width / height
    ax = fig.add_axes([0.98 - logo_width, 1.01, logo_width, logo_height])
    ax.set_in_layout(False)  # Keep constrained_layout focused on the data axes.
    ax.imshow(image, aspect="equal")  # preserve original proportions
    ax.axis("off")
    return ax


def save_figure(
    fig: Figure,
    path: str | Path,
    *,
    dpi: int = 300,
    logo: bool | None = None,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Save PDF and PNG beside a caller-selected path; return (png, pdf).

    `path` is a filename stem or ends in .png/.pdf. No output root is assumed.
    logo=None uses the logo if available; True warns if missing; False omits it.
    Existing files are protected unless overwrite=True.
    """
    stem = Path(path)
    if stem.suffix.lower() in {".png", ".pdf"}:
        stem = stem.with_suffix("")
    elif stem.suffix:
        raise ValueError("Output path must be a stem, .png, or .pdf")
    if not stem.name or dpi <= 0:
        raise ValueError("Provide a nonempty filename and positive DPI")

    png, pdf = stem.with_suffix(".png"), stem.with_suffix(".pdf")
    if not overwrite and (png.exists() or pdf.exists()):
        raise FileExistsError(f"Figure already exists: {png} or {pdf}")
    stem.parent.mkdir(parents=True, exist_ok=True)

    logo_ax = _add_logo(fig, logo)
    try:
        for destination in (png, pdf):
            fig.savefig(
                destination, dpi=dpi, bbox_inches="tight", pad_inches=0.08,
                bbox_extra_artists=(logo_ax,) if logo_ax is not None else (),
            )
    finally:
        if logo_ax is not None:
            logo_ax.remove()
    return png, pdf
