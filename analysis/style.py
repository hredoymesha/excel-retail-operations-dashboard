"""One plain chart style for the matplotlib figures."""
import matplotlib.pyplot as plt

COLOURS = dict(navy="#1F3A5F", teal="#2A7F8E", amber="#C98B2B", sky="#A3B4C6", slate="#5B6B7B", grey="#8895A3")


def apply_style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#B8C4D0", "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.color": "#E3E8EE", "grid.linewidth": 0.8,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": COLOURS["navy"], "figure.facecolor": "white",
        "axes.axisbelow": True,
    })
