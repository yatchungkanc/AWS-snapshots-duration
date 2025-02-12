import boto3
from tabulate import tabulate
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import csv
import os
import sys
import traceback

def get_efs_snapshots_for_region(region):
    """Get all EFS snapshots for a specific region"""
    try:
        efs_client = boto3.client('efs', region_name=region)
        backup_client = boto3.client('backup', region_name=region)
        snapshots = []
        
        # Get all EFS file systems
        try:
            paginator = efs_client.get_paginator('describe_file_systems')
            fs_pages = paginator.paginate()
            
            for fs_page in fs_pages:
                for fs in fs_page['FileSystems']:
                    fs_id = fs['FileSystemId']
                    fs_name = next((tag['Value'] for tag in fs.get('Tags', []) 
                                 if tag['Key'] == 'Name'), 'N/A')
                    
                    # Get backup policy for the file system
                    try:
                        backup_policy = efs_client.describe_backup_policy(
                            FileSystemId=fs_id
                        )
                        
                        # Get recovery points (snapshots) using AWS Backup
                        try:
                            backup_response = backup_client.list_recovery_points_by_resource(
                                ResourceArn=fs['FileSystemArn']
                            )
                            
                            for recovery_point in backup_response.get('RecoveryPoints', []):
                                # Calculate size in GB
                                size_gb = round(recovery_point.get('BackupSizeInBytes', 0) / (1024**3), 2)
                                
                                snapshots.append({
                                    'Service': 'EFS',
                                    'Region': region,
                                    'Type': 'Automated' if recovery_point.get('CreatedBy', '').startswith('aws/backup') else 'Manual',
                                    'Snapshot ID': recovery_point['RecoveryPointArn'].split('/')[-1],
                                    'Source': fs_id,
                                    'Source Name': fs_name,
                                    'Engine': 'EFS',
                                    'Size (GB)': size_gb,
                                    'Status': recovery_point.get('Status', 'N/A'),
                                    'Creation Time': recovery_point['CreationDate'],
                                    'Encrypted': True,  # EFS is always encrypted
                                    'Description': recovery_point.get('BackupVaultName', 'N/A'),
                                    'LifeCycleState': recovery_point.get('LifecycleState', 'N/A'),
                                    'RestoreProgress': 'N/A',
                                    'PerformanceMode': fs.get('PerformanceMode', 'N/A')
                                })
                                
                        except ClientError as e:
                            print(f"Error getting backup recovery points for EFS {fs_id} in {region}: {e}")
                            continue
                            
                    except ClientError as e:
                        print(f"Error getting backup policy for EFS {fs_id} in {region}: {e}")
                        continue
                        
        except ClientError as e:
            print(f"Error getting EFS file systems in {region}: {e}")
            return []

        return snapshots

    except ClientError as e:
        print(f"Error getting EFS snapshots for region {region}: {e}")
        return []

def get_snapshots_for_region(region):
    """Get RDS, EC2, and EFS snapshots for a region"""
    rds_snapshots = get_rds_snapshots_for_region(region)
    ec2_snapshots = get_ec2_snapshots_for_region(region)
    efs_snapshots = get_efs_snapshots_for_region(region)
    return rds_snapshots + ec2_snapshots + efs_snapshots


def get_all_regions():
    """Get list of all AWS regions"""
    ec2_client = boto3.client('ec2')
    try:
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except ClientError as e:
        print(f"Error getting regions: {e}")
        return []

def get_rds_snapshots_for_region(region):
    """Get all RDS snapshots for a specific region"""
    try:
        rds_client = boto3.client('rds', region_name=region)
        snapshots = []
        paginator = rds_client.get_paginator('describe_db_snapshots')
        
        # Get manual snapshots
        manual_pages = paginator.paginate(SnapshotType='manual')
        for page in manual_pages:
            for snapshot in page['DBSnapshots']:
                snapshots.append({
                    'Service': 'RDS',
                    'Region': region,
                    'Type': 'Manual',
                    'Snapshot ID': snapshot['DBSnapshotIdentifier'],
                    'Source': snapshot['DBInstanceIdentifier'],
                    'Engine': snapshot.get('Engine', 'N/A'),
                    'Size (GB)': snapshot['AllocatedStorage'],
                    'Status': snapshot['Status'],
                    'Creation Time': snapshot['SnapshotCreateTime'],
                    'Encrypted': snapshot.get('Encrypted', False)
                })

        # Get automated snapshots
        auto_pages = paginator.paginate(SnapshotType='automated')
        for page in auto_pages:
            for snapshot in page['DBSnapshots']:
                snapshots.append({
                    'Service': 'RDS',
                    'Region': region,
                    'Type': 'Automated',
                    'Snapshot ID': snapshot['DBSnapshotIdentifier'],
                    'Source': snapshot['DBInstanceIdentifier'],
                    'Engine': snapshot.get('Engine', 'N/A'),
                    'Size (GB)': snapshot['AllocatedStorage'],
                    'Status': snapshot['Status'],
                    'Creation Time': snapshot['SnapshotCreateTime'],
                    'Encrypted': snapshot.get('Encrypted', False)
                })

        return snapshots

    except ClientError as e:
        print(f"Error getting RDS snapshots for region {region}: {e}")
        return []

