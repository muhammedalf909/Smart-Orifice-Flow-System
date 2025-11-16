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
from typing import Optional, Tuple, List, Any

# ========================= Matplotlib Backend Setup =========================
import matplotlib

# Detect headless environment
HEADLESS = not os.environ.get('DISPLAY') if os.name != 'nt' else False

if HEADLESS:
    matplotlib.use('Agg')
else:
    try:
        matplotlib.use('TkAgg')
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

# ========================= Simulated Serial Class =========================
class SimulatedSerial:
    """
    Simulated serial port for testing without hardware.
    Generates PHYSICS-BASED flow rate and pressure data.
    Uses Venturi equation: Q = K * sqrt(h)
    """
    def __init__(self, port: str, baudrate: int, timeout: float = 1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self._counter = 0
        self._start_time = time.time()
        # Venturi constant (can be adjusted based on pipe geometry)
        self.K_CONSTANT = 0.3
        logging.info('Simulated serial port initialized: %s @ %d baud', port, baudrate)
        logging.info('Using physics-based simulation: Q = %.2f * sqrt(h)', self.K_CONSTANT)

    def readline(self) -> bytes:
        """Generate simulated sensor data line with Q proportional to sqrt(h)."""
        self._counter += 1
        
        # 1. Generate h (differential height) with smooth variation
        # h varies from 0.005 to 0.035 meters in a cycle
        base_h_m = 0.005 + 0.0015 * (self._counter % 20)
        h_m = base_h_m + random.uniform(-1e-4, 1e-4)  # Small noise
        if h_m < 0: 
            h_m = 0
        
        # 2. Calculate Q based on h (correct physical relationship)
        # Q = K * sqrt(h) (Venturi equation from Bernoulli)
        q_val = self.K_CONSTANT * (h_m ** 0.5) + random.uniform(-0.005, 0.005)  # Small noise
        if q_val < 0: 
            q_val = 0
        
        line = f"Q(L/s): {q_val:.4f} h_Snap(m): {h_m:.6f}\n"
        time.sleep(0.02)  # Simulate sensor delay
        return line.encode('utf-8')

    def close(self) -> None:
        """Close the simulated port."""
        self.is_open = False
        logging.debug('Simulated serial port closed')

    def reset_input_buffer(self) -> None:
        """Reset input buffer (no-op for simulation)."""
        pass

# ========================= Fake Serial for Missing PySerial =========================
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

    # Create fake serial module
    class _FakeSerialModule:
        class SerialException(Exception):
            pass
        
        Serial = SimulatedSerial
        tools = _FakeSerialTools()

    serial = _FakeSerialModule()

# ========================= Configuration =========================
DEFAULT_BAUD = 9600
DEFAULT_MAX_POINTS = 100
DEFAULT_MAX_LOG_ENTRIES = 10000
GUI_UPDATE_INTERVAL_MS = 200
CSV_FILENAME_TEMPLATE = 'venturi_log_{ts}.csv'

# Regex patterns for parsing sensor data
PATTERN_Q = re.compile(r"Q\(L/s\):\s*([+-]?[-0-9]*\.?[0-9]+(?:[eE][+-]?\d+)?)")
PATTERN_H = re.compile(r"h_Snap\(m\):\s*([+-]?[-0-9]*\.?[0-9]+(?:[eE][+-]?\d+)?)")

# ========================= Thread-Safe Data Storage =========================
class DataStore:
    """
    Thread-safe storage for collected sensor data.
    Supports both in-memory buffering and progressive CSV writing.
    """
    def __init__(self, maxlen: int = DEFAULT_MAX_POINTS, 
                 csv_path: Optional[str] = None,
                 stream_csv: bool = False):
        self.lock = threading.Lock()
        self.time_data = collections.deque(maxlen=maxlen)
        self.q_data = collections.deque(maxlen=maxlen)
        self.h_data_cm = collections.deque(maxlen=maxlen)
        
        # CSV streaming support
        self.stream_csv = stream_csv
        self.csv_path = csv_path
        self.csv_file = None
        self.csv_writer = None
        self.row_count = 0
        
        if stream_csv and csv_path:
            self._init_csv_writer()
        else:
            # In-memory log with size limit
            self.all_data_log = collections.deque(maxlen=DEFAULT_MAX_LOG_ENTRIES)
    
    def _init_csv_writer(self) -> None:
        """Initialize CSV writer for progressive writing."""
        try:
            self.csv_file = open(self.csv_path, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(['timestamp_iso', 'flow_rate_L_s', 'delta_h_cm', 'raw_line'])
            logging.info('Progressive CSV writing enabled: %s', self.csv_path)
        except Exception:
            logging.exception('Failed to initialize CSV writer')
            self.stream_csv = False
    
    def append(self, timestamp: dt.datetime, q_val: float, h_cm: float, raw_line: str) -> None:
        """Append new data point (thread-safe)."""
        with self.lock:
            self.time_data.append(timestamp)
            self.q_data.append(q_val)
            self.h_data_cm.append(h_cm)
            self.row_count += 1
            
            if self.stream_csv and self.csv_writer:
                try:
                    self.csv_writer.writerow([timestamp.isoformat(), q_val, h_cm, raw_line])
                    # Flush every 10 rows to balance performance and data safety
                    if self.row_count % 10 == 0:
                        self.csv_file.flush()
                except Exception:
                    logging.exception('Error writing to CSV stream')
            else:
                if hasattr(self, 'all_data_log'):
                    self.all_data_log.append((timestamp.isoformat(), q_val, h_cm, raw_line))
    
    def get_plot_data(self) -> Tuple[List[dt.datetime], List[float], List[float]]:
        """Get current plot data (thread-safe)."""
        with self.lock:
            return (list(self.time_data), list(self.q_data), list(self.h_data_cm))
    
    def get_all_logs(self) -> List[Tuple]:
        """Get all logged data (thread-safe)."""
        with self.lock:
            if hasattr(self, 'all_data_log'):
                return list(self.all_data_log)
            return []
    
    def close(self) -> None:
        """Close CSV file if streaming."""
        with self.lock:
            if self.csv_file:
                try:
                    self.csv_file.close()
                    logging.info('CSV stream closed: %d rows written', self.row_count)
                except Exception:
                    logging.exception('Error closing CSV file')

# Global instances
data_store: Optional[DataStore] = None
data_queue = queue.Queue()
is_paused = False  # Global flag for pause/resume functionality

# ========================= Utilities =========================

def find_arduino_port() -> str:
    """
    Auto-detect Arduino or USB-serial port.
    Returns 'SIM_PORT' if no hardware found.
    """
    if not SERIAL_AVAILABLE:
        logging.debug('PySerial not available; returning simulated port')
        return 'SIM_PORT'
    
    try:
        ports = list(serial.tools.list_ports.comports())
    except Exception:
        logging.debug('serial.tools.list_ports not available')
        return 'SIM_PORT'

    # Look for common Arduino identifiers
    for p in ports:
        desc = (p.description or '').lower()
        if any(keyword in desc for keyword in ['arduino', 'ch340', 'usb-serial', 'cp210', 'ftdi']):
            logging.info('Auto-detected serial device: %s (%s)', p.device, p.description)
            return p.device

    if ports:
        logging.warning('Could not detect Arduino by name; using first port: %s', ports[0].device)
        return ports[0].device

    logging.warning('No serial ports found; switching to simulation mode')
    return 'SIM_PORT'


def save_to_csv(filename: str, data_rows: List[Tuple]) -> None:
    """Save collected data to CSV file."""
    if not data_rows:
        logging.info('No data to save.')
        return

    logging.info('Saving %d rows to %s', len(data_rows), filename)
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp_iso', 'flow_rate_L_s', 'delta_h_cm', 'raw_line'])
            writer.writerows(data_rows)
        logging.info('Save completed: %s', filename)
    except Exception:
        logging.exception('Failed to save CSV')


# ========================= Serial Reader Thread =========================

def serial_reader_thread(ser: Any, data_q: queue.Queue, stop_event: threading.Event) -> None:
    """
    Thread target: read lines from serial and push into queue with timestamp.
    Enhanced error handling and recovery.
    """
    logging.info('Serial reader thread started')
    consecutive_errors = 0
    max_consecutive_errors = 10
    
    try:
        while not stop_event.is_set():
            try:
                # Check if port is still open
                if not getattr(ser, 'is_open', True):
                    logging.error('Serial port closed unexpectedly')
                    break
                
                raw = ser.readline()
                if not raw:
                    time.sleep(0.01)  # Prevent CPU spinning
                    continue
                
                # Multi-level encoding handling
                line = None
                for encoding in ['utf-8', 'latin1', 'ascii']:
                    try:
                        line = raw.decode(encoding).strip()
                        break
                    except UnicodeDecodeError:
                        continue
                
                if line is None:
                    line = raw.decode('utf-8', errors='ignore').strip()

                if line:
                    timestamp = dt.datetime.now()
                    data_q.put((line, timestamp))
                    consecutive_errors = 0  # Reset on success
                    
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= 3:
                    logging.warning('Serial read error (%d/%d): %s', 
                                  consecutive_errors, max_consecutive_errors, e)
                
                if consecutive_errors >= max_consecutive_errors:
                    logging.error('Too many consecutive errors, stopping serial reader')
                    break
                
                if SERIAL_AVAILABLE and isinstance(e, serial.SerialException):
                    logging.error('Serial exception: %s', e)
                    break
                
                time.sleep(0.1)  # Brief pause before retry
                
    except Exception:
        logging.exception('Fatal error in serial reader thread')
    finally:
        logging.info('Serial reader thread exiting')


# ========================= Plot Setup =========================

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
fig.suptitle('Venturi Pro - Live Dashboard', fontsize=14, fontweight='bold')

ax1.set_title('Flow Rate vs Time')
ax1.set_ylabel('Flow Rate (L/s)')
line1, = ax1.plot([], [], '-', linewidth=1.5, color='#2E86AB', label='Flow Rate')
ax1.legend(loc='upper right')

ax2.set_title('Flow Rate vs Delta h (Venturi Curve: Q ∝ √h)')
ax2.set_xlabel('Manometer Level (Δh) [cm]')
ax2.set_ylabel('Flow Rate (L/s)')
line2, = ax2.plot([], [], 'o', markersize=5, color='#A23B72', label='Venturi Curve')
ax2.legend(loc='upper left')

ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
ax1.grid(True, alpha=0.3, linestyle='--')
ax2.grid(True, alpha=0.3, linestyle='--')


def init_plot() -> Tuple:
    """Initialize plot lines."""
    line1.set_data([], [])
    line2.set_data([], [])
    return line1, line2


def update_plot(frame) -> Tuple:
    """
    Called by FuncAnimation. Consume queue and update plot data.
    Returns artists for blitting.
    """
    global data_store, is_paused
    
    # --- If paused, don't process any data ---
    if is_paused:
        return line1, line2
    # -----------------------------------------
    
    updated = False
    
    # Consume all available queue items
    while True:
        try:
            line, timestamp = data_queue.get_nowait()
        except queue.Empty:
            break

        match_q = PATTERN_Q.search(line)
        match_h = PATTERN_H.search(line)

        if match_q and match_h:
            try:
                q_val = float(match_q.group(1))
                h_m = float(match_h.group(1))
                h_cm = h_m * 100.0

                data_store.append(timestamp, q_val, h_cm, line)
                updated = True
                
            except ValueError:
                logging.debug('Could not parse numeric values from line: %s', line)
                continue

    # Update lines only if new data arrived
    if updated:
        time_list, q_list, h_list = data_store.get_plot_data()
        
        if time_list:
            x_nums = mdates.date2num(time_list)
            line1.set_data(x_nums, q_list)
            
            # Update x-axis limits with padding
            if len(x_nums) > 1:
                ax1.set_xlim(x_nums[0], x_nums[-1])
            
            # Update y-axis with margin
            if q_list:
                q_min, q_max = min(q_list), max(q_list)
                margin = (q_max - q_min) * 0.1 if q_max > q_min else 0.1
                ax1.set_ylim(q_min - margin, q_max + margin)

        if h_list and q_list:
            line2.set_data(h_list, q_list)
            
            # Update axes for second plot
            h_min, h_max = min(h_list), max(h_list)
            q_min, q_max = min(q_list), max(q_list)
            
            h_margin = (h_max - h_min) * 0.1 if h_max > h_min else 0.1
            q_margin = (q_max - q_min) * 0.1 if q_max > q_min else 0.1
            
            ax2.set_xlim(h_min - h_margin, h_max + h_margin)
            ax2.set_ylim(q_min - q_margin, q_max + q_margin)

        fig.autofmt_xdate()
    
    return line1, line2


# ========================= Signal Handlers =========================

shutdown_requested = threading.Event()
cleanup_done = threading.Event()

def signal_handler(signum: int, frame: Any) -> None:
    """Handle system signals for graceful shutdown."""
    logging.info('Signal %d received, initiating graceful shutdown...', signum)
    shutdown_requested.set()


# ========================= Main Function =========================

def main() -> None:
    global data_store
    
    parser = argparse.ArgumentParser(
        description='Venturi live dashboard - Production-Ready Version with Physics-Based Simulation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port COM3                    # Connect to COM3
  %(prog)s --simulate                     # Run in simulation mode (Physics-based: Q ∝ √h)
  %(prog)s --no-gui --csv-only            # Collect data without GUI
  %(prog)s --stream-csv --max-points 200  # Progressive CSV with 200 points buffer

Controls (GUI mode):
  SPACEBAR    - Pause/Resume plot updates
  Close window or Ctrl+C - Stop and save data
        """
    )
    parser.add_argument('--port', help='Serial port (e.g. COM3 or /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=DEFAULT_BAUD, help=f'Baud rate (default: {DEFAULT_BAUD})')
    parser.add_argument('--max-points', type=int, default=DEFAULT_MAX_POINTS, 
                       help=f'Max points to display (default: {DEFAULT_MAX_POINTS})')
    parser.add_argument('--simulate', action='store_true', help='Force simulated serial data')
    parser.add_argument('--no-gui', action='store_true', help='Run without matplotlib GUI')
    parser.add_argument('--csv-only', action='store_true', help='Save CSV without plotting')
    parser.add_argument('--stream-csv', action='store_true', 
                       help='Write CSV progressively (safer for long runs)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Set logging level')
    parser.add_argument('--collection-time', type=float, default=10.0,
                       help='Data collection time in no-GUI mode (seconds)')
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level), 
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Check headless environment
    if HEADLESS and not args.no_gui and not args.csv_only:
        logging.warning('No display available, forcing --no-gui mode')
        args.no_gui = True

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # CSV filename
    csv_filename = CSV_FILENAME_TEMPLATE.format(ts=dt.datetime.now().strftime('%Y%m%d_%H%M%S'))

    # Initialize data store
    data_store = DataStore(
        maxlen=args.max_points,
        csv_path=csv_filename if args.stream_csv else None,
        stream_csv=args.stream_csv
    )

    # Decide simulation mode
    simulate = args.simulate or (not SERIAL_AVAILABLE)
    if args.simulate:
        logging.info('Simulation mode requested')
    elif not SERIAL_AVAILABLE:
        logging.warning('PySerial not found: running in simulation mode')

    # Find or create port
    port = args.port or find_arduino_port()
    if not port or port == 'SIM_PORT':
        logging.warning('No hardware port available; switching to simulation mode')
        simulate = True
        port = 'SIM_PORT'

    stop_event = threading.Event()
    ser = None
    reader_thread = None

    def cleanup_and_save() -> None:
        """Cleanup function - runs only once."""
        if cleanup_done.is_set():
            return
        cleanup_done.set()
        
        logging.info('Cleaning up...')
        stop_event.set()
        
        # Close serial port
        try:
            if ser and getattr(ser, 'is_open', False):
                ser.close()
                logging.info('Serial port closed')
        except Exception:
            logging.exception('Error closing serial port')

        # Join reader thread
        if reader_thread and reader_thread.is_alive():
            reader_thread.join(timeout=2)
            logging.info('Reader thread joined')

        # Close data store (if streaming CSV)
        if data_store:
            data_store.close()
            
            # Save buffered data if not streaming
            if not args.stream_csv:
                all_logs = data_store.get_all_logs()
                save_to_csv(csv_filename, all_logs)

    try:
        # Create serial object
        if simulate:
            logging.info('Starting simulated serial mode. Port=%s Baud=%d', port, args.baud)
            ser = SimulatedSerial(port, args.baud, timeout=1)
        else:
            logging.info('Opening real serial port %s @ %d', port, args.baud)
            ser = serial.Serial(port, args.baud, timeout=1)
            try:
                ser.reset_input_buffer()
            except AttributeError:
                pass

        # Start reader thread
        reader_thread = threading.Thread(
            target=serial_reader_thread, 
            args=(ser, data_queue, stop_event), 
            daemon=True,
            name='SerialReaderThread'
        )
        reader_thread.start()

        if args.no_gui or args.csv_only:
            logging.info('Running in no-GUI mode; collecting data for %.1f seconds...', 
                        args.collection_time)
            start_t = time.time()
            
            # Process data from queue during collection
            while time.time() - start_t < args.collection_time and not shutdown_requested.is_set():
                try:
                    # Consume data from queue
                    while True:
                        try:
                            line, timestamp = data_queue.get_nowait()
                            
                            match_q = PATTERN_Q.search(line)
                            match_h = PATTERN_H.search(line)

                            if match_q and match_h:
                                try:
                                    q_val = float(match_q.group(1))
                                    h_m = float(match_h.group(1))
                                    h_cm = h_m * 100.0
                                    data_store.append(timestamp, q_val, h_cm, line)
                                except ValueError:
                                    pass
                        except queue.Empty:
                            break
                except Exception as e:
                    logging.exception('Error processing queue data')
                
                time.sleep(0.1)
            
            cleanup_and_save()
            
        else:
            # Determine if blitting should be used
            try:
                backend = matplotlib.get_backend().lower()
                use_blit = backend not in ['agg', 'pdf', 'svg', 'ps']
                logging.info('Backend: %s, Blitting: %s', backend, use_blit)
            except Exception:
                use_blit = False
                logging.warning('Could not detect backend, disabling blitting')

            # Setup plot close handler
            def on_close(event):
                logging.info('Plot window closed by user')
                shutdown_requested.set()
                cleanup_and_save()
                plt.close('all')

            fig.canvas.mpl_connect('close_event', on_close)
            
            # --- NEW: Pause/Resume with Spacebar ---
            def on_key_press(event):
                """Handle key press for pause/resume."""
                global is_paused
                if event.key == ' ':  # Spacebar
                    is_paused = not is_paused
                    if is_paused:
                        logging.info('Plot PAUSED (press Spacebar to resume)')
                        fig.suptitle('Venturi Pro - (PAUSED)', fontsize=14, fontweight='bold', color='red')
                    else:
                        logging.info('Plot RESUMED')
                        fig.suptitle('Venturi Pro - Live Dashboard', fontsize=14, fontweight='bold', color='black')
                    fig.canvas.draw_idle()

            fig.canvas.mpl_connect('key_press_event', on_key_press)
            # ---------------------------------------

            # Create animation
            ani = FuncAnimation(
                fig, 
                update_plot, 
                init_func=init_plot, 
                interval=GUI_UPDATE_INTERVAL_MS, 
                blit=use_blit,
                cache_frame_data=False
            )
            
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            
            logging.info('Starting GUI... Press SPACEBAR to pause/resume, close window to stop.')
            plt.show()
            
            # If show() returns (window closed), cleanup
            if not shutdown_requested.is_set():
                cleanup_and_save()

    except KeyboardInterrupt:
        logging.info('KeyboardInterrupt received')
        cleanup_and_save()
        
    except Exception:
        logging.exception('Exception in main')
        cleanup_and_save()
        
    finally:
        if not cleanup_done.is_set():
            cleanup_and_save()
        
        logging.info('Program terminated successfully')


# ========================= Tests =========================

def _test_regex_parsing() -> None:
    """Basic unit tests for regex patterns."""
    samples = [
        ("Q(L/s): 1.234 h_Snap(m): 0.012345", 1.234, 0.012345),
        ("Q(L/s): -0.5 h_Snap(m): -0.001", -0.5, -0.001),
        ("Q(L/s): 1.23e-2 h_Snap(m): 3.4E-4", 1.23e-2, 3.4e-4),
    ]
    for line, q_exp, h_exp in samples:
        m_q = PATTERN_Q.search(line)
        m_h = PATTERN_H.search(line)
        assert m_q, f"Failed to match Q in: {line}"
        assert m_h, f"Failed to match h in: {line}"
        q_val = float(m_q.group(1))
        h_val = float(m_h.group(1))
        assert abs(q_val - q_exp) < 1e-9, (q_val, q_exp)
        assert abs(h_val - h_exp) < 1e-12, (h_val, h_exp)
    print('✓ Regex parsing tests passed')


def _test_simulated_serial_reader() -> None:
    """Smoke test for simulated serial reader."""
    logging.info('Running simulated serial reader test...')
    q = queue.Queue()
    stop_event = threading.Event()
    
    ser_sim = SimulatedSerial('SIM_PORT', 9600, timeout=1)
    t = threading.Thread(target=serial_reader_thread, args=(ser_sim, q, stop_event), daemon=True)
    t.start()
    
    time.sleep(0.5)
    stop_event.set()
    t.join(timeout=2)
    
    found = False
    item_count = 0
    while not q.empty():
        line, ts = q.get()
        item_count += 1
        if PATTERN_Q.search(line) and PATTERN_H.search(line):
            found = True
    
    assert found, 'Simulated reader did not produce expected lines'
    assert item_count > 0, 'No data received from simulated reader'
    print(f'✓ Simulated serial reader test passed (received {item_count} items)')


def _test_thread_safety() -> None:
    """Test thread-safe data store."""
    store = DataStore(maxlen=10)
    
    def writer():
        for i in range(20):
            store.append(dt.datetime.now(), float(i), float(i*2), f"line{i}")
            time.sleep(0.001)
    
    def reader():
        for _ in range(20):
            _ = store.get_plot_data()
            time.sleep(0.001)
    
    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=reader)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    logs = store.get_all_logs()
    assert len(logs) == 20, f"Expected 20 logs, got {len(logs)}"
    store.close()
    print('✓ Thread safety test passed')


def _test_csv_streaming() -> None:
    """Test progressive CSV writing."""
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        csv_path = f.name
    
    try:
        store = DataStore(maxlen=10, csv_path=csv_path, stream_csv=True)
        
        # Write some data
        for i in range(5):
            store.append(dt.datetime.now(), float(i), float(i*2), f"test{i}")
        
        store.close()
        
        # Verify CSV was written
        with open(csv_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 6, f"Expected 6 lines (header + 5 data), got {len(lines)}"
        
        print('✓ CSV streaming test passed')
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)


def _test_physics_simulation() -> None:
    """Test that simulation follows Q ∝ sqrt(h)."""
    ser_sim = SimulatedSerial('SIM_PORT', 9600, timeout=1)
    
    # Collect samples and calculate K for each
    K_values = []
    for _ in range(15):
        line = ser_sim.readline().decode('utf-8').strip()
        m_q = PATTERN_Q.search(line)
        m_h = PATTERN_H.search(line)
        if m_q and m_h:
            q = float(m_q.group(1))
            h = float(m_h.group(1))
            if h > 0 and q > 0:
                K = q / (h ** 0.5)
                K_values.append(K)
    
    # Check that K is relatively constant (coefficient of variation < 30%)
    if K_values:
        import statistics
        mean_K = statistics.mean(K_values)
        stdev_K = statistics.stdev(K_values) if len(K_values) > 1 else 0
        cv = (stdev_K / mean_K) if mean_K > 0 else 0
        
        assert cv < 0.3, f"Physics check failed: K too variable (CV={cv:.2%})"
        print(f'✓ Physics simulation test passed (Q ∝ √h verified, K≈{mean_K:.3f}±{stdev_K:.3f})')
    else:
        print('⚠ Warning: No valid samples for physics test')


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        print('Running self-tests...\n')
        _test_regex_parsing()
        _test_simulated_serial_reader()
        _test_thread_safety()
        _test_csv_streaming()
        _test_physics_simulation()
        print('\n✓ All tests passed successfully!')
        sys.exit(0)

    main()
