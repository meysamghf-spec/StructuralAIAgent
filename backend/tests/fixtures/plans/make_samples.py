"""Regenerate the sample plans used by the plan-import tests: python tests/fixtures/plans/make_samples.py"""
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
SX, SY = [5.0, 4.0, 6.0], [4.5, 5.0]  # m
XS = [0.0, 5.0, 9.0, 15.0]
YS = [0.0, 4.5, 9.5]
MISSING = (2, 1)  # no column at C-3 (an opening)


def dxf() -> None:
    doc = ezdxf.new("R2010", setup=True); doc.header["$INSUNITS"] = 4
    doc.layers.add("A-GRID", linetype="CENTER"); m = doc.modelspace()
    k = 1000.0
    for i, x in enumerate(XS):
        m.add_line((x * k, -2500), (x * k, YS[-1] * k + 2500), dxfattribs={"layer": "A-GRID"})
        for yy in (-3000, YS[-1] * k + 3000):
            m.add_circle((x * k, yy), 450); m.add_text(str(i + 1), height=400).set_placement((x * k, yy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    for j, y in enumerate(YS):
        m.add_line((-2500, y * k), (XS[-1] * k + 2500, y * k), dxfattribs={"layer": "A-GRID"})
        for xx in (-3000, XS[-1] * k + 3000):
            m.add_circle((xx, y * k), 450); m.add_text("ABC"[j], height=400).set_placement((xx, y * k), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    for i, x in enumerate(XS):
        for j, y in enumerate(YS):
            if (i, j) != MISSING:
                m.add_lwpolyline([(x * k - 200, y * k - 200), (x * k + 200, y * k - 200), (x * k + 200, y * k + 200), (x * k - 200, y * k + 200)], close=True)
    for a, b in zip(XS, XS[1:]):
        m.add_linear_dim(base=(0, -1500), p1=(a * k, 0), p2=(b * k, 0)).render()
    doc.saveas(HERE / "sample_plan.dxf")


def _mpl(ax, with_text=True):
    for i, x in enumerate(XS):
        ax.plot([x, x], [-2, YS[-1] + 2], color="k", lw=0.8)
        if with_text:
            ax.text(x, -2.5, str(i + 1), ha="center", va="center", fontsize=12)
    for j, y in enumerate(YS):
        ax.plot([-2, XS[-1] + 2], [y, y], color="k", lw=0.8)
        if with_text:
            ax.text(-2.5, y, "ABC"[j], ha="center", va="center", fontsize=12)
    for i, x in enumerate(XS):
        for j, y in enumerate(YS):
            if (i, j) != MISSING:
                ax.add_patch(plt.Rectangle((x - 0.25, y - 0.25), 0.5, 0.5, color="k"))
    if with_text:
        for a, b, v in zip(XS, XS[1:], SX):
            ax.text((a + b) / 2, -1.2, f"{v * 1000:.0f}", ha="center", fontsize=10)
        for a, b, v in zip(YS, YS[1:], SY):
            ax.text(-1.2, (a + b) / 2, f"{v * 1000:.0f}", ha="center", fontsize=10)
    ax.set_xlim(-3.5, XS[-1] + 3); ax.set_ylim(-3.5, YS[-1] + 3); ax.set_aspect("equal"); ax.axis("off")


def pdf_png() -> None:
    plt.rcParams["pdf.fonttype"] = 42
    fig, ax = plt.subplots(figsize=(8, 6)); _mpl(ax); fig.savefig(HERE / "sample_plan.pdf"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 6)); _mpl(ax, with_text=False); fig.savefig(HERE / "sample_plan.png", dpi=100); plt.close(fig)


if __name__ == "__main__":
    dxf(); pdf_png()
