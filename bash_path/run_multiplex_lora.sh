#!/bin/bash

# === DEBUGGING ===
# 'set -e' will exit the script immediately if a command fails.
# 'set -x' will print each command before it is executed.
# This combination is a powerful tool for debugging.
set -ex

# --- Configuration ---
CONTAINER_NAME="gr-lora-interactive-$$"
IMAGE_NAME="rpp0/gr-lora:latest"
GIT_REPO_URL="https://github.com/Charmander542/LoRaMultiplex.git"
REPO_DIR_NAME="LoRaMultiplex"
WORK_DIR="/root"
SCRIPT_TO_RUN="multiplex.py"

# --- Cleanup Function ---
function cleanup {
  echo "--- [CLEANUP] Script exiting. Stopping and removing container ${CONTAINER_NAME}... ---"
  if [ "$(docker ps -q -f name=${CONTAINER_NAME})" ]; then
    docker stop ${CONTAINER_NAME} > /dev/null
  fi
  echo "--- [CLEANUP] Complete. ---"
}
  trap cleanup EXIT

# --- X11 GUI Forwarding Setup ---
echo "--- Setting up X11 forwarding... ---"
DOCKER_XAUTH=/tmp/.docker.xauth
touch $DOCKER_XAUTH
xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f $DOCKER_XAUTH nmerge -
xhost +local:docker > /dev/null

# --- Main Logic ---
echo "--- Starting a long-running Docker container named ${CONTAINER_NAME}... ---"

docker run \
  -d \
  --rm \
  --name ${CONTAINER_NAME} \
  --privileged \
  --network=host \
  -e DISPLAY=$DISPLAY \
  -e XAUTHORITY=$DOCKER_XAUTH \
  -v /tmp/.docker.xauth:/tmp/.docker.xauth:ro \
  -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  -v /dev/bus/usb:/dev/bus/usb \
  -v $HOME/GNURADIO:/root \
  ${IMAGE_NAME} \
  tail -f /dev/null

echo "--- Waiting for container to initialize... ---"
sleep 5

echo "--- Container is running. Executing commands inside it... ---"

echo "--- [STEP 1] Cloning git repository into ${WORK_DIR}/${REPO_DIR_NAME}... ---"

#docker exec ${CONTAINER_NAME} ls
# This is the command that is likely failing. 'set -ex' will now show us the error.
docker exec ${CONTAINER_NAME} git clone ${GIT_REPO_URL} ${WORK_DIR}/${REPO_DIR_NAME}

echo "--- [DEBUG] Verifying contents of clone directory... ---"


echo "--- [STEP 2] Running the Python script (${SCRIPT_TO_RUN}) inside the container... ---"
docker exec ${CONTAINER_NAME} /bin/bash -c "cd ${WORK_DIR}/${REPO_DIR_NAME} && python3 ${SCRIPT_TO_RUN}"

echo "--- Script execution finished. The script will now exit and trigger cleanup. ---"