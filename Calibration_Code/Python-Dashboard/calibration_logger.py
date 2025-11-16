import serial
import serial.tools.list_ports
from datetime import datetime
import sys
import time


class ArduinoCalibration:
    """Handle Arduino connection and calibration logging"""
    
    def __init__(self, baudrate=9600, duration=180):
        self.baudrate = baudrate
        self.duration = duration  # seconds
        self.ser = None
        self.port = None
        
    def find_arduino(self):
        """
        Detect Arduino port automatically
        Returns: Port name (str) or None
        """
        available_ports = serial.tools.list_ports.comports()
        
        # Priority check: Arduino-specific identifiers
        for port in available_ports:
            desc_lower = port.description.lower()
            if 'arduino' in desc_lower or 'ch340' in desc_lower or 'usb serial' in desc_lower:
                return port.device
            
            if port.manufacturer and 'arduino' in port.manufacturer.lower():
                return port.device
        
        # Fallback: return first available port
        if available_ports:
            return available_ports[0].device
        
        return None
    
    def list_ports(self):
        """Display all available serial ports"""
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("No serial ports detected on this system.")
            return
        
        print("\nAvailable Serial Ports:")
        print("-" * 50)
        for p in ports:
            print(f"Port: {p.device}")
            print(f"  Description: {p.description}")
            if p.manufacturer:
                print(f"  Manufacturer: {p.manufacturer}")
            print()
    
    def connect(self, port=None):
        """
        Establish serial connection
        Args:
            port: Specific port name (optional)
        Returns: True if connected, False otherwise
        """
        if port:
            self.port = port
        else:
            print("Detecting Arduino...")
            self.port = self.find_arduino()
            
            if not self.port:
                print("\nERROR: Arduino not found!")
                print("\nAvailable ports:")
                self.list_ports()
                print("\nTry specifying port manually:")
                print("  python script.py --port COM3")
                return False
            
            print(f"Arduino detected on: {self.port}")
        
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            print(f"Connected to {self.port} at {self.baudrate} baud")
            return True
            
        except serial.SerialException as e:
            print(f"\nERROR: Cannot connect to {self.port}")
            print(f"Details: {e}")
            print("\nTroubleshooting:")
            print("  1. Check Arduino is connected via USB")
            print("  2. Close Arduino IDE Serial Monitor")
            print("  3. Try a different USB port")
            print("  4. Check device drivers are installed")
            return False
    
    def run_calibration(self):
        """Execute calibration procedure"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'calibration_{timestamp}.txt'
        
        print("\n" + "="*60)
        print("  VENTURI METER CALIBRATION - 3 MINUTE TEST")
        print("="*60)
        print(f"\nOutput file: {filename}")
        print(f"Duration: {self.duration} seconds ({self.duration//60} minutes)")
        print("\nTest Procedure:")
        print("  1. Ensure pump is OFF at start (Δh = 0)")
        print("  2. After 90 seconds, turn pump to MAX speed")
        print("  3. System will log automatically")
        print("\nStarting in 3 seconds...")
        print("="*60 + "\n")
        
        time.sleep(3)
        
        start_time = time.time()
        readings = []
        
        try:
            with open(filename, 'w', encoding='utf-8') as logfile:
                # Write header
                logfile.write("="*60 + "\n")
                logfile.write("VENTURI METER CALIBRATION LOG\n")
                logfile.write("="*60 + "\n")
                logfile.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                logfile.write(f"Port: {self.port}\n")
                logfile.write(f"Baudrate: {self.baudrate}\n")
                logfile.write(f"Duration: {self.duration}s\n")
                logfile.write("="*60 + "\n\n")
                
                last_update = 0
                
                while True:
                    elapsed = time.time() - start_time
                    
                    # Check timeout
                    if elapsed > self.duration:
                        print("\nTime limit reached. Finalizing...")
                        break
                    
                    # Read serial data
                    if self.ser.in_waiting > 0:
                        try:
                            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                            
                            if line:
                                timestamp_log = datetime.now().strftime('%H:%M:%S')
                                log_entry = f"[{timestamp_log}] {line}"
                                
                                print(log_entry)
                                logfile.write(log_entry + "\n")
                                logfile.flush()
                                
                                # Store reading for analysis
                                readings.append(line)
                                
                                # Check completion signals
                                if 'DONE' in line.upper() or 'COMPLETE' in line.upper():
                                    print("\nCalibration signal received.")
                                    break
                        
                        except UnicodeDecodeError:
                            continue  # Skip corrupted data
                    
                    # Progress indicator every 30 seconds
                    if int(elapsed) // 30 > last_update:
                        remaining = self.duration - int(elapsed)
                        if remaining > 0:
                            print(f"\n--- {remaining}s remaining ---\n")
                        last_update = int(elapsed) // 30
                    
                    time.sleep(0.1)  # Prevent CPU overload
                
                # Write summary
                logfile.write("\n" + "="*60 + "\n")
                logfile.write("CALIBRATION COMPLETE\n")
                logfile.write(f"Total readings: {len(readings)}\n")
                logfile.write(f"Actual duration: {int(elapsed)}s\n")
                logfile.write("="*60 + "\n")
            
            print("\n" + "="*60)
            print("CALIBRATION COMPLETED SUCCESSFULLY")
            print("="*60)
            print(f"Data saved: {filename}")
            print(f"Total readings: {len(readings)}")
            print(f"Duration: {int(elapsed)}s")
            print("\nNext Steps:")
            print("  1. Open the TXT file")
            print("  2. Identify MIN and MAX sensor values")
            print("  3. Physically measure H_max with ruler/caliper")
            print("  4. Update calibration constants in main code")
            print("="*60 + "\n")
            
        except KeyboardInterrupt:
            print("\n\nCalibration stopped by user (Ctrl+C)")
            return False
        
        return True
    
    def disconnect(self):
        """Close serial connection safely"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"Disconnected from {self.port}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Venturi Meter Calibration Data Logger',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python calibration.py                 # Auto-detect Arduino
  python calibration.py --port COM3     # Use specific port
  python calibration.py --list          # List available ports
  python calibration.py --duration 300  # 5-minute test
        """
    )
    
    parser.add_argument('--port', type=str, help='Serial port (e.g., COM3, /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate (default: 9600)')
    parser.add_argument('--duration', type=int, default=180, help='Test duration in seconds (default: 180)')
    parser.add_argument('--list', action='store_true', help='List available ports and exit')
    
    args = parser.parse_args()
    
    calib = ArduinoCalibration(baudrate=args.baudrate, duration=args.duration)
    
    # List ports mode
    if args.list:
        calib.list_ports()
        sys.exit(0)
    
    # Connect to Arduino
    if not calib.connect(args.port):
        sys.exit(1)
    
    # Run calibration
    try:
        success = calib.run_calibration()
        sys.exit(0 if success else 1)
    finally:
        calib.disconnect()


if __name__ == '__main__':
    main()
