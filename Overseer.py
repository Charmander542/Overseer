import json
import subprocess
import threading
import time
import os
import sys
from datetime import datetime
import serial

# --- Configuration ---
CONFIG_FILE = 'config.json'
LOG_DIR = 'logs'

# --- Global variables ---
active_processes = {}
serial_thread = None
serial_connection = None
stop_event = threading.Event()

def timestamp():
    """Returns a formatted timestamp string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def execute_script(script_config):
    """
    Constructs the correct command based on the script type (docker, shell, conda, local)
    and executes it in a new process, logging all output.
    """
    name = script_config['name']
    log_filename = os.path.join(LOG_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    command = []
    script_type = script_config['type']
    config = script_config['config']

    print(f"[{timestamp()}] Preparing to start script: '{name}' (type: {script_type})")

    try:
        if script_type == 'docker':
            extra_args = config.get('extra_docker_args', '').split()
            command = [
                'docker', 'run', '--rm', '-i',
                *extra_args,
                config['image_name'],
                'python3', '-u', config['script_path_in_container']
            ]
        elif script_type == 'conda':
            command = [
                'conda', 'run', '-n', config['env_name'],
                'python', '-u', config['script_path']
            ]
        elif script_type == 'shell':
            command = [config['script_path']]
        elif script_type == 'local':
            command = ['python', '-u', config['script_path']]
        else:
            print(f"[{timestamp()}] ERROR: Unknown script type '{script_type}' for script '{name}'. Skipping.")
            return

        print(f"[{timestamp()}] Executing command: {' '.join(command)}")
        
        # Open log file and start the subprocess
        # stderr is redirected to stdout to capture all output in one place.
        log_file = open(log_filename, 'w')
        process = subprocess.Popen(
            command,
            shell=True, # This is the key
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=1
        )
        active_processes[name] = {'process': process, 'log_file': log_file}
        print(f"[{timestamp()}] Started '{name}'. Logging to '{log_filename}'")

    except FileNotFoundError as e:
        print(f"[{timestamp()}] ERROR starting '{name}': Command not found. Is Docker/Conda installed and in your PATH? ({e})")
    except Exception as e:
        print(f"[{timestamp()}] ERROR starting '{name}': {e}")


def serial_reader_thread(ser, log_filename):
    """
    Continuously reads from the serial port and logs the data.
    Runs in a separate thread.
    """
    print(f"[{timestamp()}] Serial reader started. Logging to '{log_filename}'")
    with open(log_filename, 'w') as log_file:
        while not stop_event.is_set():
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        ts = timestamp()
                        log_entry = f"[{ts}] RECV: {line}"
                        print(log_entry)
                        log_file.write(log_entry + '\n')
                        log_file.flush()
            except serial.SerialException as e:
                print(f"[{timestamp()}] ERROR: Serial device disconnected or error. {e}")
                break
            except Exception as e:
                print(f"[{timestamp()}] An unexpected error occurred in the serial thread: {e}")
                break
            time.sleep(0.05)
    print(f"[{timestamp()}] Serial reader thread stopped.")


def main():
    """Main function to orchestrate everything."""
    global serial_thread, serial_connection

    # --- 1. Initial Setup ---
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        print(f"[{timestamp()}] Created log directory: {LOG_DIR}")

    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        print(f"[{timestamp()}] ERROR: '{CONFIG_FILE}' not found. Please create it.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"[{timestamp()}] ERROR: Could not decode '{CONFIG_FILE}'. Please check for syntax errors.")
        sys.exit(1)

    # --- 2. Start Serial Port Listener ---
    serial_config = config_data.get('serial_port')
    if serial_config:
        try:
            serial_connection = serial.Serial(serial_config['port'], serial_config['baud_rate'], timeout=1)
            print(f"[{timestamp()}] Serial port {serial_config['port']} opened successfully.")
            
            log_filename = os.path.join(LOG_DIR, f"serial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            serial_thread = threading.Thread(
                target=serial_reader_thread, 
                args=(serial_connection, log_filename),
                daemon=True
            )
            serial_thread.start()
        except serial.SerialException as e:
            print(f"[{timestamp()}] ERROR: Could not open serial port {serial_config['port']}. {e}")
            print("[{timestamp()}] Continuing without serial functionality.")
    
    # --- 3. Start Scripts ---
    for script_conf in config_data['scripts_to_run']:
        if script_conf.get('enabled', False):
            execute_script(script_conf)
        else:
            print(f"[{timestamp()}] Script '{script_conf['name']}' is disabled in config. Skipping.")
    
    print("\n" + "="*50)
    print("All configured processes are running.")
    print("="*50 + "\n")

    # --- 4. Main Interactive Loop ---
    try:
        while True:
            print("\n--- Main Controller Menu ---")
            print("(s) Send serial command")
            print("(c) Check process status")
            print("(q) Quit and terminate all processes")
            choice = input("Enter your choice: ").lower()

            if choice == 's':
                if serial_connection and serial_connection.is_open:
                    cmd = input("Enter command to send: ")
                    serial_connection.write((cmd + '\n').encode('utf-8'))
                    print(f"[{timestamp()}] SENT: {cmd}")
                else:
                    print("Serial port not available.")
            elif choice == 'c':
                print("\n--- Process Status ---")
                if not active_processes:
                    print("No active processes.")
                for name, data in active_processes.items():
                    if data['process'].poll() is None:
                        status = "Running"
                    else:
                        status = f"Finished with exit code {data['process'].poll()}"
                    print(f"- {name}: {status}")
            elif choice == 'q':
                break
            else:
                print("Invalid choice, please try again.")

    except KeyboardInterrupt:
        print(f"\n[{timestamp()}] Ctrl+C detected. Shutting down...")
    
    # --- 5. Cleanup ---
    print(f"[{timestamp()}] Initiating shutdown...")
    stop_event.set() # Signal threads to stop

    if serial_connection and serial_connection.is_open:
        serial_connection.close()
        print(f"[{timestamp()}] Serial port closed.")

    if serial_thread:
        serial_thread.join(timeout=2)

    for name, data in active_processes.items():
        print(f"[{timestamp()}] Terminating '{name}' (PID: {data['process'].pid})...")
        data['process'].terminate()
        try:
            # Wait a bit for graceful termination
            data['process'].wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"[{timestamp()}] '{name}' did not terminate gracefully. Forcing kill...")
            data['process'].kill()
        
        data['log_file'].close()
        print(f"[{timestamp()}] '{name}' terminated.")

    print(f"[{timestamp()}] Shutdown complete. All logs saved in '{LOG_DIR}'.")


if __name__ == '__main__':
    main()