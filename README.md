# AWS Snapshot Inventory Tool

This project provides a Python script for retrieving and summarizing AWS snapshots across multiple services and regions.

The AWS Snapshot Inventory Tool is designed to give users a comprehensive view of their snapshot inventory across different AWS services, including Elastic File System (EFS), Relational Database Service (RDS), and Elastic Block Store (EBS). It retrieves snapshot information from multiple AWS regions and generates a summary report, allowing users to monitor and manage their snapshot inventory efficiently.

Key features of this tool include:
- Multi-region snapshot retrieval
- Support for EFS, RDS, and EBS snapshots
- Detailed snapshot information including size, creation time, and encryption status
- Summary generation by service, source, and date range
- Concurrent processing for improved performance

## Repository Structure

```
.
├── README.md
├── requirements.txt
└── snapshot_inventory.py
```

- `requirements.txt`: Lists the Python package dependencies for the project.
- `snapshot_inventory.py`: The main Python script that retrieves and summarizes AWS snapshots.

## Usage Instructions

### Installation

1. Ensure you have Python 3.6 or later installed.
2. Clone this repository to your local machine.
3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

Before running the script, make sure you have configured your AWS credentials. You can do this by setting up the AWS CLI or by setting the following environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=your_default_region
```

### Running the Script

To run the snapshot inventory tool, execute the following command:

```bash
python snapshot_inventory.py
```

The script will retrieve snapshot information from all available AWS regions and generate a summary report.

### Output

The script generates a summary of snapshots grouped by service (EFS, RDS, EBS), source (file system, database instance, or volume), and date range. The output includes details such as:

- Snapshot ID
- Source identifier
- Engine type
- Size in GB
- Status
- Creation time
- Encryption status

### Troubleshooting

If you encounter any issues while running the script, consider the following:

1. Ensure your AWS credentials are correctly configured and have the necessary permissions to access snapshot information across services.
2. Check your internet connection, as the script needs to make API calls to AWS.
3. If you're getting throttling errors, you may need to implement rate limiting or increase the delay between API calls.

For more detailed error messages, you can enable debug logging by adding the following lines at the beginning of the `snapshot_inventory.py` script:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will provide more verbose output, which can help identify the source of any issues.

### Performance Optimization

To optimize the performance of the script:

1. The script uses concurrent processing to retrieve snapshots from multiple regions simultaneously. You can adjust the number of concurrent threads by modifying the `max_workers` parameter in the `ThreadPoolExecutor`.
2. Consider filtering snapshots by date range or other criteria to reduce the amount of data processed if you're dealing with a large number of snapshots.
3. If you're only interested in specific regions, you can modify the `get_all_regions()` function to return a subset of regions.

## Data Flow

The AWS Snapshot Inventory Tool follows this data flow:

1. Retrieve a list of all available AWS regions.
2. For each region, concurrently:
   a. Retrieve EFS snapshots
   b. Retrieve RDS snapshots (both manual and automated)
   c. Retrieve EBS snapshots
3. Combine all snapshot data from different services and regions.
4. Generate summary information based on the collected snapshot data.
5. Output the summary report.

```
[User] -> [snapshot_inventory.py] -> [AWS API (boto3)]
                 |
                 v
         [Snapshot Data]
                 |
                 v
      [Summary Generation]
                 |
                 v
        [Output Summary]
```

The script interacts with various AWS services through the boto3 library, which handles the API calls to retrieve snapshot information. The collected data is then processed and summarized within the script before being presented to the user.