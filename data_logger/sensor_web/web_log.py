import serial
import serial.tools.list_ports
import json
import threading
import numpy as np
import csv
import time
from pathlib import Path
from scipy.optimize import least_squares

# ==========================================
# 1. CONFIGURATION
# ==========================================
# WARNING: Ensure these match your REAL WORLD measurements in METERS.
# Currently set to a small 27cm triangle.
ANCHOR_CONFIG = {
    'A1': {'serial': 'DF622C6417244126', 'pos': np.array([0.0, 0.27])},
    'A2': {'serial': 'DF622C64171D4E26', 'pos': np.array([0.27, 0.0])},
    'A3': {'serial': 'DF622C64177E5827', 'pos': np.array([0.0, 0.0])} # Origin
}

latest_distances = {'A1': None, 'A2': None, 'A3': None}
data_lock = threading.Lock()

# ==========================================
# 2. LOGGER CLASS
# ==========================================
class ExperimentLogger:
    def __init__(self, target_dist, target_hz, sample_limit):
        self.limit = sample_limit
        self.count = 0
        self.start_time = time.time()
        
        self.base_dir = Path(__file__).parent.resolve() / "CSVs"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Filename example: "1.5m_10Hz.csv"
        filename = f"{target_dist}m_{target_hz}Hz.csv"
        self.filepath = self.base_dir / filename
        1
        self.f = open(self.filepath, 'w', newline='')
        self.writer = csv.writer(self.f)
        
        # Header for the plotting script
        self.writer.writerow(["Timestamp_ms", "Measured_Distance_m", "X", "Y"])
        
        print(f"\n[LOGGER] File: {self.filepath}")
        print(f"[LOGGER] Target: {self.limit} samples @ {target_hz} Hz")

    def log_data(self, x, y):
        if self.count < self.limit:
            # 1. Get current time in milliseconds
            t_ms = int(time.time() * 1000)
            
            # 2. COMPUTE DISTANCE FOR PLOT
            # This calculates the Euclidean distance from the Origin (0,0) (Anchor A3)
            # If you are testing "1 meter accuracy", place tag 1m from Anchor 3.
            dist_from_origin = np.sqrt(x**2 + y**2)
            
            # 3. Write to CSV
            self.writer.writerow([t_ms, dist_from_origin, x, y])
            
            self.count += 1
            return False
        else:
            return True

    def close(self):
        self.f.close()
        print(f"\n[LOGGER] Finished. Saved to {self.filepath}")

# ==========================================
# 3. MATH ALGORITHMS
# ==========================================
def calculate_tag_position(dist_dict):
    """
    Solves the system of equations using Non-Linear Least Squares.
    Equation: (x-ax)^2 + (y-ay)^2 = measured_dist^2
    """
    try:
        # If any anchor is missing data, we cannot triangulate (in this simple version)
        if any(v is None for v in dist_dict.values()): return None
        
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

        # The Error Function: (Calculated Distance - Measured Distance)
        def residuals(p):
            # p[0] is x, p[1] is y
            # We calculate distance from guess 'p' to each anchor
            theoretical_dists = np.linalg.norm(anchors - p, axis=1)
            # We return the error array
            return theoretical_dists - measured_dists

        # Initial guess: Start at the average position of all anchors
        initial_guess = np.mean(anchors, axis=0)

        # Optimize!
        res = least_squares(residuals, initial_guess, ftol=1e-4, xtol=1e-4)
        
        # Returns [x, y]
        return res.x
    except Exception:
        return None

# ==========================================
# 4. SERIAL READERS
# ==========================================
def get_anchor_ports():
    found_ports = {}
    ports = serial.tools.list_ports.comports()
    print("--- Scanning ---")
    for p in ports:
        for aid, cfg in ANCHOR_CONFIG.items():
            if p.serial_number == cfg['serial']:
                print(f"Found {aid} on {p.device}")
                found_ports[aid] = p.device
    return found_ports

def anchor_reader(aid, port):
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        while True:
            # Read line, decode, parse JSON
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith('{'):
                try:
                    data = json.loads(line)
                    with data_lock:
                        latest_distances[aid] = float(data['dist'])
                except:
                    pass
    except Exception as e:
        print(f"Error {aid}: {e}")

# ==========================================
# 5. MAIN LOOP
# ==========================================
if __name__ == "__main__":
    print("\n=== UWB DATA LOGGER ===")
    try:
        u_dist = input("Distance Label (e.g. 1.0): ").strip()
        u_hz   = float(input("Target Hz (e.g. 10): ").strip())
        u_lim  = int(input("Sample Limit (e.g. 1000): ").strip())
        
        sleep_time = 1.0 / u_hz
    except ValueError:
        print("Error: Please enter numbers.")
        exit()

    ports = get_anchor_ports()
    if len(ports) < 3:
        print(f"Error: Need 3 anchors. Found {len(ports)}.")
        exit()

    for aid, port in ports.items():
        threading.Thread(target=anchor_reader, args=(aid, port), daemon=True).start()

    logger = ExperimentLogger(u_dist, u_hz, u_lim)
    
    print("\nStarting Log... (Move tag to position now)")
    time.sleep(1) # Give a second to settle

    try:
        while True:
            # 1. Snapshot the latest serial data
            with data_lock:
                current_dists = latest_distances.copy()
            
            # 2. Calculate Position
            pos = calculate_tag_position(current_dists)

            # 3. If valid, log it
            if pos is not None:
                x, y = pos[0], pos[1]
                
                print(f"Pos: X={x:.2f}, Y={y:.2f} | Count: {logger.count}/{logger.limit}   ", end='\r')
                
                finished = logger.log_data(x, y)
                if finished:
                    break
            
            # 4. Control Sampling Rate
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        logger.close()