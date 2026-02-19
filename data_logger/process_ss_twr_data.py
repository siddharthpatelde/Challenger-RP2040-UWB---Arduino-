import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "figure.dpi": 150,
    "figure.figsize": (8, 6)
})

def get_paths():
    base_dir = Path(__file__).parent.resolve()
    # We only need the raw CSVs folder now
    raw_csv_dir = base_dir / "CSVs"
    output_dir = base_dir / "conclusion_plots"
    output_dir.mkdir(exist_ok=True)
    return raw_csv_dir, output_dir

# ==========================================
# 2. DATA LOADING & GENERATION
# ==========================================
def load_and_process_data():
    raw_csv_dir, _ = get_paths()
    
    if not raw_csv_dir.exists():
        print(f"Error: CSV folder not found at {raw_csv_dir}")
        return None, None
    
    print("Reading raw CSV files...")
    
    # Lists to store data
    all_raw_data = []
    summary_list = []
    
    files = sorted(raw_csv_dir.glob("*.csv"))
    
    for f in files:
        try:
            # 1. Parse filename: e.g., "1m_10Hz.csv"
            parts = f.stem.split('_')
            dist_true = float(parts[0].replace('m', ''))
            target_hz = float(parts[1].replace('Hz', ''))
            
            # 2. Read Raw Data
            df = pd.read_csv(f)
            
            # 3. Calculate metrics for this specific file
            # Timing/Frequency
            df['dt_ms'] = df['Timestamp_ms'].diff()
            avg_dt = df['dt_ms'].mean()
            actual_hz = 1000.0 / avg_dt if avg_dt > 0 else 0
            
            # Distance Stats
            mean_dist = df['Measured_Distance_m'].mean()
            std_dev = df['Measured_Distance_m'].std()
            
            # Add to Summary List
            summary_list.append({
                'Target_Distance_m': dist_true,
                'Target_Hz': target_hz,
                'Actual_Hz': actual_hz,
                'Measured_Mean_m': mean_dist,
                'Std_Dev_m': std_dev
            })
            
            # 4. Add to Raw Data List (for Boxplot)
            df['True_Distance'] = dist_true
            df['Target_Hz'] = target_hz
            df['Error'] = df['Measured_Distance_m'] - dist_true
            all_raw_data.append(df)
            
        except Exception as e:
            print(f"Skipping {f.name}: {e}")

    # Create DataFrames
    if all_raw_data:
        df_raw = pd.concat(all_raw_data, ignore_index=True)
        df_summary = pd.DataFrame(summary_list)
        return df_summary, df_raw
    else:
        return None, None

# ==========================================
# 3. PLOTTING FUNCTIONS
# ==========================================

def plot_frequency_saturation(df, out_dir):
    fig, ax = plt.subplots()
    
    distances = sorted(df['Target_Distance_m'].unique())
    # Create a distinct color for each distance
    colors = sns.color_palette("husl", len(distances))
    
    # Plot Ideal Line
    ax.plot([1, 10000], [1, 10000], 'k--', alpha=0.5, label="Ideal")
    
    for i, dist in enumerate(distances):
        subset = df[df['Target_Distance_m'] == dist].sort_values('Target_Hz')
        ax.plot(subset['Target_Hz'], subset['Actual_Hz'], marker='o', 
                label=f"{dist}m", color=colors[i], linewidth=2, alpha=0.8)
        
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel("Target Update Rate (Hz)")
    ax.set_ylabel("Actual Measured Rate (Hz)")
    ax.set_title("Hardware Limitation: Update Rate Saturation")
    ax.legend(title="Distance")
    ax.grid(True, which="both", ls="--", alpha=0.4)
    
    fig.savefig(out_dir / "1_Frequency_Saturation.png", bbox_inches='tight')
    plt.close()

def plot_error_boxplot(df_raw, out_dir):
    if df_raw.empty: return

    fig, ax = plt.subplots(figsize=(10, 6))
    
    sns.boxplot(data=df_raw, x='True_Distance', y='Error', hue='True_Distance', 
                palette="coolwarm", legend=False, ax=ax, showfliers=False)
    
    ax.axhline(0, color='red', linestyle='--', linewidth=1.5, label="Ideal")
    ax.set_xlabel("True Distance (m)")
    ax.set_ylabel("Measurement Error (m)")
    ax.set_title("Measurement Error Distribution vs. Distance")
    
    fig.savefig(out_dir / "2_Error_Distribution_Boxplot.png", bbox_inches='tight')
    plt.close()

def plot_precision_degradation(df_summary, out_dir):
    fig, ax = plt.subplots()
    
    # Average StdDev across all frequencies for each distance
    grouped = df_summary.groupby('Target_Distance_m')['Std_Dev_m'].mean()
    
    bars = ax.bar(grouped.index.astype(str), grouped.values, color='skyblue', edgecolor='black')
    
    ax.set_xlabel("True Distance (m)")
    ax.set_ylabel("Standard Deviation (m)")
    ax.set_title("Precision Degradation over Distance")
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}m', ha='center', va='bottom', fontsize=10)

    fig.savefig(out_dir / "3_Precision_Degradation.png", bbox_inches='tight')
    plt.close()

def plot_linearity(df_summary, out_dir):
    fig, ax = plt.subplots()
    
    # Take mean measured distance across all frequencies
    grouped = df_summary.groupby('Target_Distance_m')['Measured_Mean_m'].mean()
    
    x = grouped.index
    y = grouped.values
    
    # Plot Ideal Line (Start to End)
    ax.plot([min(x), max(x)], [min(x), max(x)], 'k--', label="Ideal Linearity", alpha=0.5)
    
    # Plot Actual
    ax.plot(x, y, 'ro-', label="Measured Mean", linewidth=2)
    
    ax.set_xlabel("True Distance (m)")
    ax.set_ylabel("Measured Distance (m)")
    ax.set_title("System Linearity Check")
    ax.legend()
    
    fig.savefig(out_dir / "4_System_Linearity.png", bbox_inches='tight')
    plt.close()

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
def main():
    print("--- Regenerating Conclusion Plots ---")
    _, out_dir = get_paths()
    
    # 1. Process Data from Scratch (Ensures all files are included)
    df_sum, df_raw = load_and_process_data()
    
    if df_sum is None:
        print("No data found!")
        return

    # 2. Generate Plots
    plot_frequency_saturation(df_sum, out_dir)
    plot_error_boxplot(df_raw, out_dir)
    plot_precision_degradation(df_sum, out_dir)
    plot_linearity(df_sum, out_dir)
    
    print(f"\nSuccess! Check the folder: {out_dir}")

if __name__ == "__main__":
    main()