#!/usr/bin/env python3
"""
Plot UWB distance logs of the form:

Timestamp_ms,Measured_Distance_m
13365,12.326
...

Usage:
    python plot_uwb_logs.py path/to/1m_10Hz.csv
    python plot_uwb_logs.py data_logger/             # plots all *.csv in folder
"""

import sys
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# ---- basic style (blue-ish, similar to your LaTeX look) ----
plt.rcParams.update({
    "figure.figsize": (8, 4.5),
    "figure.dpi": 150,
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": "serif",
})


def plot_uwb_file(csv_path: Path, out_dir: Path) -> None:
    print(f"Processing {csv_path.name} ...")

    df = pd.read_csv(csv_path)

    # Time: shift so that first sample is at t = 0 s
    t_ms = df["Timestamp_ms"].to_numpy()
    t_ms = t_ms - t_ms[0]
    t_s = t_ms / 1000.0

    dist = df["Measured_Distance_m"].to_numpy()

    window = max(5, len(df) // 50)
    df["dist_smooth"] = df["Measured_Distance_m"].rolling(window=window,
                                                          center=True).mean()

    stem = csv_path.stem
    title = stem
    try:
        nominal_m = stem.split("m_")[0].replace("m", "")
        rate_hz = stem.split("_")[1].replace("Hz", "")
        title = f"{nominal_m} m @ {rate_hz} Hz"
    except Exception:
        pass

    fig, ax = plt.subplots()
    ax.plot(t_s, dist, linewidth=0.9, alpha=0.5,
            color="#4C8DFF", label="Raw distance")

    if not df["dist_smooth"].isna().all():
        ax.plot(t_s, df["dist_smooth"], linewidth=1.8,
                color="#0050A8", label="Moving mean")

    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Distance [m]")
    ax.set_title(title)
    ax.legend(loc="best")
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{stem}.png"
    fig.savefig(out_file)
    print(f"  → saved figure to {out_file}")
    plt.close(fig)


def main():
    if len(sys.argv) != 2:
        print("Usage: python plot_uwb_logs.py <csv-file-or-folder>")
        sys.exit(1)

    path = Path(sys.argv[1]).resolve()

    if path.is_dir():
        # Save all plots into <folder>/plots/
        out_dir = path.parent / "plots"
        csv_files = sorted(path.glob("*.csv"))
        if not csv_files:
            print("No *.csv files found in", path)
            return
        for csv_file in csv_files:
            plot_uwb_file(csv_file, out_dir)
    else:
        # Single file → <that_folder>/plots/
        out_dir = path.parent / "plots"
        plot_uwb_file(path, out_dir)



if __name__ == "__main__":
    main()
