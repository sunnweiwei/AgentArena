#!/bin/bash
# Script to kill swebench_env_server processes

echo "Finding swebench_env_server processes..."

# Find processes by name
PIDS=$(ps aux | grep "[s]webench_env_server" | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "No swebench_env_server processes found."
    exit 0
fi

echo "Found processes: $PIDS"

# Kill processes
for PID in $PIDS; do
    echo "Killing process $PID..."
    kill -TERM $PID 2>/dev/null || kill -9 $PID 2>/dev/null
done

# Wait a bit and check if processes are still running
sleep 2
REMAINING=$(ps aux | grep "[s]webench_env_server" | awk '{print $2}')

if [ -n "$REMAINING" ]; then
    echo "Some processes still running, force killing..."
    for PID in $REMAINING; do
        kill -9 $PID 2>/dev/null
    done
fi

echo "Done."

