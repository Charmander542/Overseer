#!/bin/bash

# This script is a wrapper for the Python TX script.
# It expects gain, delay, and spreading factor as arguments.
# Example: ./run_tx.sh 1.5 0.5 8

PYTHON_SCRIPT="./CollisionTX.py" # Ensure this path is correct

# Check for the correct number of arguments
if [ "$#" -ne 3 ]; then
    echo "Error: Incorrect number of arguments."
    echo "Usage: $0 <gain> <delay_seconds> <spreading_factor>"
    exit 1
fi

GAIN=$1
DELAY=$2
SF=$3

echo "--- run_tx.sh: Executing Python script with SF=$SF, Gain=$GAIN, and Delay=${DELAY}s ---"

# Activate conda environment if needed
# conda activate gr310

# Execute the Python script, passing all arguments
python3 "$PYTHON_SCRIPT" --gain "$GAIN" --delay "$DELAY" --spreading-factor "$SF" --packets 300

echo "--- run_tx.sh: Python script finished ---"
