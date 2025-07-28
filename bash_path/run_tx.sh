#!/bin/bash

# This script acts as a wrapper for the Python TX script.
# It expects the desired power level to be passed as its first argument.
# Example: ./run_tx.sh 80

# The underlying Python script that will be executed.
PYTHON_SCRIPT="./CollisionTX.py"

# Check if a power level argument was provided.
if [ -z "$1" ]; then
    echo "Error: No power level provided to run_tx.sh."
    echo "Usage: $0 <power_level>"
    exit 1
fi

# The power level is the first argument passed to this script ($1)
POWER_LEVEL=$1

echo "--- run_tx.sh: Executing Python script with power level $POWER_LEVEL ---"

conda activate gr310

# Execute the Python script, passing the power level to its --power argument.
# Make sure CollisionTX.py is executable (chmod +x CollisionTX.py)
"$PYTHON_SCRIPT" --power "$POWER_LEVEL"
