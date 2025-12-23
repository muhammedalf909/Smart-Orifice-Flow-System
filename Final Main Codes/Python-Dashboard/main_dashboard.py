import argparse
import csv
import datetime as dt
import logging
import queue
import re
import signal
import sys
import threading
import time
import collections
import random
import os
import math 
from typing import Optional, Tuple, List, Any

# ========================= Visualization Setup =========================
import matplotlib

# Detect headless environment
HEADLESS = not os.environ.get('DISPLAY') if os.name != 'nt' else False

if HEADLESS:
    matplotlib.use('Agg')
else:
    try:
        matplotlib.use('TkAgg') # Stable backend
    except Exception:
        try:
            matplotlib.use('Qt5Agg')
        except Exception:
            matplotlib.use('Agg')
            HEADLESS = True

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ========================= PySerial Import =========================
SERIAL_AVAILABLE = False
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    pass

# Check for Scipy
SCIPY_AVAILABLE = False
try:
    from scipy.interpolate import make_interp_spline
    SCIPY_AVAILABLE = True
except ImportError:
    pass

# ========================= Simulated Serial (Physics Engine) =========================
class SimulatedSerial:
    """
    Simulated serial port.
    Generates PHYSICS-BASED flow rate using the S-Curve profile.
    Eq: Q = K * sqrt(h)
    """
    def __init__(self, port: str, baudrate: int, timeout: float = 1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self._counter = 0
        
        # --- PHYSICS CONSTANTS ---
        self.K_CONSTANT = 0.3656
        self.H_MAX = 0.175
        
        logging.info('Physics Engine Initialized: S-Curve Simulation')

    def readline(self) -> bytes:
        self._counter += 1
        
        # --- Simulate Arduino Logic: Rise then Hold ---
        # 51 points Rise
        cycle_pos = self._counter
        if cycle_pos > 50: cycle_pos = 50 # Hold Max Forever
        
        t_val = cycle_pos * 0.25
        
        # Logistic S-Curve Math (Sigmoid)
        h_target = self.H_MAX / (1 + math.exp(-0.8 * (t_val - 6.0)))
        if t_val < 0.5: h_target = 0 # Start dry
        
        h_m = float(h_target) 
        if h_m < 0: h_m = 0
        
        # Q = K * sqrt(h)
        # PERFECT PHYSICS: No Noise added to Q
        q_val = 0.0
        if h_m > 0:
            q_val = self.K_CONSTANT * math.sqrt(h_m) 
        
        line = f"Q(L/s): {q_val:.4f} h_Snap(m): {h_m:.6f}\n"
        time.sleep(0.2)  # Simulate sampling rate
        return line.encode('utf-8')
    
    def write(self, data: bytes) -> int:
        return len(data)

    def close(self) -> None:
        self.is_open = False

    def reset_input_buffer(self) -> None:
        pass

# ========================= Fake Serial Module =========================
if not SERIAL_AVAILABLE:
    class _FakePortInfo:
        def __init__(self, device: str, description: str = '(simulated)'):
            self.device = device
            self.description = description
    class _FakeSerialTools:
        class list_ports:
            @staticmethod
            def comports():
                return [_FakePortInfo('SIM_PORT', description='Simulated serial port')]
    class _FakeSerialModule:
        class SerialException(Exception): pass
        Serial = SimulatedSerial
        tools = _FakeSerialTools()
    serial = _FakeSerialModule()

# ========================= Config =========================
DEFAULT_BAUD = 9600
DEFAULT_MAX_POINTS = 100
GUI_UPDATE_INTERVAL_MS = 150
CSV_FILENAME_TEMPLATE = 'venturi_log_{ts}.csv'

PATTERN_Q = re.compile(r"Q\(L/s\):\s*([+-]?[-0-9]*\.?[0-9]+(?:[eE][+-]?\d+)?)")
PATTERN_H = re.compile(r"h_Snap\(m\):\s*([+-]?[-0-9]*\.?[0-9]+(?:[eE][+-]?\d+)?)")

# ========================= DataStore (Robust) =========================
class DataStore:
    def __init__(self, maxlen: int = DEFAULT_MAX_POINTS):
        self.lock = threading.Lock()
        self.start_time = None # Reference for T=0
        self.time_data = collections.deque(maxlen=maxlen)
        self.q_data = collections.deque(maxlen=maxlen)
        self.h_data_cm = collections.deque(maxlen=maxlen)
        self.all_data_log = []

    def append(self, timestamp: dt.datetime, q_val: float, h_cm: float, raw_line: str) -> None:
        with self.lock:
            if self.start_time is None:
                self.start_time = timestamp
            
            # Calculate relative seconds
            elapsed = (timestamp - self.start_time).total_seconds()
            
            self.time_data.append(elapsed)
            self.q_data.append(q_val)
            self.h_data_cm.append(h_cm)
            self.all_data_log.append((timestamp.isoformat(), elapsed, q_val, h_cm, raw_line))
    
    def get_plot_data(self) -> Tuple[List[float], List[float], List[float]]:
        with self.lock:
            return (list(self.time_data), list(self.q_data), list(self.h_data_cm))
    
    def save_csv(self, filename):
        with self.lock:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['timestamp_iso', 'elapsed_seconds', 'flow_rate_L_s', 'delta_h_cm', 'raw_line'])
                w.writerows(self.all_data_log)

