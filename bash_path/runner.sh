#!/bin/bash

# === Configuration ===
SCRIPT1="./run_iotscan_lora.sh"
SCRIPT2="./run_multiplex_lora.sh"
SCRIPT3="./run_catsniffer.sh"
SCRIPT4="./run_tx.sh"

LOG_DIR="logs"
LOG1="$LOG_DIR/iotscan_lora_log.txt"
LOG2="$LOG_DIR/multiplex_log.txt"
LOG3="$LOG_DIR/catsniffer_log.txt"
LOG4="$LOG_DIR/tx_log.txt"

# === Power Levels ===
# Define the cycle of power levels (gain values) to use for the TX script.
POWER_LEVELS=(100 80 60 40 35)

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to start all scripts and store their PIDs
# It now accepts a power level argument to pass to the TX wrapper script.
start_scripts() {
    local power=$1 # The first argument to the function is the power level

    echo "-----------------------------------------------------"
    echo ">>> Starting all scripts. Relaying TX Power Level: $power"
    echo "-----------------------------------------------------"

    bash "$SCRIPT1" > "$LOG1" 2>&1 &
    PID1=$!
    echo "Started $SCRIPT1 (PID $PID1, logging to $LOG1)"

    bash "$SCRIPT2" > "$LOG2" 2>&1 &
    PID2=$!
    echo "Started $SCRIPT2 (PID $PID2, logging to $LOG2)"

    bash "$SCRIPT3" > "$LOG3" 2>&1 &
    PID3=$!
    echo "Started $SCRIPT3 (PID $PID3, logging to $LOG3)"

    # --- MODIFIED LINE ---
    # Execute SCRIPT4 (run_tx.sh) and pass the power level as an argument
    bash "$SCRIPT4" "$power" > "$LOG4" 2>&1 &
    PID4=$!
    echo "Started $SCRIPT4 (PID $PID4, logging to $LOG4, passing power: $power)"
}

# Function to gracefully stop all background scripts
kill_scripts() {
    echo ">>> Stopping all running script processes..."
    kill 0
}

# Trap script exit (e.g., Ctrl+C) to ensure cleanup
trap 'echo -e "\n>>> Exiting and cleaning up all processes..."; kill_scripts; exit 1' SIGINT SIGTERM

# --- Main Automation Loop ---
while true; do
    # Loop through each defined power level
    for power in "${POWER_LEVELS[@]}"; do
        
        start_scripts "$power"

        echo ">>> Waiting for $SCRIPT4 (PID $PID4) to finish..."
        wait $PID4

        echo ">>> $SCRIPT4 has completed its run for power level $power."
        echo ">>> Archiving log files..."

        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

        mv "$LOG1" "$LOG_DIR/iotscan_lora_log_${TIMESTAMP}.txt"
        mv "$LOG2" "$LOG_DIR/multiplex_log_${TIMESTAMP}.txt"
        mv "$LOG3" "$LOG_DIR/catsniffer_log_${TIMESTAMP}.txt"
        mv "$LOG4" "$LOG_DIR/tx_log_power_${power}_${TIMESTAMP}.txt"

        echo ">>> Log files have been archived."
        echo ">>> Cleaning up other scripts before next run..."
        kill $PID1 $PID2 $PID3 >/dev/null 2>&1
        sleep 2
    done

    echo ">>> Completed a full cycle of power levels. Restarting..."
done