def get_ec2_snapshots_for_region(region):
    """Get all EBS snapshots owned by the account for a specific region"""
    try:
        ec2_client = boto3.client('ec2', region_name=region)
        snapshots = []
        
        # Get account ID
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        
        paginator = ec2_client.get_paginator('describe_snapshots')
        pages = paginator.paginate(OwnerIds=[account_id])
        
        # Get all volumes in the region for additional details
        volumes = {}
        try:
            volume_paginator = ec2_client.get_paginator('describe_volumes')
            volume_pages = volume_paginator.paginate()
            for page in volume_pages:
                for volume in page['Volumes']:
                    volumes[volume['VolumeId']] = {
                        'Size': volume['Size'],
                        'Type': volume['VolumeType'],
                        'IOPS': volume.get('Iops', 'N/A'),
                        'Throughput': volume.get('Throughput', 'N/A')
                    }
        except Exception as e:
            print(f"Warning: Could not fetch volume details in {region}: {e}")
        
        for page in pages:
            for snapshot in page['Snapshots']:
                # Get tags
                tags = snapshot.get('Tags', [])
                name_tag = next((tag['Value'] for tag in tags if tag['Key'] == 'Name'), 'N/A')
                
                # Get volume details if available
                volume_id = snapshot.get('VolumeId', 'N/A')
                volume_details = volumes.get(volume_id, {})
                
                snapshots.append({
                    'Service': 'EBS',
                    'Region': region,
                    'Type': 'Manual' if not snapshot.get('Description', '').startswith('Created by CreateImage') else 'Automated',
                    'Snapshot ID': snapshot['SnapshotId'],
                    'Source': volume_id,
                    'Source Name': name_tag,
                    'Engine': volume_details.get('Type', 'EBS'),
                    'Size (GB)': snapshot['VolumeSize'],
                    'Status': snapshot['State'],
                    'Creation Time': snapshot['StartTime'],
                    'Encrypted': snapshot.get('Encrypted', False),
                    'Description': snapshot.get('Description', 'N/A'),
                    'Volume Type': volume_details.get('Type', 'N/A'),
                    'Volume IOPS': volume_details.get('IOPS', 'N/A'),
                    'Volume Throughput': volume_details.get('Throughput', 'N/A')
                })

        return snapshots

    except ClientError as e:
        print(f"Error getting EBS snapshots for region {region}: {e}")
        return []

def generate_date_ranges(latest_date):
    """Generate date ranges for snapshot grouping"""
    ranges = [
        (7, '7 days'),
        (15, '15 days'),
        (30, '30 days'),
        (90, '90 days'),
        (180, '180 days'),
        (365, '365 days'),
        (730, '730 days')
    ]
    
    date_ranges = []
    for days, label in ranges:
        start_date = latest_date - timedelta(days=days)
        date_ranges.append((start_date, latest_date, label))
        latest_date = start_date
    
    return date_ranges

def generate_summary(snapshots):
    """Generate summary of snapshots by volume/instance and date ranges"""
    if not snapshots:
        return {}
    
    # Find the latest snapshot date
    latest_date = max(s['Creation Time'] for s in snapshots)
    date_ranges = generate_date_ranges(latest_date)
    
    # Group snapshots by service and source
    summary = defaultdict(lambda: defaultdict(list))
    
    for snapshot in snapshots:
        service = snapshot['Service']
        source = snapshot['Source']
        creation_time = snapshot['Creation Time']
        
        # Determine which date range this snapshot falls into
        range_found = False
        for start_date, end_date, label in date_ranges:
            if start_date <= creation_time <= end_date:
                summary[f"{service}-{source}"][label].append({
                    'Snapshot ID': snapshot['Snapshot ID'],
                    'Creation Time': creation_time,
                    'Size (GB)': snapshot['Size (GB)'],
                    'Type': snapshot['Type']
                })
                range_found = True
                break
        
        # If snapshot is older than all ranges, put it in >730 days category
        if not range_found:
            summary[f"{service}-{source}"]['> 730 days'].append({
                'Snapshot ID': snapshot['Snapshot ID'],
                'Creation Time': creation_time,
                'Size (GB)': snapshot['Size (GB)'],
                'Type': snapshot['Type']
            })
    
    return summary

