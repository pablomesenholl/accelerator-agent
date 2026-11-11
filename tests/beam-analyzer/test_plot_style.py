"""Headless export regressions; no OPALX data or simulation is needed."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HELPER = (
    Path(__file__).resolve().parents[2]
    / "src/skills/beam-analyzer/scripts/plot_style.py"
)
spec = importlib.util.spec_from_file_location("plot_style", HELPER)
plot_style = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plot_style)


class FigureExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(plt.close, "all")
        self.output = Path(self.temp.name)
        # Distinct colours let us check actual exported content without relying
        # on font rasterization or the appearance of the bundled logo.
        self.logo = self.output / "logo.png"
        plt.imsave(self.logo, np.tile([0.0, 1.0, 1.0], (20, 80, 1)))

    def assert_colour_visible(self, image, colour, minimum_width, minimum_height):
        mask = np.all(np.abs(image[:, :, :3] - colour) < 0.05, axis=2)
        y, x = np.where(mask)
        self.assertGreater(x.size, 0, "Expected artist is absent from the PNG")
        self.assertGreaterEqual(x.max() - x.min() + 1, minimum_width)
        self.assertGreaterEqual(y.max() - y.min() + 1, minimum_height)
        self.assertGreater(x.min(), 0, "Artist touches the export boundary")
        self.assertGreater(y.min(), 0, "Artist touches the export boundary")
        self.assertLess(x.max(), image.shape[1] - 1)
        self.assertLess(y.max(), image.shape[0] - 1)

    def check_legend_export(self, shared):
        for logo in (False, True):
            with self.subTest(shared=shared, logo=logo):
                fig, axes = plt.subplots(1, 2 if shared else 1, figsize=(7, 3), dpi=100)
                axes = np.atleast_1d(axes)
                for ax in axes:
                    ax.plot([0, 1], [0, 1], label="Measured")
                    ax.set(xlabel="Path length [m]", ylabel="RMS size [mm]")
                options = dict(framealpha=1, facecolor="magenta", edgecolor="magenta")
                if shared:
                    fig.subplots_adjust(bottom=0.30, wspace=0.40)
                    handles, labels = axes[0].get_legend_handles_labels()
                    legend = fig.legend(handles, labels, loc="upper center",
                                        bbox_to_anchor=(0.5, -0.02), **options)
                else:
                    legend = axes[0].legend(loc="upper left",
                                            bbox_to_anchor=(1.02, 1), **options)
                fig.canvas.draw()
                bounds = legend.get_window_extent(fig.canvas.get_renderer())
                original_axes = tuple(fig.axes)
                with patch.object(plot_style, "_LOGO", self.logo):
                    png, pdf = plot_style.save_figure(
                        fig, self.output / f"legend-{shared}-{logo}", dpi=100, logo=logo
                    )
                self.assertEqual(tuple(fig.axes), original_axes)
                image = plt.imread(png)
                self.assert_colour_visible(image, [1, 0, 1], bounds.width - 2, bounds.height - 2)
                if logo:
                    self.assert_colour_visible(image, [0, 1, 1], 60, 14)
                self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
                plt.close(fig)

    def test_outside_axes_legend(self):
        self.check_legend_export(shared=False)

    def test_shared_figure_legend(self):
        self.check_legend_export(shared=True)

    def test_repeated_exports_preserve_figure_and_existing_file_guard(self):
        fig, ax = plt.subplots(layout="constrained")
        ax.plot([0, 1], [0, 1], label="Measured")
        ax.legend()
        with patch.object(plot_style, "_LOGO", self.logo):
            for name in ("first", "second"):
                plot_style.save_figure(fig, self.output / name, dpi=100)
                self.assertEqual(fig.axes, [ax])
            with self.assertRaises(FileExistsError):
                plot_style.save_figure(fig, self.output / "first", dpi=100)
        self.assertEqual(fig.axes, [ax])


if __name__ == "__main__":
    unittest.main()
