#!/bin/bash

# === Configuration ===
SCRIPT_IOTSCAN="./run_iotscan_lora.sh"
SCRIPT_MULTIPLEX="./run_multiplex_lora.sh"
SCRIPT_CATSNIFFER="./run_catsniffer.sh"
SCRIPT_TX_WRAPPER="./run_tx_collision.sh"

LOG_DIR="logs"
LOG_IOTSCAN="$LOG_DIR/iotscan_lora_log.txt"
LOG_MULTIPLEX="$LOG_DIR/multiplex_log.txt"
LOG_CATSNIFFER="$LOG_DIR/catsniffer_log.txt"
LOG_TX="$LOG_DIR/tx_log.txt"

# === Parameter Ranges ===
# Defines the parameter space to test.
# Format: seq <start> <increment> <end>
GAIN_RANGE=$(seq 0.5 0.5 3.0)
DELAY_RANGE=$(seq 0.0 0.2 1.0) # Delay in seconds

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to start all scripts and store their PIDs
start_scripts() {
    local gain=$1
    local delay=$2

    echo "-----------------------------------------------------"
    echo ">>> Starting all scripts for Gain: $gain, Delay: ${delay}s"
    echo "-----------------------------------------------------"

    # Start monitoring scripts in the background
    bash "$SCRIPT_IOTSCAN" > "$LOG_IOTSCAN" 2>&1 &
    PID_IOTSCAN=$!
    echo "Started $SCRIPT_IOTSCAN (PID $PID_IOTSCAN, logging to $LOG_IOTSCAN)"

    bash "$SCRIPT_MULTIPLEX" > "$LOG_MULTIPLEX" 2>&1 &
    PID_MULTIPLEX=$!
    echo "Started $SCRIPT_MULTIPLEX (PID $PID_MULTIPLEX, logging to $LOG_MULTIPLEX)"

    bash "$SCRIPT_CATSNIFFER" > "$LOG_CATSNIFFER" 2>&1 &
    PID_CATSNIFFER=$!
    echo "Started $SCRIPT_CATSNIFFER (PID $PID_CATSNIFFER, logging to $LOG_CATSNIFFER)"

    # Execute the TX wrapper script and pass the gain and delay
    bash "$SCRIPT_TX_WRAPPER" "$gain" "$delay" > "$LOG_TX" 2>&1 &
    PID_TX=$!
    echo "Started $SCRIPT_TX_WRAPPER (PID $PID_TX, logging to $LOG_TX)"
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

for gain in $GAIN_RANGE; do
    for delay in $DELAY_RANGE; do
        
        start_scripts "$gain" "$delay"

        echo ">>> Waiting for TX script (PID $PID_TX) to finish..."
        wait $PID_TX # Wait specifically for the transmission to complete

        echo ">>> TX run has completed for Gain: $gain, Delay: ${delay}s"
        echo ">>> Archiving log files..."

        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        
        # Archive logs with descriptive names
        mv "$LOG_IOTSCAN" "$LOG_DIR/iotscan_g${gain}_d${delay}_${TIMESTAMP}.txt"
        mv "$LOG_MULTIPLEX" "$LOG_DIR/multiplex_g${gain}_d${delay}_${TIMESTAMP}.txt"
        mv "$LOG_CATSNIFFER" "$LOG_DIR/catsniffer_g${gain}_d${delay}_${TIMESTAMP}.txt"
        mv "$LOG_TX" "$LOG_DIR/tx_g${gain}_d${delay}_${TIMESTAMP}.txt"

        echo ">>> Log files have been archived."
        echo ">>> Cleaning up monitoring scripts before next run..."
        kill $PID_IOTSCAN $PID_MULTIPLEX $PID_CATSNIFFER >/dev/null 2>&1
        wait $PID_IOTSCAN $PID_MULTIPLEX $PID_CATSNIFFER 2>/dev/null
        sleep 2
    done
done

echo ">>> Completed full cycle of all gain and delay combinations. Automation finished."
