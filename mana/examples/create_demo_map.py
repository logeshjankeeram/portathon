"""
Create Dead Reckoning Demo Map from CSV data
"""

import pandas as pd
from dead_reckoning_map import DeadReckoningMap
import os

def create_demo_map_from_csv(csv_file):
    """Create dead reckoning demo map from CSV data"""
    
    print(f"Creating Dead Reckoning Demo from CSV: {csv_file}")
    
    # Load the CSV data
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} position reports from {df['mmsi'].nunique()} ships")
    
    # Create map
    map_demo = DeadReckoningMap()
    map_demo.ship_data = df
    
    # Convert timestamp to datetime
    map_demo.ship_data['timestamp'] = pd.to_datetime(map_demo.ship_data['timestamp'])
    
    # Sort by timestamp
    map_demo.ship_data = map_demo.ship_data.sort_values('timestamp')
    
    # Create ship tracks
    map_demo._create_ship_tracks()
    
    # Set time range
    map_demo.time_range = {
        'start': map_demo.ship_data['timestamp'].min(),
        'end': map_demo.ship_data['timestamp'].max()
    }
    
    # Create map
    map_demo.create_map(center_lat=55.7, center_lon=21.1, zoom=10)
    
    # Save map
    map_file = "demo_dead_reckoning_map.html"
    map_demo.save_map(map_file)
    
    # Generate summary
    summary = map_demo.get_ship_summary()
    summary_file = "demo_ship_summary.csv"
    summary.to_csv(summary_file, index=False)
    
    print(f"\n=== DEAD RECKONING DEMO SUMMARY ===")
    print(f"Total ships: {len(summary)}")
    print(f"Total position reports: {len(df)}")
    print(f"Dead reckoned positions: {df['is_dead_reckoned'].sum()}")
    print(f"DR percentage: {(df['is_dead_reckoned'].sum() / len(df)) * 100:.1f}%")
    
    print("\nTop 5 ships by dead reckoning usage:")
    print(summary.head().to_string(index=False))
    
    print(f"\nFiles created:")
    print(f"- Interactive map: {map_file}")
    print(f"- Summary: {summary_file}")
    
    return map_file, summary_file

if __name__ == "__main__":
    csv_file = "demo_ais_data.csv"
    if os.path.exists(csv_file):
        create_demo_map_from_csv(csv_file)
    else:
        print(f"CSV file {csv_file} not found. Please run generate_demo_ais.py first.")
