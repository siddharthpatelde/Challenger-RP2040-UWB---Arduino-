import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# ==========================================
# 1. PLOT STYLING
# ==========================================
plt.rcParams.update({
    "figure.figsize": (10, 6),
    "figure.dpi": 150,
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": "serif",
    "font.size": 10
})

# ==========================================
# 2. PLOTTING LOGIC
# ==========================================
def plot_uwb_file(csv_path: Path):
    print(f"Processing: {csv_path.name}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if "Timestamp_ms" not in df.columns or "Measured_Distance_m" not in df.columns:
        print(f"Skipping {csv_path.name}: Missing required columns.")
        return

    # 1. Process Time
    t_ms = df["Timestamp_ms"].to_numpy()
    t_ms = t_ms - t_ms[0]
    t_s = t_ms / 1000.0

    # 2. Process Distance
    dist = df["Measured_Distance_m"].to_numpy()

    # 3. Calculate Moving Average
    window = max(5, len(df) // 50) 
    df["dist_smooth"] = df["Measured_Distance_m"].rolling(window=window, center=True).mean()

    # 4. Generate Title
    stem = csv_path.stem
    title = stem
    try:
        parts = stem.split("_")
        nominal_m = parts[0].replace("m", "")
        rate_hz = parts[1].replace("Hz", "")
        title = f"Target: {nominal_m}m @ {rate_hz}Hz"
    except:
        pass

    # 5. Create Plot
    fig, ax = plt.subplots()
    ax.plot(t_s, dist, linewidth=0.5, alpha=0.4, color="#4C8DFF", label="Raw Data")
    
    if not df["dist_smooth"].isna().all():
        ax.plot(t_s, df["dist_smooth"], linewidth=2.0, color="#004080", label=f"Moving Mean (N={window})")

    mean_val = df["Measured_Distance_m"].mean()
    std_val = df["Measured_Distance_m"].std()
    ax.axhline(mean_val, color='red', linestyle='--', alpha=0.7, label=f"Mean: {mean_val:.3f}m")

    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Distance form Origin [m]")
    ax.set_title(title)
    ax.legend(loc="upper right")
    
    stats_text = f"Mean: {mean_val:.4f} m\nStd Dev: {std_val:.4f} m\nSamples: {len(df)}"
    props = dict(boxstyle='round', facecolor='white', alpha=0.8)
    ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=props)

    fig.tight_layout()

    # 6. Save Plot inside 'CSVs/plots/'
    out_dir = csv_path.parent / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = out_dir / f"{stem}.png"
    fig.savefig(out_file)
    print(f"  -> Saved plot to: {out_file}")
    plt.close(fig)

# ==========================================
# 3. MAIN EXECUTION (UPDATED)
# ==========================================
def main():
    # A. If user drags a file onto the script or provides path
    if len(sys.argv) > 1:
        path = Path(sys.argv[1]).resolve()
        if path.is_dir():
            files = sorted(path.glob("*.csv"))
            for f in files: plot_uwb_file(f)
        else:
            plot_uwb_file(path)
    
    # B. AUTOMATIC MODE: Look in "CSVs" folder
    else:
        base_dir = Path(__file__).parent.resolve()
        
        # 1. Look inside the 'CSVs' folder (where web_log.py saves them)
        csv_folder = base_dir / "CSVs"
        found_files = []

        if csv_folder.exists():
            found_files.extend(sorted(csv_folder.glob("*.csv")))
        
        # 2. Also look in current folder just in case
        found_files.extend(sorted(base_dir.glob("*.csv")))

        if not found_files:
            print("No CSV files found in 'CSVs' folder or current directory.")
            return

        print(f"Found {len(found_files)} CSV files. Processing...")
        for f in found_files:
            plot_uwb_file(f)

if __name__ == "__main__":
    main()