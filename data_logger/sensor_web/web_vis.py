import serial
import serial.tools.list_ports
import json
import threading
import numpy as np
import matplotlib.pyplot as plt
from time import sleep
from scipy.optimize import least_squares


# ==========================================
# 1. CONFIGURATION (Matching your real setup)
# ==========================================
ANCHOR_CONFIG = {
    'A1': {'serial': 'DF622C6417244126', 'pos': np.array([0.0, 0.0])},
    'A2': {'serial': 'DF622C64171D4E26', 'pos': np.array([1.2, 0.0])},
    'A3': {'serial': 'DF622C64177E5827', 'pos': np.array([0.0, 1.2])}
}

# Global dictionary to store the latest distances from each anchor
latest_distances = {'A1': None, 'A2': None, 'A3': None}
data_lock = threading.Lock()

# ==========================================
# 2. SERIAL PORT AUTO-DETECTION
# ==========================================
def get_anchor_ports():
    found_ports = {}
    ports = serial.tools.list_ports.comports()
    print("--- Scanning COM Ports ---")
    for p in ports:
        for aid, cfg in ANCHOR_CONFIG.items():
            if p.serial_number == cfg['serial']:
                print(f"Found {aid} on {p.device}")
                found_ports[aid] = p.device
    return found_ports

# ==========================================
# 3. SERIAL DATA READER THREAD
# ==========================================
def anchor_reader(aid, port):
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith('{'):
                try:
                    data = json.loads(line)
                    with data_lock:
                        latest_distances[aid] = float(data['dist'])
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass
    except Exception as e:
        print(f"Error reading {aid}: {e}")

# ==========================================
# 4. MATH: TRILATERATION (Ax = b)
# ==========================================

def calculate_tag_position(dist_dict):
    """
    Implements Non-linear Least Squares Trilateration.
    This finds the 'Best Fit' position that minimizes the error 
    between all three anchor distances simultaneously.
    """
    try:
        # Check if we have data for all anchors
        if any(v is None for v in dist_dict.values()):
            return None

        # 1. Prepare Anchor Positions and Measured Distances
        # We pull these into lists for easier processing
        anchors = np.array([
            ANCHOR_CONFIG['A1']['pos'],
            ANCHOR_CONFIG['A2']['pos'],
            ANCHOR_CONFIG['A3']['pos']
        ])
        
        measured_dists = np.array([
            dist_dict['A1'],
            dist_dict['A2'],
            dist_dict['A3']
        ])

        # 2. Define the Residual Function (The 'Trigonometry' error)
        # This function calculates: (Geometric Distance - Measured Distance)
        def residuals(p):
            # p is the current guess of [x, y]
            # np.linalg.norm calculates the straight-line distance to each anchor
            return [np.linalg.norm(p - anchors[i]) - measured_dists[i] for i in range(3)]

        # 3. Initial Guess
        # We start the search at the average of the anchor positions
        initial_guess = np.mean(anchors, axis=0)

        # 4. Solve for Position (The Optimizer)
        # least_squares 'squeezes' the point until the error is as small as possible
        result = least_squares(residuals, initial_guess, ftol=1e-4, xtol=1e-4)

        # Return the optimized [xt, yt]
        return result.x

    except Exception as e:
        # If the math fails (e.g., distances are physically impossible), return None
        return None
# ==========================================
# 5. MAIN EXECUTION & PLOTTING
# ==========================================
ports = get_anchor_ports()
if len(ports) < 3:
    print(f"Error: Found only {len(ports)} anchors. Need 3. Check USB cables!")
    exit()

# Start background threads
for aid, port_name in ports.items():
    t = threading.Thread(target=anchor_reader, args=(aid, port_name), daemon=True)
    t.start()

# Initialize Plot
plt.ion()
fig, ax = plt.subplots(figsize=(7, 7))
ax.set_title("UWB Real-time Tag Tracking (Least Squares)")
ax.set_xlabel("X (meters)")
ax.set_ylabel("Y (meters)")

# Plot Anchors
for aid, cfg in ANCHOR_CONFIG.items():
    ax.scatter(cfg['pos'][0], cfg['pos'][1], marker='^', s=150, color='red', zorder=5)
    ax.text(cfg['pos'][0] + 0.05, cfg['pos'][1] + 0.05, aid, color='red', fontweight='bold')

# Tag Point
tag_dot, = ax.plot([], [], 'bo', markersize=12, label="Tag", zorder=10)
ax.legend()
ax.grid(True, linestyle='--', alpha=0.7)
ax.set_xlim(-2, 4) # Slightly wider limits
ax.set_ylim(-2, 4)

print("\nSystem Running. Searching for data from all 3 anchors...")

try:
    while True:
        with data_lock:
            current_dists = latest_distances.copy()
        
        # --- DIAGNOSTIC: Print status if data is missing ---
        missing = [aid for aid, dist in current_dists.items() if dist is None]
        if missing:
            print(f"Waiting for: {', '.join(missing)}...", end='\r')
        else:
            pos = calculate_tag_position(current_dists)

            if pos is not None:
                print(f"Data OK! -> A1:{current_dists['A1']:.2f} A2:{current_dists['A2']:.2f} A3:{current_dists['A3']:.2f} | Pos: X={pos[0]:.2f}, Y={pos[1]:.2f}      ")
                
                tag_dot.set_data([pos[0]], [pos[1]])
                
                # Force Matplotlib to update the window properly
                fig.canvas.draw()
                fig.canvas.flush_events()
            
        plt.pause(0.01) 
        sleep(0.05)

except KeyboardInterrupt:
    print("\nStopping...")