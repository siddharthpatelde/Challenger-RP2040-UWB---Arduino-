import serial
import serial.tools.list_ports
import json
import threading
import time
import numpy as np
from scipy.optimize import least_squares
import matplotlib.pyplot as plt

# ==========================================
# 1. CONFIGURATION & COORDINATES
# ==========================================
# Define where your anchors are physically located (X, Y) in meters
ANCHOR_CONFIG = {
    'A1': {'serial': 'DF622C6417244126', 'pos': np.array([1.6, 0.0])},
    'A2': {'serial': 'DF622C64171D4E26', 'pos': np.array([0.0, 0.0])},
    'A3': {'serial': 'DF622C64177E5827', 'pos': np.array([0, 1.6])}
}

SPEED_OF_LIGHT = 299792458.0
# DW3000 time unit: 1 tick ≈ 15.65e-12 seconds
TICK_TO_SEC = 1.0 / (128 * 499.2e6) 

# Shared data structure to store incoming timestamps
# format: { seq_num: { 'A1': ts, 'A2': ts, 'A3': ts } }
packet_buffer = {}
buffer_lock = threading.Lock()

# ==========================================
# 2. AUTOMATIC PORT DISCOVERY
# ==========================================
def find_anchor_ports():
    found_ports = {}
    ports = serial.tools.list_ports.comports()
    print("Searching for Anchors...")
    for p in ports:
        for aid, cfg in ANCHOR_CONFIG.items():
            if p.serial_number == cfg['serial']:
                print(f"Match: {aid} found on {p.device}")
                found_ports[aid] = p.device
    return found_ports

# ==========================================
# 3. SERIAL READER THREAD
# ==========================================
def read_anchor_thread(aid, port_name):
    try:
        ser = serial.Serial(port_name, 115200, timeout=1)
        while True:
            line = ser.readline().decode('utf-8').strip()
            if line.startswith('{'):
                try:
                    data = json.loads(line)
                    seq = data['seq']
                    # Convert Hex String timestamp to integer
                    ts = int(data['ts'], 16)
                    
                    with buffer_lock:
                        if seq not in packet_buffer:
                            packet_buffer[seq] = {}
                        packet_buffer[seq][aid] = ts
                        
                        # Clean up old packets (keep buffer small)
                        if len(packet_buffer) > 50:
                            oldest = min(packet_buffer.keys())
                            del packet_buffer[oldest]
                except:
                    pass
    except Exception as e:
        print(f"Error on {aid}: {e}")

# ==========================================
# 4. TDOA SOLVER (NON-LINEAR LEAST SQUARES)
# ==========================================
def solve_position(anchors_present, timestamps):
    # Reference Anchor is always the first one in the list
    ref_aid = anchors_present[0]
    ref_pos = ANCHOR_CONFIG[ref_aid]['pos']
    ref_ts = timestamps[ref_aid]
    
    def equations(p):
        x, y = p
        errors = []
        for i in range(1, len(anchors_present)):
            aid = anchors_present[i]
            pos = ANCHOR_CONFIG[aid]['pos']
            ts = timestamps[aid]
            
            # Measured Distance Difference (TDOA * Speed of Light)
            delta_t = (ts - ref_ts) * TICK_TO_SEC
            measured_diff = delta_t * SPEED_OF_LIGHT
            
            # Geometric Distance Difference
            dist_i = np.sqrt((x - pos[0])**2 + (y - pos[1])**2)
            dist_ref = np.sqrt((x - ref_pos[0])**2 + (y - ref_pos[1])**2)
            expected_diff = dist_i - dist_ref
            
            errors.append(expected_diff - measured_diff)
        return errors

    # Start guess at center of anchors
    initial_guess = np.mean([ANCHOR_CONFIG[a]['pos'] for a in anchors_present], axis=0)
    res = least_squares(equations, initial_guess)
    return res.x

# ==========================================
# 5. MAIN EXECUTION & PLOTTING
# ==========================================
ports = find_anchor_ports()
if len(ports) < 3:
    print("Error: Could not find all 3 anchors. Check USB connections.")
    exit()

for aid, port in ports.items():
    t = threading.Thread(target=read_anchor_thread, args=(aid, port), daemon=True)
    t.start()

# Setup Plotting
plt.ion()
fig, ax = plt.subplots(figsize=(8, 8))
anchor_x = [cfg['pos'][0] for cfg in ANCHOR_CONFIG.values()]
anchor_y = [cfg['pos'][1] for cfg in ANCHOR_CONFIG.values()]
ax.scatter(anchor_x, anchor_y, marker='^', s=100, color='red', label='Anchors')
for aid, cfg in ANCHOR_CONFIG.items():
    ax.text(cfg['pos'][0], cfg['pos'][1], aid)

tag_plot = ax.scatter([], [], color='blue', s=50, label='Tag')
ax.set_xlim(-2, 8)
ax.set_ylim(-2, 8)
ax.legend()
ax.grid(True)

print("Starting solver...")
try:
    while True:
        target_seq = None
        with buffer_lock:
            # Find a sequence number that has data from all 3 anchors
            for seq, data in packet_buffer.items():
                if len(data) == 3:
                    target_seq = seq
                    break
        
        if target_seq is not None:
            with buffer_lock:
                ts_data = packet_buffer.pop(target_seq)
            
            # Solve for X, Y
            pos = solve_position(['A1', 'A2', 'A3'], ts_data)
            
            print(f"Seq {target_seq} -> Pos: X={pos[0]:.2f}, Y={pos[1]:.2f}")
            
            # Update Plot
            tag_plot.set_offsets([pos[0], pos[1]])
            fig.canvas.draw()
            fig.canvas.flush_events()
        
        time.sleep(0.01)

except KeyboardInterrupt:
    print("Closing...")