def export_to_csv(snapshots, headers, filename):
    """Export snapshots data to CSV file"""
    try:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write headers
            writer.writerow(headers)
            
            # Write data
            for snapshot in snapshots:
                row = []
                for header in headers:
                    value = snapshot.get(header, 'N/A')
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(value, bool):
                        value = 'Yes' if value else 'No'
                    row.append(value)
                writer.writerow(row)
                
        print(f"\nData exported to: {filename}")
    except Exception as e:
        print(f"Error exporting to CSV: {e}")

def export_summary_to_csv(summary, filename):
    """Export summary data to CSV file with date range as primary grouping"""
    try:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write headers
            headers = ['Date Range', 'Service-Source', 'Snapshot Count', 
                      'Total Size (GB)', 'Snapshot IDs', 'Types', 'Service']
            writer.writerow(headers)
            
            # Reorganize data by date range first
            date_range_groups = defaultdict(list)
            date_ranges = ['7 days', '15 days', '30 days', '90 days', 
                         '180 days', '365 days', '730 days', '> 730 days']
            
            # Collect data for each date range
            for source, ranges in summary.items():
                service = source.split('-')[0]  # Extract service from source
                for date_range in date_ranges:
                    snapshots = ranges.get(date_range, [])
                    if snapshots:
                        date_range_groups[date_range].append({
                            'Service-Source': source,
                            'Snapshots': snapshots,
                            'Service': service
                        })
            
            # Write data grouped by date range
            for date_range in date_ranges:
                sources = date_range_groups.get(date_range, [])
                if sources:
                    # Add a blank line before each date range group (except the first one)
                    if date_range != '7 days':
                        writer.writerow([])
                    
                    # Write date range header
                    writer.writerow([f"=== {date_range} ==="])
                    
                    # Sort by service first, then by source
                    sorted_sources = sorted(sources, 
                                         key=lambda x: (x['Service'], x['Service-Source']))
                    
                    # Write data for each source in this date range
                    for source_data in sorted_sources:
                        snapshots = source_data['Snapshots']
                        snapshot_ids = ', '.join(s['Snapshot ID'] for s in snapshots)
                        total_size = sum(s['Size (GB)'] for s in snapshots)
                        types = ', '.join(sorted(set(s['Type'] for s in snapshots)))
                        
                        writer.writerow([
                            date_range,
                            source_data['Service-Source'],
                            len(snapshots),
                            total_size,
                            snapshot_ids,
                            types,
                            source_data['Service']
                        ])
                    
                    # Add summary for this date range by service
                    services = set(s['Service'] for s in sources)
                    writer.writerow(['', f'Summary for {date_range}:', '', '', '', ''])
                    
                    for service in sorted(services):
                        service_snapshots = [s for s in sources if s['Service'] == service]
                        total_snapshots = sum(len(s['Snapshots']) for s in service_snapshots)
                        total_size = sum(sum(snap['Size (GB)'] for snap in s['Snapshots']) 
                                      for s in service_snapshots)
                        writer.writerow(['', f'{service}:', total_snapshots, total_size, '', ''])
                    
                    # Add total for all services
                    total_snapshots = sum(len(s['Snapshots']) for s in sources)
                    total_size = sum(sum(snap['Size (GB)'] for snap in s['Snapshots']) 
                                  for s in sources)
                    writer.writerow(['', f'Total:', total_snapshots, total_size, '', ''])
        
        print(f"\nSummary exported to: {filename}")
    except Exception as e:
        print(f"Error exporting summary to CSV: {e}")