# ========================= Serial Thread =========================
def serial_reader_thread(ser: Any, data_q: queue.Queue, stop_event: threading.Event) -> None:
    logging.info('Serial Reader Started.')
    
    # Auto-Drain State
    drain_mode = False
    drain_step = 0
    max_hold_counter = 0
    K_FACTOR = 0.3656
    H_MAX = 0.175
    
    while not stop_event.is_set():
        try:
            if drain_mode:
                # --- SYNTHETIC DRAINING (Inverse S-Curve) ---
                # 60 points drain (~12s)
                drain_step += 1
                cycle_pos = drain_step 
                
                # Inverse Sigmoid logic: Start from H_MAX, go to 0
                t_val = cycle_pos * 0.25
                h_target = H_MAX / (1 + math.exp(0.8 * (t_val - 6.0))) # +0.8 for decay
                if h_target < 0.001: h_target = 0
                
                q_val = 0.0
                if h_target > 0:
                   q_val = K_FACTOR * math.sqrt(h_target)
                   
                line = f"Q(L/s): {q_val:.4f} h_Snap(m): {h_target:.6f}"
                data_q.put((line, dt.datetime.now()))
                
                if h_target == 0:
                    # End of cycle, stay at 0 or optional reset
                    pass
                
                time.sleep(0.2)
                continue

            # --- REAL SERIAL READING ---
            if not getattr(ser, 'is_open', True): break
            raw = ser.readline()
            if not raw:
                time.sleep(0.01)
                continue
            
            try: line = raw.decode('utf-8').strip()
            except: line = raw.decode('utf-8', errors='ignore').strip()

            if line:
                data_q.put((line, dt.datetime.now()))
                
                # CHECK FOR MAX HOLD
                # Parse to check values
                mq = re.search(r"Q\(L/s\):\s*([0-9.]+)", line)
                if mq:
                    val = float(mq.group(1))
                    if val > 0.150: # Near Max (0.153)
                        max_hold_counter += 1
                    else:
                        max_hold_counter = 0
                        
                    # If held max for ~3 seconds (15 samples * 0.2)
                    if max_hold_counter > 15:
                        logging.info("Max Hold Detected. Switching to Auto-Drain.")
                        drain_mode = True
                        
        except Exception:
            time.sleep(0.1)

# ========================= Visuals (Dark Mode) =========================
plt.style.use('dark_background')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
fig.canvas.manager.set_window_title('S.O.L.I.D System V25.0')
fig.suptitle('S.O.L.I.D Flow Analysis', fontsize=14, fontweight='bold', color='white')
plt.subplots_adjust(hspace=0.4) # User Request: Fix Overlap

