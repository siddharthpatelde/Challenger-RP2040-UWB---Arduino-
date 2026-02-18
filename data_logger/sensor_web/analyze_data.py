import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ==========================================
# 1. CONFIGURATION
# ==========================================
plt.rcParams.update({
    "figure.figsize": (10, 6),
    "figure.dpi": 150,
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.5,
    "font.family": "serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def parse_filename(filename):
    """
    Extracts Nominal Distance and Target Rate from filename.
    Ex: '1.5m_10Hz.csv' -> (1.5, 10.0)
    """
    try:
        stem = filename.stem
        parts = stem.split("_")
        
        # Part 0: Distance (remove 'm')
        dist_str = parts[0].replace("m", "")
        
        # Part 1: Hz (remove 'Hz')
        rate_str = parts[1].replace("Hz", "")
        
        return float(dist_str), float(rate_str)
    except Exception:
        # If filename doesn't match pattern, return None
        return None, None

def analyze_folder(folder_path: Path):
    results = []
    
    # Get all CSVs and sort them so the table looks organized
    csv_files = sorted(folder_path.glob("*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {folder_path}")
        return None

    # Print Table Header
    print("\n" + "="*115)
    print(f"{'File':<25} | {'Tgt Hz':<8} | {'Act Hz':<8} | {'Avg ms':<8} | {'Mean Dist':<10} | {'Error':<8} | {'Std Dev':<8} | {'Samples':<8}")
    print("-" * 115)

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
        except Exception:
            continue

        # Skip if empty or wrong format
        if df.empty or 'Timestamp_ms' not in df.columns:
            continue
        
        # 1. Parse Target Info from Filename
        target_dist, target_hz = parse_filename(csv_file)
        if target_dist is None: 
            target_dist = 0.0 # Fallback if parsing fails
            target_hz = 0.0

        # 2. Calculate Timing & Frequency
        # Difference between rows in milliseconds
        df['dt_ms'] = df['Timestamp_ms'].diff()
        
        # Average time gap (ignoring the first NaN)
        avg_dt_ms = df['dt_ms'].mean()
        
        # Actual Frequency = 1000 ms / avg_gap_ms
        if avg_dt_ms > 0:
            actual_hz = 1000.0 / avg_dt_ms
        else:
            actual_hz = 0

        # 3. Calculate Distance Statistics
        mean_dist = df['Measured_Distance_m'].mean()
        std_dev = df['Measured_Distance_m'].std()
        
        # Accuracy Error (Mean - Target)
        error = mean_dist - target_dist

        # 4. Store Data
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

        # 5. Print Row to Console
        print(f"{csv_file.name:<25} | {target_hz:<8} | {actual_hz:<8.2f} | {avg_dt_ms:<8.2f} | {mean_dist:<10.4f} | {error:<8.4f} | {std_dev:<8.4f} | {len(df):<8}")

    print("="*115 + "\n")

    # Create DataFrame
    res_df = pd.DataFrame(results)
    
    # Save Summary CSV to the PARENT folder (next to the script, not inside CSVs)
    out_file = folder_path.parent / "UWB_Analysis_Summary.csv"
    res_df.to_csv(out_file, index=False)
    print(f"Summary table saved to: {out_file}")

    return res_df

def plot_frequency_saturation(df, out_dir):
    """
    Plots Target Hz vs Actual Hz to show Hardware Limits
    """
    if df is None or df.empty: return

    fig, ax = plt.subplots()
    
    # 1. Plot Ideal Line (y=x)
    max_hz = df['Target_Hz'].max()
    ax.plot([1, max_hz], [1, max_hz], 'k--', alpha=0.4, label="Ideal (Target = Actual)")

    # 2. Plot Grouped by Distance
    unique_dists = sorted(df['Target_Distance_m'].unique())
    
    for dist in unique_dists:
        subset = df[df['Target_Distance_m'] == dist].sort_values(by="Target_Hz")
        ax.plot(subset['Target_Hz'], subset['Actual_Hz'], marker='o', label=f"{dist}m Test")

    # 3. Formatting
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel("Target Frequency (Setting) [Hz]")
    ax.set_ylabel("Actual Measured Frequency [Hz]")
    ax.set_title("UWB Throughput Analysis: Target vs Actual Hz")
    ax.legend()
    
    # Annotate max speed
    max_actual = df['Actual_Hz'].max()
    ax.text(0.05, 0.9, f"Max Achieved: {max_actual:.1f} Hz", transform=ax.transAxes, 
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))

    fig.tight_layout()
    
    # Save Plot
    out_path = out_dir / "Frequency_Saturation_LogScale.png"
    fig.savefig(out_path)
    print(f"Saturation plot saved to: {out_path}")

# ==========================================
# 3. MAIN EXECUTION
# ==========================================
def main():
    # 1. Determine Folder Path
    # If user provides path in terminal: python analyze_data.py /path/to/CSVs
    if len(sys.argv) > 1:
        folder_path = Path(sys.argv[1]).resolve()
    else:
        # Automatic: Look for 'CSVs' folder next to this script
        folder_path = Path(__file__).parent.resolve() / "CSVs"

    if not folder_path.exists():
        print(f"Error: Folder not found: {folder_path}")
        print("Make sure your CSV files are in a folder named 'CSVs' or provide the path.")
        return

    print(f"Analyzing data in: {folder_path}")

    # 2. Run Analysis
    df = analyze_folder(folder_path)

    # 3. Generate Comparison Plots
    if df is not None:
        # Create a 'plots' folder for the analysis images
        out_dir = folder_path / "plots"
        out_dir.mkdir(exist_ok=True)
        
        plot_frequency_saturation(df, out_dir)

if __name__ == "__main__":
    main()