def main():
    try:
        print("Collecting RDS, EC2, and EFS snapshot information across all regions...")
        
        # Get AWS account ID
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        
        # Get all regions
        regions = get_all_regions()
        if not regions:
            print("Unable to retrieve AWS regions. Please check your AWS credentials and permissions.")
            return

        # Collect snapshots from all regions using thread pool
        all_snapshots = []
        with ThreadPoolExecutor(max_workers=min(len(regions), 10)) as executor:
            future_to_region = {executor.submit(get_snapshots_for_region, region): region 
                              for region in regions}
            
            for future in as_completed(future_to_region):
                region = future_to_region[future]
                try:
                    region_snapshots = future.result()
                    all_snapshots.extend(region_snapshots)
                    print(f"Completed scanning region: {region}")
                except Exception as e:
                    print(f"Error processing region {region}: {e}")
                    traceback.print_exc(file=sys.stdout)

        if not all_snapshots:
            print("No snapshots found in any region.")
            return

        # Sort snapshots by Service, Type and Creation Time (descending)
        sorted_snapshots = sorted(
            all_snapshots,
            key=lambda x: (x['Service'], x['Type'], x['Creation Time']),
            reverse=True
        )

        # Prepare headers
        headers = [
            'Service',
            'Region',
            'Type',
            'Snapshot ID',
            'Source',
            'Source Name',
            'Engine',
            'Size (GB)',
            'Status',
            'Creation Time',
            'Encrypted',
            'Description',
            'Volume Type',
            'Volume IOPS',
            'Volume Throughput'
        ]

        # Format the data for display
        table_data = []
        for snapshot in sorted_snapshots:
            table_data.append([
                snapshot['Service'],
                snapshot['Region'],
                snapshot['Type'],
                snapshot['Snapshot ID'],
                snapshot['Source'],
                snapshot['Engine'],
                snapshot['Size (GB)'],
                snapshot['Status'],
                snapshot['Creation Time'].strftime('%Y-%m-%d %H:%M:%S'),
                'Yes' if snapshot['Encrypted'] else 'No'
            ])

        # Print the table
        print("\nSnapshot Details Across All Regions:")
        print(tabulate(table_data, headers=headers, tablefmt='grid'))

        # Generate timestamp and filenames with account ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'aws_snapshots_{account_id}_{timestamp}.csv'
        summary_filename = f'aws_snapshots_summary_{account_id}_{timestamp}.csv'
        
        # Export to CSV
        export_to_csv(sorted_snapshots, headers, csv_filename)

        # Generate and export summary
        print("\nGenerating summary report...")
        summary = generate_summary(sorted_snapshots)
        export_summary_to_csv(summary, summary_filename)

        # Print detailed summary to console with date range grouping
        print("\nDetailed Summary by Age:")
        date_ranges = ['7 days', '15 days', '30 days', '90 days', 
                      '180 days', '365 days', '730 days', '> 730 days']
        
        for date_range in date_ranges:
            range_snapshots = []
            range_total_size = 0
            
            print(f"\n=== {date_range} ===")
            for source, ranges in sorted(summary.items()):
                snapshots = ranges.get(date_range, [])
                if snapshots:
                    size = sum(s['Size (GB)'] for s in snapshots)
                    range_snapshots.extend(snapshots)
                    range_total_size += size
                    print(f"  {source}:")
                    print(f"    Snapshots: {len(snapshots)}")
                    print(f"    Size: {size:,} GB")
            
            if range_snapshots:
                print(f"\n  Summary for {date_range}:")
                print(f"    Total Snapshots: {len(range_snapshots)}")
                print(f"    Total Size: {range_total_size:,} GB")

        # Print overall summary
        print(f"\nOverall Summary:")
        total_snapshots = len(all_snapshots)
        ebs_snapshots = sum(1 for s in all_snapshots if s['Service'] == 'EBS')
        rds_snapshots = sum(1 for s in all_snapshots if s['Service'] == 'RDS')
        efs_snapshots = sum(1 for s in all_snapshots if s['Service'] == 'EFS')
        manual_snapshots = sum(1 for s in all_snapshots if s['Type'] == 'Manual')
        automated_snapshots = sum(1 for s in all_snapshots if s['Type'] == 'Automated')
        
        print(f"Total snapshots: {total_snapshots}")
        print(f"EBS snapshots: {ebs_snapshots}")
        print(f"RDS snapshots: {rds_snapshots}")
        print(f"EFS snapshots: {efs_snapshots}")
        print(f"Manual snapshots: {manual_snapshots}")
        print(f"Automated snapshots: {automated_snapshots}")
        
        # Calculate total storage
        total_storage = sum(s['Size (GB)'] for s in all_snapshots)
        ebs_storage = sum(s['Size (GB)'] for s in all_snapshots if s['Service'] == 'EBS')
        rds_storage = sum(s['Size (GB)'] for s in all_snapshots if s['Service'] == 'RDS')
        efs_storage = sum(s['Size (GB)'] for s in all_snapshots if s['Service'] == 'EFS')
        
        print(f"\nStorage Usage:")
        print(f"Total storage used: {total_storage:,} GB")
        print(f"EBS storage used: {ebs_storage:,} GB")
        print(f"RDS storage used: {rds_storage:,} GB")
        print(f"EFS storage used: {efs_storage:,} GB")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc(file=sys.stdout)

if __name__ == "__main__":
    # Ensure AWS credentials are configured before running
    print("Checking AWS credentials...")
    try:
        # Get caller identity
        identity = boto3.client('sts').get_caller_identity()
        account_id = identity['Account']
        print(f"Using AWS account: {account_id}")
        print(f"Using IAM user: {identity['Arn']}")
        
        main()
    except ClientError as e:
        print("Error: Unable to validate AWS credentials.")
        print("Please ensure you have configured your AWS credentials correctly.")
        print(f"Error details: {str(e)}")
        traceback.print_exc(file=sys.stdout)
