#!/bin/bash

# === Configuration ===
PORT="/dev/ttyACM1"
BAUD=115200

# === Ensure serial port exists ===
if [ ! -e "$PORT" ]; then
  echo "[arduino] Error: Serial port $PORT does not exist."
  exit 1
fi

echo "[arduino] Listening on $PORT at ${BAUD} baud..."

# === Configure port ===
stty -F "$PORT" cs8 "$BAUD" igncr -ixon -icanon -echo

echo "GO" > ${PORT}

# === Start listening ===
cat "$PORT"
