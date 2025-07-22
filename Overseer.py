import json
import subprocess
import threading
import time
import os
import sys
from datetime import datetime
import serial

# --- Configuration ---
CONFIG_FILE = '/src/apps/Overseer/config.json'
BASE_LOG_DIR = 'logs'
# The 'name' from config.json of the script whose log file we will monitor
TRIGGER_SCRIPT_NAME = "Gnuradio_TX"
TRIGGER_WORD = "Finished"

# --- Global variables for process management ---
active_processes = {}
serial_thread = None
serial_connection = None
stop_event = threading.Event()

def timestamp():
    """Returns a formatted timestamp string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def monitor_trigger_file(log_path, trigger_word):
    """
    A dedicated function to monitor a log file for a specific word.
    This runs in a thread and blocks until the word is found.
    """
    ##print(f"[{timestamp()}] [MONITOR] Watching '{log_path}' for the word '{trigger_word}'...")
    
    # Wait for the file to be created
    while not os.path.exists(log_path) and not stop_event.is_set():
        time.sleep(0.5)

    if stop_event.is_set():
        return

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            while not stop_event.is_set():
                line = f.readline()
                if line:
                    if trigger_word in line:
                        ##print(f"[{timestamp()}] [MONITOR] Trigger word '{trigger_word}' found! Signaling shutdown for this run.")
                        return # Exit the function, allowing the main loop to proceed
                else:
                    # No new line, wait a bit before checking again
                    time.sleep(1)
    except Exception as e:
        #print(f"[{timestamp()}] [MONITOR] Error while monitoring file: {e}")

def execute_script(script_config, run_log_dir):
    """
    Launches a script and manages its logging for a specific run.
    Returns the process object and the path to its log file.
    """
    name = script_config['name']
    log_filename = os.path.join(run_log_dir, f"{name}.txt")
    
    command_str = ""
    script_type = script_config['type']
    config = script_config['config']
    
    try:
        command_list = []
        if script_type in ['shell', 'local', 'conda']:
            if script_type == 'shell':
                command_list = [config['script_path']]
            elif script_type == 'local':
                command_list = ['python', '-u', config['script_path']]
            elif script_type == 'conda':
                command_list = ['conda', 'run', '-n', config['env_name'], 'python', '-u', config['script_path']]
            
            command_str = ' '.join(command_list)
        else:
            #print(f"[{timestamp()}] ERROR: Unknown or unsupported script type '{script_type}'.")
            return None, None
            
        #print(f"[{timestamp()}] Executing shell command: {command_str}")
        
        log_file = open(log_filename, 'w')
        process = subprocess.Popen(
            command_str,
            shell=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        #print(f"[{timestamp()}] Started '{name}'. Logging to '{log_filename}'")
        return process, log_filename, log_file

    except Exception as e:
        #print(f"[{timestamp()}] ERROR starting '{name}': {e}")
        return None, None, None

def serial_reader_thread(ser, log_file_path):
    """Continuously reads from the serial port and logs the data."""
    #print(f"[{timestamp()}] [SERIAL] Reader started. Logging to '{log_file_path}'")
    try:
        with open(log_file_path, 'w') as log_file:
            while not stop_event.is_set():
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        log_entry = f"[{timestamp()}] RECV: {line}"
                        print(log_entry)
                        log_file.write(log_entry + '\n')
                        log_file.flush()
                else:
                    time.sleep(0.05)
    except Exception as e:
        #print(f"[{timestamp()}] [SERIAL] An error occurred in the serial thread: {e}")
    #print(f"[{timestamp()}] [SERIAL] Reader thread stopped.")

def shutdown_all_processes():
    """Gracefully terminates all active processes and threads."""
    #print(f"[{timestamp()}] --- Initiating shutdown of all services... ---")
    stop_event.set() # Signal all threads to stop

    if serial_connection and serial_connection.is_open:
        serial_connection.close()
        #print(f"[{timestamp()}] Serial port closed.")

    if serial_thread and serial_thread.is_alive():
        serial_thread.join(timeout=2)

    for name, data in list(active_processes.items()):
        #print(f"[{timestamp()}] Terminating '{name}' (PID: {data['process'].pid})...")
        data['process'].terminate()
        try:
            data['process'].wait(timeout=5)
        except subprocess.TimeoutExpired:
            #print(f"[{timestamp()}] '{name}' did not terminate gracefully. Forcing kill...")
            data['process'].kill()
        
        if data['log_file']:
            data['log_file'].close()
        #print(f"[{timestamp()}] '{name}' terminated.")
    
    active_processes.clear()
    stop_event.clear() # Reset the event for the next run
    #print(f"[{timestamp()}] --- Shutdown complete. ---")

def main():
    """Main automation loop."""
    global serial_thread, serial_connection
    run_number = 1
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
    except Exception as e:
        #print(f"FATAL: Could not load '{CONFIG_FILE}'. Exiting. Error: {e}")
        sys.exit(1)

    while True:
        print("\n" + "="*20 + f" Starting Run #{run_number} " + "="*20)
        
        # --- 1. Setup for this run ---
        run_log_dir = os.path.join(BASE_LOG_DIR, f"run_{run_number}")
        os.makedirs(run_log_dir, exist_ok=True)
        #print(f"[{timestamp()}] Log directory for this run: '{run_log_dir}'")

        trigger_log_path = None
        
        # --- 2. Start Serial Port Listener ---
        serial_config = config_data.get('serial_port')
        if serial_config:
            try:
                serial_connection = serial.Serial(serial_config['port'], serial_config['baud_rate'], timeout=1)
                serial_log_path = os.path.join(run_log_dir, "serial.txt")
                serial_thread = threading.Thread(target=serial_reader_thread, args=(serial_connection, serial_log_path), daemon=True)
                serial_thread.start()
            except serial.SerialException as e:
                #print(f"[{timestamp()}] WARNING: Could not open serial port. Continuing without it. Error: {e}")
        
        # --- 3. Start Scripts ---
        for script_conf in config_data['scripts_to_run']:
            if script_conf.get('enabled', False):
                process, log_path, log_file_handle = execute_script(script_conf, run_log_dir)
                if process:
                    active_processes[script_conf['name']] = {'process': process, 'log_file': log_file_handle}
                    if script_conf['name'] == TRIGGER_SCRIPT_NAME:
                        trigger_log_path = log_path

        if not trigger_log_path:
            #print(f"FATAL: Trigger script '{TRIGGER_SCRIPT_NAME}' not found or failed to start. Cannot continue.")
            break
            
        # --- 4. Monitor for Trigger ---
        # This function will block until the trigger word is found or the program is stopped
        monitor_trigger_file(trigger_log_path, TRIGGER_WORD)

        # If we get here, it means the trigger was found or the stop_event was set by Ctrl+C
        if stop_event.is_set(): # Check if we were interrupted
             break

        #print(f"[{timestamp()}] --- Run #{run_number} complete. Restarting services... ---")
        shutdown_all_processes()
        run_number += 1
        time.sleep(2) # Brief pause before starting the next run

    # --- 5. Final Cleanup on Exit ---
    #print(f"\n[{timestamp()}] Main loop exited. Performing final cleanup.")
    shutdown_all_processes()
    #print(f"[{timestamp()}] Automation controller has shut down.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # This handles Ctrl+C if it's pressed while the main loop is between states
        #print(f"\n[{timestamp()}] Ctrl+C detected. Shutting down...")
        stop_event.set()
