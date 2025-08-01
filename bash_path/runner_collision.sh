#!/bin/bash

# === Configuration ===
SCRIPT_IOTSCAN="./run_iotscan_lora.sh"
SCRIPT_MULTIPLEX="./run_multiplex_collision.sh"
SCRIPT_CATSNIFFER="./run_catsniffer.sh"
SCRIPT_TX_WRAPPER="./run_tx_collision.sh" # The wrapper script

LOG_DIR="logs"
LOG_IOTSCAN="$LOG_DIR/iotscan_lora_log.txt"
LOG_MULTIPLEX="$LOG_DIR/multiplex_log.txt"
LOG_CATSNIFFER="$LOG_DIR/catsniffer_log.txt"
LOG_TX="$LOG_DIR/tx_log.txt"

# === Parameter Ranges ===
# Defines the parameter space to test.
SPREADING_FACTOR_RANGE=$(seq 7 1 12)
GAIN_RANGE=$(seq 1.0 0.5 3.0)
DELAY_RANGE=$(seq 0.0 0.2 1.0) # Delay in seconds

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to start all scripts and store their PIDs
start_scripts() {
    local sf=$1
    local gain=$2
    local delay=$3

    echo "-----------------------------------------------------"
    echo ">>> Starting all scripts for SF: $sf, Gain: $gain, Delay: ${delay}s"
    echo "-----------------------------------------------------"

    # Start monitoring scripts in the background
    bash "$SCRIPT_IOTSCAN" > "$LOG_IOTSCAN" 2>&1 &
    PID_IOTSCAN=$!
    echo "Started $SCRIPT_IOTSCAN (PID $PID_IOTSCAN)"

    bash "$SCRIPT_MULTIPLEX" > "$LOG_MULTIPLEX" 2>&1 &
    PID_MULTIPLEX=$!
    echo "Started $SCRIPT_MULTIPLEX (PID $PID_MULTIPLEX)"

    bash "$SCRIPT_CATSNIFFER" > "$LOG_CATSNIFFER" 2>&1 &
    PID_CATSNIFFER=$!
    echo "Started $SCRIPT_CATSNIFFER (PID $PID_CATSNIFFER)"

    # Execute the TX wrapper script with all parameters
    bash "$SCRIPT_TX_WRAPPER" "$gain" "$delay" "$sf" > "$LOG_TX" 2>&1 &
    PID_TX=$!
    echo "Started $SCRIPT_TX_WRAPPER (PID $PID_TX)"
}

# Function to gracefully stop all background scripts
kill_scripts() {
    echo ">>> Stopping all running script processes..."
    # Kill all child processes of this script
    pkill -P $$
    sleep 2
}

# Trap script exit (e.g., Ctrl+C) to ensure cleanup
trap 'echo -e "\n>>> Exiting and cleaning up all processes..."; kill_scripts; exit 1' SIGINT SIGTERM

# --- Main Automation Loop ---
echo ">>> Starting Automation Loop <<<"

for sf in $SPREADING_FACTOR_RANGE; do
    for gain in $GAIN_RANGE; do
        for delay in $DELAY_RANGE; do
            
            start_scripts "$sf" "$gain" "$delay"

            echo ">>> Waiting for TX script (PID $PID_TX) to finish..."
            wait $PID_TX # Wait specifically for the transmission to complete

            echo ">>> TX run has completed for SF: $sf, Gain: $gain, Delay: ${delay}s"
            echo ">>> Archiving log files..."

            TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
            
            # Archive logs with descriptive names including SF, gain, and delay
            mv "$LOG_IOTSCAN" "$LOG_DIR/iotscan_sf${sf}_g${gain}_d${delay}_${TIMESTAMP}.txt"
            mv "$LOG_MULTIPLEX" "$LOG_DIR/multiplex_sf${sf}_g${gain}_d${delay}_${TIMESTAMP}.txt"
            mv "$LOG_CATSNIFFER" "$LOG_DIR/catsniffer_sf${sf}_g${gain}_d${delay}_${TIMESTAMP}.txt"
            mv "$LOG_TX" "$LOG_DIR/tx_sf${sf}_g${gain}_d${delay}_${TIMESTAMP}.txt"

            echo ">>> Log files have been archived."
            echo ">>> Cleaning up monitoring scripts before next run..."
            kill $PID_IOTSCAN $PID_MULTIPLEX $PID_CATSNIFFER >/dev/null 2>&1
            wait $PID_IOTSCAN $PID_MULTIPLEX $PID_CATSNIFFER 2>/dev/null
            sleep 2
        done
    done
done

echo ">>> Completed full cycle of all SF, gain, and delay combinations. Automation finished."
