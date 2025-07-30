#!/bin/bash

# === Configuration ===
PORT="/dev/ttyACM1"
BAUD=115200

# === Ensure serial port exists ===
if [ ! -e "$PORT" ]; then
  echo "[catsniffer] Error: Serial port $PORT does not exist."
  exit 1
fi

echo "[catsniffer] Listening on $PORT at ${BAUD} baud..."

# === Configure port ===
stty -F "$PORT" cs8 "$BAUD" igncr -ixon -icanon -echo

# === Start listening ===
cat "$PORT"
