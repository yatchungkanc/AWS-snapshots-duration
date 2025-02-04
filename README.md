# AWS Snapshot Inventory Tool

This Python script provides a comprehensive inventory of AWS snapshots across multiple services and regions.

The AWS Snapshot Inventory Tool is designed to retrieve and summarize snapshots from Elastic File System (EFS), Relational Database Service (RDS), and Elastic Block Store (EBS) across all AWS regions. It offers a detailed view of snapshot metadata, including size, creation time, encryption status, and more.

Key features include:
- Multi-region snapshot retrieval
- Support for EFS, RDS, and EBS snapshots
- Detailed metadata for each snapshot
- Summary generation by service, source, and date range
- CSV export functionality for further analysis

## Repository Structure

The repository contains a single Python script:

- `snapshot_inventory.py`: The main script that performs all snapshot inventory operations.

## Usage Instructions

### Installation

1. Ensure you have Python 3.6 or later installed.
2. Install the required dependencies:

```bash
pip install boto3 tabulate
```

3. Configure your AWS credentials using one of the methods supported by boto3 (e.g., AWS CLI configuration, environment variables).

### Getting Started

To run the script:

```bash
python snapshot_inventory.py
```

The script will automatically retrieve snapshots from all available AWS regions and generate a summary.

### Configuration Options

The script does not require any additional configuration. It uses the default AWS credentials and regions available to the authenticated user.

### Common Use Cases

1. Generate a complete snapshot inventory:

```python
regions = get_all_regions()
all_snapshots = []

for region in regions:
    all_snapshots.extend(get_snapshots_for_region(region))

summary = generate_summary(all_snapshots)
```

2. Export snapshot data to CSV:

```python
with open('snapshot_inventory.csv', 'w', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=all_snapshots[0].keys())
    writer.writeheader()
    for snapshot in all_snapshots:
        writer.writerow(snapshot)
```

### Troubleshooting

Common issues and solutions:

1. AWS credentials not found:
   - Error message: "botocore.exceptions.NoCredentialsError: Unable to locate credentials"
   - Solution: Ensure AWS credentials are properly configured using AWS CLI (`aws configure`) or set as environment variables.

2. Region access denied:
   - Error message: "An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials"
   - Solution: Verify that your IAM user or role has the necessary permissions to describe regions and access the required services (EFS, RDS, EC2) in all regions.

3. Rate limiting:
   - Error message: "An error occurred (RequestLimitExceeded) when calling the DescribeSnapshots operation: Request limit exceeded."
   - Solution: Implement exponential backoff retry logic or reduce the concurrency of API calls.

Debugging:

To enable debug logging for boto3, set the following environment variable:

```bash
export BOTO_LOG_LEVEL=DEBUG
```

Log files are typically located in:
- Linux/macOS: `~/.boto` or `/tmp/`
- Windows: `%UserProfile%\.boto` or `%TEMP%`

Performance optimization:

- Monitor API call frequency using AWS CloudTrail.
- Use the `ThreadPoolExecutor` to parallelize API calls across regions for faster execution.
- Implement caching mechanisms for frequently accessed data, such as region lists or account IDs.

## Data Flow

The AWS Snapshot Inventory Tool processes data through the following flow:

1. Retrieve list of all AWS regions
2. For each region:
   a. Fetch EFS snapshots
   b. Fetch RDS snapshots (both manual and automated)
   c. Fetch EBS snapshots
3. Combine all snapshots into a single list
4. Generate summary statistics
5. Output results (console display or CSV export)

```
[AWS API] -> [Region List] -> [Per-Region Snapshot Retrieval] -> [Snapshot Aggregation] -> [Summary Generation] -> [Output]
```

Notes:
- The script uses boto3 clients for each service (EFS, RDS, EC2) to interact with the AWS API.
- Pagination is implemented to handle large numbers of snapshots.
- Error handling is in place to manage API failures gracefully.
- The summary generation groups snapshots by service, source, and date range for easier analysis.