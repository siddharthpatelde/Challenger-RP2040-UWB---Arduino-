import serial
import time
import csv
import os

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/cu.usbmodem1201' # Check your port!
BAUD_RATE = 115200
SAMPLES_TO_COLLECT = 1000  # Will stop automatically after this many
# ---------------------

def collect_data():
    # 1. Determine where to save the file (same folder as this script)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. Connect to Serial
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"Error connecting to port: {e}")
        return

    # 3. Get Filename
    filename_input = input("Enter filename (e.g., 1m_10Hz): ").strip()
    if not filename_input.endswith(".csv"):
        filename_input += ".csv"
    
    # Create the full path
    full_path = os.path.join(script_dir, filename_input)

    print(f"Starting collection... Target: {SAMPLES_TO_COLLECT} samples.")
    print(f"Saving to: {full_path}")
    print("Waiting for data stream...")

    data_points = []
    
    # Flush old buffer to ensure fresh data
    ser.reset_input_buffer()

    # 4. Collection Loop
    while len(data_points) < SAMPLES_TO_COLLECT:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            # Parse the line (Expecting: "timestamp,distance")
            if ',' in line:
                parts = line.split(',')
                if len(parts) == 2:
                    t_stamp = parts[0]
                    dist = parts[1]
                    
                    data_points.append([t_stamp, dist])
                    
                    # --- LIVE PROGRESS FEEDBACK ---
                    # Print every 10 samples so you see it moving
                    count = len(data_points)
                    if count % 10 == 0:
                        print(f"Collected {count}/{SAMPLES_TO_COLLECT} | Last value: {dist}m")
            
        except KeyboardInterrupt:
            print("\nStopped early by user.")
            break
        except Exception as e:
            print(f"Error reading: {e}")

    # 5. Save Data
    with open(full_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp_ms", "Measured_Distance_m"]) # Header
        writer.writerows(data_points)

    print(f"\nDONE! Saved {len(data_points)} samples to:")
    print(full_path)
    ser.close()

if __name__ == "__main__":
    while True:
        collect_data()
        cont = input("\nDo another experiment? (y/n): ")
        if cont.lower() != 'y':
            break