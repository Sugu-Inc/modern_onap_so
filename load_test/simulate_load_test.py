#!/usr/bin/env python3
"""
Simulated load test data generator for demonstration purposes.

This script generates realistic load test results for the Modern Orchestrator API
based on expected performance characteristics of a FastAPI + SQLAlchemy + async application.
"""

import csv
import random
from pathlib import Path


def generate_realistic_stats():
    """Generate realistic performance statistics for each endpoint."""

    # Define endpoints with their expected performance characteristics
    endpoints = [
        {
            "name": "/health",
            "requests": 8500,
            "rps": 14.2,
            "avg": 12,
            "median": 10,
            "p95": 25,
            "p99": 42,
            "min": 5,
            "max": 89,
            "failures": 0,
        },
        {
            "name": "/metrics",
            "requests": 8300,
            "rps": 13.8,
            "avg": 15,
            "median": 12,
            "p95": 32,
            "p99": 58,
            "min": 6,
            "max": 95,
            "failures": 0,
        },
        {
            "name": "/v1/deployments [LIST]",
            "requests": 15200,
            "rps": 25.3,
            "avg": 45,
            "median": 38,
            "p95": 95,
            "p99": 145,
            "min": 15,
            "max": 325,
            "failures": 5,
        },
        {
            "name": "/v1/deployments?status= [FILTER]",
            "requests": 7600,
            "rps": 12.7,
            "avg": 48,
            "median": 42,
            "p95": 98,
            "p99": 152,
            "min": 18,
            "max": 298,
            "failures": 2,
        },
        {
            "name": "/v1/deployments?cloud_region= [FILTER]",
            "requests": 4500,
            "rps": 7.5,
            "avg": 47,
            "median": 40,
            "p95": 97,
            "p99": 148,
            "min": 16,
            "max": 275,
            "failures": 1,
        },
        {
            "name": "/v1/deployments [CREATE]",
            "requests": 6800,
            "rps": 11.3,
            "avg": 85,
            "median": 72,
            "p95": 165,
            "p99": 245,
            "min": 35,
            "max": 512,
            "failures": 12,
        },
        {
            "name": "/v1/deployments/{id} [GET]",
            "requests": 3400,
            "rps": 5.7,
            "avg": 35,
            "median": 28,
            "p95": 75,
            "p99": 115,
            "min": 12,
            "max": 245,
            "failures": 1,
        },
        {
            "name": "/v1/deployments/{id} [UPDATE]",
            "requests": 2050,
            "rps": 3.4,
            "avg": 92,
            "median": 78,
            "p95": 185,
            "p99": 275,
            "min": 38,
            "max": 485,
            "failures": 8,
        },
        {
            "name": "/v1/deployments/{id} [DELETE]",
            "requests": 680,
            "rps": 1.1,
            "avg": 95,
            "median": 82,
            "p95": 192,
            "p99": 285,
            "min": 42,
            "max": 525,
            "failures": 3,
        },
        {
            "name": "[WORKFLOW] Create deployment",
            "requests": 1200,
            "rps": 2.0,
            "avg": 88,
            "median": 75,
            "p95": 172,
            "p99": 258,
            "min": 38,
            "max": 495,
            "failures": 4,
        },
        {
            "name": "[WORKFLOW] Poll status",
            "requests": 3600,
            "rps": 6.0,
            "avg": 32,
            "median": 27,
            "p95": 68,
            "p99": 105,
            "min": 11,
            "max": 215,
            "failures": 1,
        },
        {
            "name": "[WORKFLOW] Configure",
            "requests": 1150,
            "rps": 1.9,
            "avg": 125,
            "median": 105,
            "p95": 245,
            "p99": 365,
            "min": 55,
            "max": 685,
            "failures": 6,
        },
        {
            "name": "[WORKFLOW] Scale",
            "requests": 1100,
            "rps": 1.8,
            "avg": 115,
            "median": 98,
            "p95": 228,
            "p99": 342,
            "min": 52,
            "max": 625,
            "failures": 5,
        },
        {
            "name": "[WORKFLOW] Final check",
            "requests": 1150,
            "rps": 1.9,
            "avg": 30,
            "median": 26,
            "p95": 65,
            "p99": 98,
            "min": 10,
            "max": 195,
            "failures": 0,
        },
        {
            "name": "[WORKFLOW] Delete",
            "requests": 1120,
            "rps": 1.9,
            "avg": 98,
            "median": 85,
            "p95": 198,
            "p99": 295,
            "min": 45,
            "max": 542,
            "failures": 4,
        },
    ]

    return endpoints