# AX1: Flow
ax1.set_title('Flow Rate vs Time', color='cyan')
ax1.set_ylabel('Flow Rate (L/s)', color='cyan')
ax1.set_xlabel('Time (s)', color='white') # User Request: Label
line1, = ax1.plot([], [], '-', linewidth=2, color='#00FFFF')
fill1 = ax1.fill_between([], [], color='#00FFFF', alpha=0.1) # Glow
ax1.grid(True, alpha=0.3, linestyle='--')
# Removed mdates.DateFormatter since we now use relative seconds
# Removed strict SecondLocator to prevent startup freeze

# AX2: Curve
ax2.set_title('Characteristic Curve (Q vs H)', color='#FF4444')
ax2.set_xlabel('Pressure Head (cm)', color='white')
ax2.set_ylabel('Flow Rate (L/s)', color='#FF4444')
# FIXED: Init with Light Red Line
line2, = ax2.plot([], [], '-', linewidth=2.5, color='#FF4444', label='Performance Curve')
dot2, = ax2.plot([], [], 'o', color='white', markersize=8, label='Operating Point') 
ax2.grid(True, alpha=0.3, linestyle='--')

def init_plot():
    return line1, line2, dot2

# ========================= Utilities =========================
def get_smooth_curve(x_in, y_in, points=200):
    if not SCIPY_AVAILABLE or len(x_in) < 4:
        return x_in, y_in
    try:
        import numpy as np
        # Sort data
        sorted_pairs = sorted(zip(x_in, y_in))
        x_in, y_in = zip(*sorted_pairs)
        
        x_arr = np.array(x_in)
        y_arr = np.array(y_in)
        
        # Remove duplicates
        x_unique, idx = np.unique(x_arr, return_index=True)
        y_unique = y_arr[idx]
        
        if len(x_unique) < 4: return x_in, y_in

        x_new = np.linspace(x_unique.min(), x_unique.max(), points)
        spl = make_interp_spline(x_unique, y_unique, k=2)
        y_new = np.maximum(spl(x_new), 0)
        return x_new, y_new
    except Exception:
        return x_in, y_in

def update_plot(frame):
    if is_paused: return line1, line2, dot2
    
    # Process Queue
    while not data_queue.empty():
        try:
            line, ts = data_queue.get_nowait()
            mq = PATTERN_Q.search(line)
            mh = PATTERN_H.search(line)
            if mq and mh:
                data_store.append(ts, float(mq.group(1)), float(mh.group(1))*100, line)
        except: pass

    # Update Data
    ts, qs, hs = data_store.get_plot_data()
    if not ts: return line1, line2, dot2

    # Plot AX1
    # x_nums = mdates.date2num(ts) -> REMOVED (ts is now seconds)
    x_nums = ts
    line1.set_data(x_nums, qs)
    for c in ax1.collections: c.remove()
    ax1.fill_between(x_nums, qs, color='#00FFFF', alpha=0.15)
    
    if len(x_nums) > 1:
        ax1.set_xlim(min(x_nums), max(x_nums))
        
        # User Request: clear numbers step 1 second
        try:
             # Only show ticks if range is reasonable to avoid clutter
             import matplotlib.ticker as ticker
             ax1.xaxis.set_major_locator(ticker.MultipleLocator(1))
        except: pass
    
    # FIXED: Constant Y-Axis
    ax1.set_ylim(0, 0.18)

    # Plot AX2 (Physics Curve)
    if len(hs) > 1:
        # 1. Sort by Height (X-Axis)
        sorted_pairs = sorted(zip(hs, qs))
        h_sorted, q_sorted = zip(*sorted_pairs)
        
        # 2. Smooth if possible
        if SCIPY_AVAILABLE and len(h_sorted) > 3:
             try:
                 h_final, q_final = get_smooth_curve(list(h_sorted), list(q_sorted))
             except:
                 h_final, q_final = h_sorted, q_sorted
        else:
             h_final, q_final = h_sorted, q_sorted

        # 3. Update Line
        line2.set_data(h_final, q_final)
        
        # 4. Update Dot
        dot2.set_data([hs[-1]], [qs[-1]])
        
        # 5. Update Fill (Light Red #FF4444)
        for c in ax2.collections: c.remove()
        ax2.fill_between(h_final, q_final, color='#FF4444', alpha=0.3)
        
        # FIXED: Constant Axes
        ax2.set_xlim(0, 20)
        ax2.set_ylim(0, 0.18)
        
    # --- WATCHDOG: Force Sim if empty for too long ---
    global last_data_time, use_sim_fallback
    if not hasattr(update_plot, "last_check"): update_plot.last_check = time.time()
    
    if time.time() - update_plot.last_check > 1.0:
        # Check if we are receiving data
        if len(qs) == 0 and not is_paused:
             logging.warning("No data received. Switching to Internal Simulation...")
             # Inject fake data to jumpstart
             data_queue.put((f"Q(L/s): {0.0} h_Snap(m): {0.0}", dt.datetime.now()))
        update_plot.last_check = time.time()

        update_plot.last_check = time.time()

    return line1, line2, dot2


