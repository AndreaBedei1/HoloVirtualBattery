"""Plot archived native force measurements; matplotlib is an optional tool dependency."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("docs/figures/holoocean_drag_units"))
    args = parser.parse_args()
    import matplotlib.pyplot as plt

    report = json.loads(args.report.read_text(encoding="utf-8"))
    records = report["records"]
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.3), layout="constrained")
    colors = ["#0072B2", "#D55E00", "#009E73"]
    rates = sorted({r["ticks_per_sec"] for r in records})
    for rate, color in zip(rates, colors, strict=True):
        points = sorted(
            [
                r
                for r in records
                if r["ticks_per_sec"] == rate
                and r["trial"] == 0
                and r["case"] in [f"current_x_{u:g}" for u in (0.1, 0.2, 0.4, 0.8)]
            ],
            key=lambda r: r["current_m_s"][0],
        )
        currents = [r["current_m_s"][0] for r in points]
        forces = [r["observed_drag_N"][0] for r in points]
        axes[0].plot(currents, forces, "o-", color=color, label=f"Runtime {rate} Hz")
        axes[1].plot(
            currents,
            [r["observed_expected_scale"] for r in points],
            "o-",
            color=color,
            label=f"Runtime {rate} Hz",
        )
    expected = [r["expected_drag_N"][0] for r in points]
    axes[0].plot(currents, expected, "k--", label="Source equation in SI")
    axes[0].set(yscale="log", xlabel="Current speed (m/s)", ylabel="Initial drag force (N)")
    axes[0].set_title("Absolute force; known UE damping removed")
    axes[0].legend(fontsize=9)
    axes[1].axhline(1, color="black", linestyle="--", label="Correct implementation: 1")
    axes[1].axhline(0.01, color="gray", linestyle=":", label="Missing unit conversion: 0.01")
    axes[1].set(
        yscale="log",
        ylim=(0.007, 1.6),
        xlabel="Current speed (m/s)",
        ylabel="Observed / SI source equation",
    )
    axes[1].set_title("No coefficients fitted to observations")
    axes[1].legend(fontsize=9)
    for ax in axes:
        ax.set_xticks([0.1, 0.2, 0.4, 0.8])
        ax.grid(True, alpha=0.25)
    fig.suptitle("HoloOcean 2.3.0 installed binary — implementation verification", fontsize=12)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(args.output.with_suffix("." + suffix), dpi=220, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
