import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# ------------------------------
# Anchor positions (meters)
# ------------------------------
ANCHORS = {
    "A1": (0.0, 0.27),
    "A2": (0.27, 0.0),
    "A3": (0.0, 0.0),  # Origin
}

def get_paths():
    base_dir = Path(__file__).parent.resolve()
    raw_csv_dir = base_dir / "sensor_web" / "CSVs"
    output_dir = base_dir / "sensor_web" / "conclusion_plots" / "xy_stability_each_file"
    output_dir.mkdir(parents=True, exist_ok=True)
    return raw_csv_dir, output_dir

def compute_global_limits(files, pad_ratio=0.05):
    xs, ys = [], []

    for f in files:
        df = pd.read_csv(f)
        xs.append(pd.to_numeric(df["X"], errors="coerce").to_numpy())
        ys.append(pd.to_numeric(df["Y"], errors="coerce").to_numpy())

    x_all = np.concatenate(xs)
    y_all = np.concatenate(ys)

    # ignore NaNs
    x_all = x_all[np.isfinite(x_all)]
    y_all = y_all[np.isfinite(y_all)]

    xmin, xmax = x_all.min(), x_all.max()
    ymin, ymax = y_all.min(), y_all.max()

    # padding
    xpad = (xmax - xmin) * pad_ratio if xmax > xmin else 0.1
    ypad = (ymax - ymin) * pad_ratio if ymax > ymin else 0.1

    return (xmin - xpad, xmax + xpad), (ymin - ypad, ymax + ypad)

def plot_xy_for_each_file():
    raw_csv_dir, out_dir = get_paths()

    if not raw_csv_dir.exists():
        print(f"Error: Folder not found at {raw_csv_dir}")
        return

    files = sorted(raw_csv_dir.glob("*.csv"))
    if not files:
        print(f"No CSV files found in: {raw_csv_dir}")
        return

    # compute same axis limits for all plots
    xlim, ylim = compute_global_limits(files, pad_ratio=0.05)

    for f in files:
        try:
            df = pd.read_csv(f)

            x = pd.to_numeric(df["X"], errors="coerce")
            y = pd.to_numeric(df["Y"], errors="coerce")
            mask = x.notna() & y.notna()
            x = x[mask].astype(float)
            y = y[mask].astype(float)

            mean_x = x.mean()
            mean_y = y.mean()

            fig, ax = plt.subplots(figsize=(7, 7), dpi=150)

            # raw scatter + mean marker
            ax.scatter(x, y, s=12, alpha=0.25)
            ax.plot(mean_x, mean_y, "r+", markersize=16, markeredgewidth=2, label="Mean")

            # anchors (red triangles) + labels
            for name, (ax_x, ax_y) in ANCHORS.items():
                ax.scatter(
                    ax_x, ax_y,
                    marker="^", s=140, color="red", zorder=5,
                    label="Anchors" if name == "A1" else None
                )
                ax.text(
                    ax_x + 0.02, ax_y + 0.02, name,
                    color="red", fontsize=12, fontweight="bold", zorder=6
                )

            ax.set_xlabel("X Position (m)")
            ax.set_ylabel("Y Position (m)")
            ax.set_title(f"XY Position Stability\n{f.name}")

            # fixed viewport (same for every file)
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)

            ax.grid(True, linestyle="--", alpha=0.4)
            ax.set_aspect("equal", adjustable="box")
            ax.legend()

            out_path = out_dir / f"{f.stem}_XY_Stability.png"
            fig.savefig(out_path, bbox_inches="tight")
            plt.close(fig)

            print(f"Saved: {out_path.name}")

        except Exception as e:
            print(f"Skipping {f.name}: {e}")

def main():
    print("--- XY Stability Plots (fixed size + anchors) ---")
    plot_xy_for_each_file()
    print("Done.")

if __name__ == "__main__":
    main()
