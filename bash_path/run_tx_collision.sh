#!/bin/bash

# This script is a wrapper for the Python TX script.
# It expects gain and delay to be passed as arguments.
# Example: ./run_tx.sh 1.5 0.5

PYTHON_SCRIPT="./CollisionTX.py" # Ensure this path is correct

# Check for the correct number of arguments
if [ "$#" -ne 2 ]; then
    echo "Error: Incorrect number of arguments."
    echo "Usage: $0 <gain> <delay_seconds>"
    exit 1
fi

GAIN=$1
DELAY=$2

echo "--- run_tx.sh: Executing Python script with Gain=$GAIN and Delay=${DELAY}s ---"

# Activate conda environment if needed
# conda activate gr310

# Execute the Python script, passing the arguments. [1]
python3 "$PYTHON_SCRIPT" --gain "$GAIN" --delay "$DELAY" --packets 300

echo "--- run_tx.sh: Python script finished ---"
