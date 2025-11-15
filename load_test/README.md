# Load Testing for Modern Orchestrator

This directory contains load testing infrastructure for the Modern Orchestrator API.

## Overview

The load test uses [Locust](https://locust.io/), a modern Python-based load testing tool, to simulate realistic user workflows and measure API performance under load.

## User Scenarios

The load test includes 4 different user types that simulate realistic usage patterns:

### 1. HealthCheckUser (10% of traffic)
- Simulates monitoring systems
- Continuously polls `/health` and `/metrics` endpoints
- Wait time: 1-3 seconds between requests

### 2. ReadHeavyUser (50% of traffic)
- Simulates dashboard users and monitoring tools
- Operations:
  - List deployments with pagination (10x weight)
  - Filter by status (5x weight)
  - Filter by cloud region (3x weight)
  - Occasional health checks (1x weight)
- Wait time: 0.5-2 seconds between requests
- Uses 5 different read-only API keys to distribute load

### 3. WriteUser (30% of traffic)
- Simulates active users creating and managing infrastructure
- Operations:
  - Create deployments (10x weight)
  - Get deployment details (5x weight)
  - Update deployments (3x weight)
  - Delete deployments (1x weight)
- Wait time: 2-5 seconds between requests
- Uses 5 different write API keys to distribute load

### 4. FullWorkflowUser (10% of traffic)
- Simulates complete real-world deployment workflows
- Executes full lifecycle:
  1. Create deployment
  2. Poll status (3 times)
  3. Configure with Ansible
  4. Scale deployment
  5. Final status check
  6. Delete deployment
- Wait time: 3-8 seconds between workflows
- Uses 2 dedicated API keys

## Quick Start

### Prerequisites

1. Ensure the application is running:
   ```bash
   cd /home/user/onap_so_modern
   docker-compose up -d
   ```

2. Configure API keys (see below)

### Run Load Test

```bash
cd load_test
chmod +x run_load_test.sh
./run_load_test.sh
```

### Generate Report

After the load test completes, generate the markdown report:

```bash
python3 generate_report.py
```

This creates `load_test.md` in the project root with comprehensive metrics and analysis.

## Configuration

### Environment Variables

- `HOST`: Target host (default: `http://localhost:8000`)
- `USERS`: Maximum concurrent users (default: `50`)
- `SPAWN_RATE`: Users spawned per second (default: `5`)
- `RUN_TIME`: Test duration (default: `10m`)

Example:
```bash
HOST=http://api.example.com USERS=100 RUN_TIME=30m ./run_load_test.sh
```

### API Keys

The load test requires 12 API keys configured in the application:

**Read-only keys (5):**
- `load-test-key-1:read`
- `load-test-key-2:read`
- `load-test-key-3:read`
- `load-test-key-4:read`
- `load-test-key-5:read`

**Write keys (7):**
- `load-test-key-6:write`
- `load-test-key-7:write`
- `load-test-key-8:write`
- `load-test-key-9:write`
- `load-test-key-10:write`
- `load-test-key-11:write`
- `load-test-key-12:write`

Add these to your `.env` file:
```bash
API_KEYS=load-test-key-1:read,load-test-key-2:read,load-test-key-3:read,load-test-key-4:read,load-test-key-5:read,load-test-key-6:write,load-test-key-7:write,load-test-key-8:write,load-test-key-9:write,load-test-key-10:write,load-test-key-11:write,load-test-key-12:write
```

## Output Files

After running the load test, results are saved to `load_test_results/`:

- `report.html` - Interactive HTML report with charts
- `stats_stats.csv` - Aggregated statistics per endpoint
- `stats_failures.csv` - Failure details (if any)
- `stats_stats_history.csv` - Time-series performance data
- `locust.log` - Detailed execution logs

## Running Interactively

For real-time monitoring and manual control:

```bash
locust -f locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser to access the Locust web UI.

## Advanced Usage

### Custom Test Duration

```bash
# 30-minute soak test
USERS=50 RUN_TIME=30m ./run_load_test.sh

# 5-minute quick test
USERS=20 RUN_TIME=5m ./run_load_test.sh
```

### Stress Testing

Find the breaking point by gradually increasing users:

```bash
USERS=100 ./run_load_test.sh
USERS=200 ./run_load_test.sh
USERS=500 ./run_load_test.sh
```

### Distributed Load Testing

For very high loads, run Locust in distributed mode:

```bash
# Master node
locust -f locustfile.py --master --host=http://localhost:8000

# Worker nodes (run multiple)
locust -f locustfile.py --worker --master-host=localhost
```

## Metrics Explained

### Response Time Percentiles

- **Average**: Mean response time
- **Median (P50)**: 50% of requests faster than this
- **P95**: 95% of requests faster than this
- **P99**: 99% of requests faster than this - important for user experience
- **Max**: Slowest observed request

### Success Rate

Percentage of requests that completed successfully (HTTP 2xx/3xx responses).

Target: >99% for production systems.

### Requests Per Second (RPS)

Total throughput the API sustained during the test.

## Troubleshooting

### Application not reachable

```
ERROR: Application is not reachable at http://localhost:8000/health
```

**Solution**: Start the application with `docker-compose up -d`

### Rate limit errors

If you see many 429 errors, either:
1. Increase rate limits in the application config
2. Add more API keys to distribute load
3. Reduce concurrent users

### Connection errors

Check that:
1. Application is running
2. Database is accessible
3. No firewall blocking requests

## Best Practices

1. **Start Small**: Begin with 10-20 users, then gradually increase
2. **Clean State**: Run tests against a fresh database for consistent results
3. **Multiple Runs**: Execute tests 3-5 times and average results
4. **Monitor Resources**: Watch CPU, memory, and database metrics during tests
5. **Realistic Data**: Seed database with representative data volumes

## Next Steps

After running the load test:

1. Review `load_test.md` for performance analysis
2. Identify bottlenecks and optimization opportunities
3. Tune application configuration based on findings
4. Re-test to validate improvements
5. Establish performance baselines for regression testing