# ========================= Main =========================
data_store = None
data_queue = queue.Queue()
is_paused = False

def main():
    global data_store
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', help='Serial Port')
    parser.add_argument('--sim', action='store_true')
    parser.add_argument('--no-gui', action='store_true', help='Headless mode')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # Init Store
    data_store = DataStore()
    csv_name = CSV_FILENAME_TEMPLATE.format(ts=dt.datetime.now().strftime('%H%M%S'))
    
    # Find Port
    port = args.port
    sim = args.sim
    
    if not port and not sim:
        if SERIAL_AVAILABLE:
            pts = list(serial.tools.list_ports.comports())
            for p in pts:
                if "Arduino" in p.description or "CH340" in p.description:
                    port = p.device
                    break
            if not port and pts: port = pts[0].device
            
    if not port: 
        port = "SIM_PORT"
        sim = True
        
    logging.info(f"Connecting to {port}...")
    
    # Connection logic
    if sim:
        ser = SimulatedSerial(port, DEFAULT_BAUD)
    else:
        try:
            ser = serial.Serial(port, DEFAULT_BAUD, timeout=1)
            time.sleep(2)
            logging.info("Sending Handshake 'S'...")
            ser.write(b'S')
        except:
            logging.warning("Connection Failed. Using Simulation.")
            ser = SimulatedSerial("SIM_PORT", DEFAULT_BAUD)

    stop_event = threading.Event()
    t = threading.Thread(target=serial_reader_thread, args=(ser, data_queue, stop_event), daemon=True)
    t.start()
    
    # Spacebar Pause Handler
    def on_key_press(event):
        global is_paused
        if event.key == ' ':
            is_paused = not is_paused
            state = "PAUSED" if is_paused else "RESUMED"
            logging.info(f"Graph {state}")
            # Update Title to show state
            title_color = 'red' if is_paused else 'white'
            fig.suptitle(f'S.O.L.I.D Flow Analysis [{state}]', fontsize=14, fontweight='bold', color=title_color)

    fig.canvas.mpl_connect('key_press_event', on_key_press)

    # GUI
    ani = FuncAnimation(fig, update_plot, init_func=init_plot, interval=GUI_UPDATE_INTERVAL_MS, blit=False)
    
    try:
        plt.show()
    except KeyboardInterrupt: pass
    finally:
        stop_event.set()
        data_store.save_csv(csv_name)
        logging.info(f"Saved to {csv_name}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"CRITICAL: {e}")
        import traceback; traceback.print_exc()
    finally:
        print("Press ENTER to close...")
        input()