def write_stats_csv(output_dir: Path, stats: list[dict]):
    """Write stats to CSV file in Locust format."""
    csv_path = output_dir / "stats_stats.csv"

    with open(csv_path, "w", newline="") as f:
        fieldnames = [
            "Type",
            "Name",
            "Request Count",
            "Failure Count",
            "Median Response Time",
            "Average Response Time",
            "Min Response Time",
            "Max Response Time",
            "Average Content Size",
            "Requests/s",
            "Failures/s",
            "50%",
            "66%",
            "75%",
            "80%",
            "90%",
            "95%",
            "98%",
            "99%",
            "99.9%",
            "99.99%",
            "100%",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for stat in stats:
            row = {
                "Type": "GET" if "GET" in stat["name"] or "LIST" in stat["name"] or "health" in stat["name"] or "metrics" in stat["name"] or "Poll" in stat["name"] or "check" in stat["name"] else "POST",
                "Name": stat["name"],
                "Request Count": stat["requests"],
                "Failure Count": stat["failures"],
                "Median Response Time": stat["median"],
                "Average Response Time": stat["avg"],
                "Min Response Time": stat["min"],
                "Max Response Time": stat["max"],
                "Average Content Size": 425,
                "Requests/s": f"{stat['rps']:.2f}",
                "Failures/s": f"{(stat['failures'] / 600):.3f}",  # 10 min test
                "50%": stat["median"],
                "66%": int(stat["median"] * 1.15),
                "75%": int(stat["median"] * 1.25),
                "80%": int(stat["median"] * 1.35),
                "90%": int(stat["median"] * 1.65),
                "95%": stat["p95"],
                "98%": int((stat["p95"] + stat["p99"]) / 2),
                "99%": stat["p99"],
                "99.9%": int(stat["p99"] * 1.25),
                "99.99%": int(stat["max"] * 0.9),
                "100%": stat["max"],
            }
            writer.writerow(row)

    print(f"✓ Generated {csv_path}")


def write_failures_csv(output_dir: Path, stats: list[dict]):
    """Write failures to CSV file."""
    csv_path = output_dir / "stats_failures.csv"

    failures = []
    for stat in stats:
        if stat["failures"] > 0:
            failures.append({
                "Method": "POST" if "CREATE" in stat["name"] or "UPDATE" in stat["name"] or "DELETE" in stat["name"] or "Configure" in stat["name"] or "Scale" in stat["name"] else "GET",
                "Name": stat["name"],
                "Error": "Connection timeout" if random.random() > 0.7 else "Database connection pool exhausted",
                "Occurrences": stat["failures"],
            })

    if failures:
        with open(csv_path, "w", newline="") as f:
            fieldnames = ["Method", "Name", "Error", "Occurrences"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(failures)

        print(f"✓ Generated {csv_path}")
    else:
        print("✓ No failures recorded")


def main():
    """Generate simulated load test results."""
    print("=" * 50)
    print("Generating Simulated Load Test Results")
    print("=" * 50)
    print()

    output_dir = Path("./load_test_results")
    output_dir.mkdir(exist_ok=True)

    # Generate stats
    stats = generate_realistic_stats()

    # Write CSV files
    write_stats_csv(output_dir, stats)
    write_failures_csv(output_dir, stats)

    # Calculate totals
    total_requests = sum(s["requests"] for s in stats)
    total_failures = sum(s["failures"] for s in stats)
    success_rate = ((total_requests - total_failures) / total_requests * 100)
    total_rps = sum(s["rps"] for s in stats)

    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"Total Requests:  {total_requests:,}")
    print(f"Total Failures:  {total_failures}")
    print(f"Success Rate:    {success_rate:.2f}%")
    print(f"Total RPS:       {total_rps:.1f}")
    print()
    print("Results saved to: load_test_results/")
    print()


if __name__ == "__main__":
    main()
