import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ---- Configuration ----
plt.rcParams.update({
    "figure.figsize": (10, 6),
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.5,
    "font.family": "serif",
})

def parse_filename(filename):
    """
    Extracts Nominal Distance and Target Rate from filename.
    Ex: '1m_10Hz.csv' -> (1.0, 10.0)
    """
    try:
        stem = filename.stem
        parts = stem.split("_")
        dist_str = parts[0].replace("m", "")
        rate_str = parts[1].replace("Hz", "")
        return float(dist_str), float(rate_str)
    except Exception as e:
        print(f"Warning: Could not parse filename {filename.name}")
        return None, None

def analyze_folder(folder_path: Path):
    results = []
    
    csv_files = sorted(folder_path.glob("*.csv"))
    if not csv_files:
        print("No CSV files found.")
        return None

    print(f"{'File':<20} | {'Target Hz':<10} | {'Actual Hz':<10} | {'Mean Dist (m)':<15} | {'Std Dev (m)':<15}")
    print("-" * 85)

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        
        # 1. Parse Metadata
        target_dist, target_hz = parse_filename(csv_file)
        if target_dist is None: continue

        # 2. Calculate Frequency
        # Calculate time difference between consecutive samples
        df['dt_ms'] = df['Timestamp_ms'].diff()
        
        # Average time gap (ignoring the first NaN)
        avg_dt_ms = df['dt_ms'].mean()
        
        # Actual Frequency = 1000 ms / avg_dt_ms
        if avg_dt_ms > 0:
            actual_hz = 1000.0 / avg_dt_ms
        else:
            actual_hz = 0

        # 3. Calculate Accuracy & Precision
        mean_dist = df['Measured_Distance_m'].mean()
        std_dev = df['Measured_Distance_m'].std()
        
        # Calculate Error (Accuracy)
        error = mean_dist - target_dist

        # Store results
        results.append({
            "File": csv_file.name,
            "Target_Distance_m": target_dist,
            "Target_Hz": target_hz,
            "Actual_Hz": round(actual_hz, 2),
            "Avg_Delta_ms": round(avg_dt_ms, 2),
            "Measured_Mean_m": round(mean_dist, 4),
            "Error_m": round(error, 4),
            "Std_Dev_m": round(std_dev, 4),
            "Samples": len(df)
        })

        print(f"{csv_file.stem:<20} | {target_hz:<10} | {actual_hz:<10.2f} | {mean_dist:<15.4f} | {std_dev:<15.4f}")

    # FIXED: Create DataFrame directly from list of dicts
    res_df = pd.DataFrame(results)
    
    # Save Summary
    out_file = folder_path.parent / "UWB_Analysis_Summary.csv"
    res_df.to_csv(out_file, index=False)
    print(f"\nSummary saved to: {out_file}")

    return res_df

def plot_frequency_saturation(df, out_dir):
    """
    Plots Target Hz vs Actual Hz to show the hardware limit.
    """
    if df is None or df.empty:
        print("No data to plot.")
        return

    unique_dists = sorted(df['Target_Distance_m'].unique())

    fig, ax = plt.subplots()
    
    # Plot Identity line (Ideal case)
    max_target = df['Target_Hz'].max()
    ax.plot([1, max_target], [1, max_target], 'k--', label="Ideal (Target=Actual)", alpha=0.5)

    for dist in unique_dists:
        subset = df[df['Target_Distance_m'] == dist].sort_values(by="Target_Hz")
        ax.plot(subset['Target_Hz'], subset['Actual_Hz'], marker='o', label=f"{dist}m Test")

    ax.set_xscale('log') 
    ax.set_yscale('log')
    
    ax.set_xlabel("Target Frequency (Setting)")
    ax.set_ylabel("Actual Measured Frequency (Hz)")
    ax.set_title("UWB Data Rate Saturation Analysis")
    ax.legend()
    ax.grid(True, which="both", ls="--", alpha=0.4)
    
    out_path = out_dir / "Frequency_Saturation.png"
    fig.savefig(out_path)
    print(f"Saved Frequency Plot to {out_path}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python analyze_uwb_data.py <folder_with_csvs>")
        sys.exit(1)

    folder_path = Path(sys.argv[1]).resolve()
    if not folder_path.is_dir():
        # Handle case where user points to a file instead of folder
        folder_path = folder_path.parent

    # 1. Analyze and create table
    df = analyze_folder(folder_path)

    # 2. Generate saturation plot
    if df is not None:
        out_dir = folder_path.parent / "plots"
        out_dir.mkdir(exist_ok=True)
        plot_frequency_saturation(df, out_dir)

if __name__ == "__main__":
    main()