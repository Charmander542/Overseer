#!/bin/bash

# === Configuration ===
SCRIPT1="./run_iotscan_lora.sh"
SCRIPT2="./run_multiplex_lora.sh"
SCRIPT3="./run_catsniffer.sh"
SCRIPT4="./run_tx.sh"

LOG1="logs/iotscan_lora_log.txt"
LOG2="logs/multiplex_log.txt"
LOG3="logs/catsniffer_log.txt"
LOG4="logs/tx_log.txt"

# Create logs directory if it doesn't exist
mkdir -p logs

# === Run scripts in parallel ===
echo ">>> Running all scripts in parallel..."

bash "$SCRIPT1" > "$LOG1" 2>&1 &
PID1=$!
echo "Started $SCRIPT1 (PID $PID1, logging to $LOG1)"

bash "$SCRIPT2" > "$LOG2" 2>&1 &
PID2=$!
echo "Started $SCRIPT2 (PID $PID2, logging to $LOG2)"

bash "$SCRIPT3" > "$LOG3" 2>&1 &
PID3=$!
echo "Started $SCRIPT3 (PID $PID3, logging to $LOG3)"

bash "$SCRIPT4" > "$LOG4" 2>&1 &
PID4=$!
echo "Started $SCRIPT4 (PID $PID4, logging to $LOG4)"

# === Wait for all scripts to finish (optional) ===
wait $PID4

echo ">>> All scripts complete."