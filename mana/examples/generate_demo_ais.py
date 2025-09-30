"""
Generate synthetic AIS data for Dead Reckoning Demo
Creates realistic ship tracks with some missing positions to demonstrate dead reckoning
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_vessel_name(ship_type: str, vessel_number: int) -> str:
    """Generate a realistic vessel name based on ship type"""
    
    # Ship type specific prefixes and suffixes
    vessel_names = {
        'Cargo': {
            'prefixes': ['MV', 'MS', 'SS'],
            'suffixes': ['Trade', 'Cargo', 'Express', 'Freight', 'Merchant', 'Commerce', 'Transport', 'Carrier']
        },
        'Tanker': {
            'prefixes': ['MT', 'ATB', 'VLCC', 'MV'],
            'suffixes': ['Oil', 'Petrol', 'Crude', 'Fuel', 'Energy', 'Marine', 'Tanker', 'Liquid']
        },
        'Passenger': {
            'prefixes': ['MV', 'MS', 'RV'],
            'suffixes': ['Express', 'Ferry', 'Cruise', 'Passenger', 'Voyager', 'Explorer', 'Adventure', 'Discovery']
        },
        'Fishing': {
            'prefixes': ['FV', 'RV'],
            'suffixes': ['Fisher', 'Catch', 'Sea', 'Ocean', 'Wave', 'Current', 'Marine', 'Fleet']
        },
        'Pleasure craft': {
            'prefixes': ['SY', 'MY'],
            'suffixes': ['Dream', 'Freedom', 'Spirit', 'Wind', 'Wave', 'Sea', 'Ocean', 'Adventure']
        }
    }
    
    # Get ship type specific names
    if ship_type in vessel_names:
        prefixes = vessel_names[ship_type]['prefixes']
        suffixes = vessel_names[ship_type]['suffixes']
    else:
        # Default names
        prefixes = ['MV', 'MS']
        suffixes = ['Vessel', 'Ship', 'Marine', 'Sea']
    
    # Generate name
    prefix = random.choice(prefixes)
    suffix = random.choice(suffixes)
    
    # Add a number or additional identifier
    if random.choice([True, False]):
        return f"{prefix} {suffix} {vessel_number}"
    else:
        # Add a location or additional word
        locations = ['Baltic', 'North', 'East', 'West', 'South', 'Central', 'Coastal']
        location = random.choice(locations)
        return f"{prefix} {location} {suffix}"

def generate_ship_track(start_lat, start_lon, start_time, duration_hours=2, ship_type="Cargo"):
    """Generate a realistic ship track with some missing positions"""
    
    # Ship parameters
    base_speed = random.uniform(8, 18)  # knots
    
    # Define realistic shipping routes near Klaipeda (all in navigable waters)
    routes = [
        # North route (towards Gotland) - staying offshore
        [(55.7, 21.1), (55.8, 21.0), (55.9, 20.8), (56.0, 20.6)],
        # East route (towards Kaliningrad) - staying in Baltic Sea
        [(55.7, 21.1), (55.6, 21.3), (55.5, 21.5), (55.4, 21.7)],
        # West route (towards Bornholm) - staying offshore
        [(55.7, 21.1), (55.6, 20.8), (55.5, 20.5), (55.4, 20.2)],
        # South route (towards Gdansk) - staying in Baltic Sea
        [(55.7, 21.1), (55.6, 21.2), (55.5, 21.3), (55.4, 21.4)],
        # Northeast route (towards Stockholm) - staying offshore
        [(55.7, 21.1), (55.8, 21.2), (55.9, 21.3), (56.0, 21.4)],
        # Southwest route (towards Copenhagen) - staying offshore
        [(55.7, 21.1), (55.6, 20.9), (55.5, 20.7), (55.4, 20.5)]
    ]
    
    # Choose a random route
    chosen_route = random.choice(routes)
    
    # Scale the route to match the desired duration
    total_distance_nm = base_speed * duration_hours
    
    # Calculate route distance
    route_distance = 0
    for i in range(len(chosen_route) - 1):
        lat_diff = chosen_route[i+1][0] - chosen_route[i][0]
        lon_diff = chosen_route[i+1][1] - chosen_route[i][1]
        route_distance += np.sqrt(lat_diff**2 + lon_diff**2) * 60
    
    # Scale factor to match desired distance
    scale_factor = total_distance_nm / route_distance if route_distance > 0 else 1
    
    # Generate scaled waypoints
    waypoints = []
    for i, (route_lat, route_lon) in enumerate(chosen_route):
        if i == 0:
            waypoints.append((start_lat, start_lon))
        else:
            lat_diff = route_lat - chosen_route[0][0]
            lon_diff = route_lon - chosen_route[0][1]
            
            scaled_lat = start_lat + lat_diff * scale_factor
            scaled_lon = start_lon + lon_diff * scale_factor
            
            waypoints.append((scaled_lat, scaled_lon))
    
    # Generate position reports along the track
    positions = []
    current_time = start_time
    
    for i in range(len(waypoints) - 1):
        start_wp = waypoints[i]
        end_wp = waypoints[i + 1]
        
        # Calculate course and distance between waypoints
        lat_diff = end_wp[0] - start_wp[0]
        lon_diff = end_wp[1] - start_wp[1]
        
        course = np.degrees(np.arctan2(lon_diff, lat_diff))
        if course < 0:
            course += 360
            
        distance_nm = np.sqrt(lat_diff**2 + lon_diff**2) * 60
        
        # Generate positions along this segment
        num_positions = max(5, int(distance_nm / 2))  # Position every ~2nm
        
        for j in range(num_positions):
            progress = j / (num_positions - 1) if num_positions > 1 else 0
            
            lat = start_wp[0] + lat_diff * progress
            lon = start_wp[1] + lon_diff * progress
            
            # Add some realistic variation
            lat += random.uniform(-0.001, 0.001)
            lon += random.uniform(-0.001, 0.001)
            
            # Calculate time (assume constant speed)
            time_offset = (distance_nm * progress) / base_speed
            position_time = start_time + timedelta(hours=time_offset)
            
            # Randomly skip some positions to simulate missing data
            if random.random() > 0.15:  # 85% of positions are present
                positions.append({
                    'timestamp': position_time,
                    'lat': lat,
                    'lon': lon,
                    'sog': base_speed + random.uniform(-2, 2),
                    'cog': course + random.uniform(-5, 5),
                    'is_dead_reckoned': False
                })
            else:
                # Mark as missing for dead reckoning
                positions.append({
                    'timestamp': position_time,
                    'lat': None,
                    'lon': None,
                    'sog': base_speed + random.uniform(-2, 2),
                    'cog': course + random.uniform(-5, 5),
                    'is_dead_reckoned': True
                })
    
    return positions

def create_demo_dataset():
    """Create a comprehensive demo dataset"""
    
    # Define ship types and their characteristics
    ship_types = {
        'Cargo': {'count': 8, 'speed_range': (8, 16)},
        'Tanker': {'count': 4, 'speed_range': (6, 14)},
        'Passenger': {'count': 3, 'speed_range': (12, 20)},
        'Fishing': {'count': 5, 'speed_range': (4, 10)},
        'Pleasure craft': {'count': 6, 'speed_range': (6, 12)}
    }
    
    # Starting area (simulate Baltic Sea near Klaipeda)
    base_lat = 55.7
    base_lon = 21.1
    
    all_data = []
    mmsi_counter = 100000000
    
    # Generate data for each ship type
    for ship_type, config in ship_types.items():
        for i in range(config['count']):
            mmsi = mmsi_counter + i
            
            # Random starting position near Klaipeda
            start_lat = base_lat + random.uniform(-0.1, 0.1)
            start_lon = base_lon + random.uniform(-0.1, 0.1)
            
            # Random start time within the last 24 hours
            start_time = datetime.now() - timedelta(hours=random.uniform(1, 24))
            
            # Generate track
            track = generate_ship_track(start_lat, start_lon, start_time, 
                                      duration_hours=random.uniform(1, 4), 
                                      ship_type=ship_type)
            
            # Add ship info to each position
            for pos in track:
                pos.update({
                    'mmsi': mmsi,
                    'ship_type': ship_type,
                    'ship_type_name': ship_type,
                    'vessel_name': generate_vessel_name(ship_type, i+1),
                    'nav_status': random.choice([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                    'position_accuracy': random.choice([0, 1]),
                    'true_heading': pos['cog'] + random.uniform(-10, 10)
                })
            
            all_data.extend(track)
        
        mmsi_counter += 100
    
    # Convert to DataFrame
    df = pd.DataFrame(all_data)
    
    # Sort by timestamp
    df = df.sort_values('timestamp')
    
    # Apply dead reckoning to missing positions
    df = apply_dead_reckoning(df)
    
    return df

def apply_dead_reckoning(df):
    """Apply dead reckoning to fill missing positions"""
    
    # Group by MMSI
    for mmsi in df['mmsi'].unique():
        ship_data = df[df['mmsi'] == mmsi].copy()
        
        last_lat = None
        last_lon = None
        last_time = None
        
        for idx, row in ship_data.iterrows():
            if pd.isna(row['lat']) or pd.isna(row['lon']):
                # Missing position - apply dead reckoning
                if last_lat is not None and last_lon is not None:
                    time_diff = (row['timestamp'] - last_time).total_seconds()
                    
                    if time_diff > 0 and time_diff < 3600:  # Within 1 hour
                        # Calculate new position
                        speed_ms = row['sog'] * 0.514444  # knots to m/s
                        distance = speed_ms * time_diff
                        
                        # Convert to degrees (approximate)
                        lat_change = distance * np.cos(np.radians(row['cog'])) / 111000
                        lon_change = distance * np.sin(np.radians(row['cog'])) / (111000 * np.cos(np.radians(last_lat)))
                        
                        new_lat = last_lat + lat_change
                        new_lon = last_lon + lon_change
                        
                        df.loc[idx, 'lat'] = new_lat
                        df.loc[idx, 'lon'] = new_lon
                        df.loc[idx, 'is_dead_reckoned'] = True
                        
                        # Update last known position
                        last_lat = new_lat
                        last_lon = new_lon
            else:
                # Valid position - update last known position
                last_lat = row['lat']
                last_lon = row['lon']
                last_time = row['timestamp']
    
    return df

if __name__ == "__main__":
    print("Generating synthetic AIS data for Dead Reckoning Demo...")
    
    # Create demo dataset
    df = create_demo_dataset()
    
    # Save to CSV
    output_file = "demo_ais_data.csv"
    df.to_csv(output_file, index=False)
    
    print(f"Generated {len(df)} position reports from {df['mmsi'].nunique()} ships")
    print(f"Dead reckoned positions: {df['is_dead_reckoned'].sum()}")
    print(f"DR percentage: {(df['is_dead_reckoned'].sum() / len(df)) * 100:.1f}%")
    print(f"Data saved to: {output_file}")
    
    # Show summary by ship type
    print("\nSummary by ship type:")
    summary = df.groupby('ship_type').agg({
        'mmsi': 'nunique',
        'is_dead_reckoned': 'sum',
        'timestamp': 'count'
    }).rename(columns={'mmsi': 'ships', 'timestamp': 'positions'})
    summary['dr_percentage'] = (summary['is_dead_reckoned'] / summary['positions']) * 100
    print(summary)
