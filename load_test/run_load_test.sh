#!/bin/bash
set -e

# Load test configuration
HOST="${HOST:-http://localhost:8000}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-5}"
RUN_TIME="${RUN_TIME:-10m}"
OUTPUT_DIR="./load_test_results"

echo "============================================"
echo "Modern Orchestrator Load Test"
echo "============================================"
echo "Host: $HOST"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE users/second"
echo "Duration: $RUN_TIME"
echo "============================================"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Install dependencies if needed
if ! command -v locust &> /dev/null; then
    echo "Installing Locust..."
    pip install -r requirements.txt
fi

# Check if host is reachable
echo "Checking if application is running at $HOST..."
if ! curl -f -s "$HOST/health" > /dev/null; then
    echo "ERROR: Application is not reachable at $HOST/health"
    echo "Please start the application first with: docker-compose up -d"
    exit 1
fi
echo "✓ Application is running"
echo ""

# Run Locust in headless mode
echo "Starting load test..."
echo "Results will be saved to: $OUTPUT_DIR"
echo ""

locust \
    -f locustfile.py \
    --host="$HOST" \
    --users="$USERS" \
    --spawn-rate="$SPAWN_RATE" \
    --run-time="$RUN_TIME" \
    --headless \
    --html="$OUTPUT_DIR/report.html" \
    --csv="$OUTPUT_DIR/stats" \
    --logfile="$OUTPUT_DIR/locust.log" \
    --loglevel INFO

echo ""
echo "============================================"
echo "Load test completed!"
echo "============================================"
echo "Results available at:"
echo "  - HTML Report: $OUTPUT_DIR/report.html"
echo "  - CSV Stats: $OUTPUT_DIR/stats_*.csv"
echo "  - Log File: $OUTPUT_DIR/locust.log"
echo ""
echo "Generating markdown report..."
