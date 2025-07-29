#!/bin/bash

# === Configuration ===
PORT="/dev/ttyACM0"
BAUD=115200

# === Ensure serial port exists ===
if [ ! -e "$PORT" ]; then
  echo "[catsniffer] Error: Serial port $PORT does not exist."
  exit 1
fi

echo "[catsniffer] Listening on $PORT at ${BAUD} baud..."

# === Configure port ===
stty -F "$PORT" cs8 "$BAUD" igncr -ixon -icanon -echo

echo "freq " > ${PORT}
echo "efreq " > ${PORT}
echo "set_step 0.2" > ${PORT}
echo "set_range " > ${PORT}

# === Start listening ===
cat "$PORT"
