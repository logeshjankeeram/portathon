"""
Hybrid AIS Data Processor
Extracts real ship data from AIS logs and generates synthetic tracks where needed
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import random
import os
from ais_parser import AISParser, DeadReckoningCalculator


class HybridAISProcessor:
    """Process real AIS data and generate synthetic tracks for missing data"""
    
    def __init__(self):
        self.parser = AISParser()
        self.dead_reckoning = DeadReckoningCalculator()
        self.ship_static_data = {}  # Store static data by MMSI
        self.ship_positions = {}    # Store position data by MMSI
        self.ship_tracks = {}       # Final processed tracks
    
    def process_log_file(self, log_file_path: str) -> pd.DataFrame:
        """Process AIS log file and create hybrid dataset"""
        
        print(f"Processing AIS log file: {log_file_path}")
        
        # First pass: Extract all ship data
        self._extract_ship_data(log_file_path)
        
        # Second pass: Generate synthetic tracks for ships with static data but no positions
        self._generate_synthetic_tracks()
        
        # Third pass: Apply dead reckoning to fill gaps
        self._apply_dead_reckoning()
        
        # Convert to DataFrame
        return self._create_dataframe()
    
    def _extract_ship_data(self, log_file_path: str):
        """Extract ship static data and position reports from log file"""
        
        with open(log_file_path, 'r') as f:
            for line_num, line in enumerate(f):
                if line_num % 50000 == 0:
                    print(f"Processed {line_num} lines...")
                
                parsed = self.parser.parse_nmea_line(line.strip())
                if not parsed:
                    continue
                
                mmsi = parsed['mmsi']
                
                # Handle static data (message type 5)
                if parsed['message_type'] == 5:
                    self.ship_static_data[mmsi] = parsed
                    continue
                
                # Handle position reports (message types 1, 2, 3)
                if parsed['message_type'] in [1, 2, 3]:
                    if parsed['lat'] is not None and parsed['lon'] is not None:
                        if mmsi not in self.ship_positions:
                            self.ship_positions[mmsi] = []
                        
                        # Transform coordinates to be near Klaipeda for demonstration
                        # Keep the relative positions but move them to Baltic Sea
                        transformed_lat, transformed_lon = self._transform_coordinates_to_klaipeda(
                            parsed['lat'], parsed['lon'], mmsi
                        )
                        
                        self.ship_positions[mmsi].append({
                            'timestamp': parsed['timestamp'],
                            'lat': transformed_lat,
                            'lon': transformed_lon,
                            'sog': parsed['sog'],
                            'cog': parsed['cog'],
                            'nav_status': parsed['nav_status'],
                            'position_accuracy': parsed['position_accuracy'],
                            'true_heading': parsed['true_heading'],
                            'is_dead_reckoned': False,
                            'is_synthetic': False
                        })
        
        print(f"Extracted static data for {len(self.ship_static_data)} ships")
        print(f"Extracted position data for {len(self.ship_positions)} ships")
    
    def _transform_coordinates_to_klaipeda(self, original_lat: float, original_lon: float, mmsi: int) -> tuple:
        """Transform coordinates to be near Klaipeda while preserving relative positions"""
        
        # Klaipeda coordinates
        klaipeda_lat = 55.7
        klaipeda_lon = 21.1
        
        # Store the first position for each ship to use as reference
        if not hasattr(self, '_ship_references'):
            self._ship_references = {}
        
        if mmsi not in self._ship_references:
            # First position for this ship - use as reference
            self._ship_references[mmsi] = {
                'ref_lat': original_lat,
                'ref_lon': original_lon,
                'klaipeda_lat': klaipeda_lat + random.uniform(-0.05, 0.05),  # Small random offset
                'klaipeda_lon': klaipeda_lon + random.uniform(-0.05, 0.05)   # Small random offset
            }
        
        ref = self._ship_references[mmsi]
        
        # Calculate offset from reference position
        lat_offset = original_lat - ref['ref_lat']
        lon_offset = original_lon - ref['ref_lon']
        
        # Apply offset to Klaipeda position
        transformed_lat = ref['klaipeda_lat'] + lat_offset
        transformed_lon = ref['klaipeda_lon'] + lon_offset
        
        return transformed_lat, transformed_lon
    
    def _generate_synthetic_tracks(self):
        """Generate synthetic tracks for ships with static data but no positions"""
        
        ships_without_positions = []
        for mmsi, static_data in self.ship_static_data.items():
            if mmsi not in self.ship_positions:
                ships_without_positions.append((mmsi, static_data))
        
        print(f"Generating synthetic tracks for {len(ships_without_positions)} ships without position data")
        
        for mmsi, static_data in ships_without_positions:
            # Generate realistic ship track
            track = self._create_realistic_track(mmsi, static_data)
            
            if track:
                self.ship_positions[mmsi] = track
                print(f"Generated {len(track)} positions for ship {mmsi} ({static_data.get('vessel_name', 'Unknown')})")
    
    def _create_realistic_track(self, mmsi: int, static_data: Dict) -> List[Dict]:
        """Create a realistic ship track based on static data"""
        
        # Get ship type and characteristics
        ship_type = static_data.get('ship_type_name', self._get_ship_type_name(static_data.get('ship_type', 0)))
        vessel_name = static_data.get('vessel_name', self._generate_vessel_name(mmsi))
        
        # Define ship characteristics based on type
        ship_chars = self._get_ship_characteristics(ship_type)
        
        # Generate starting position near Klaipeda (Baltic Sea)
        start_lat = 55.7 + random.uniform(-0.1, 0.1)  # Closer to Klaipeda
        start_lon = 21.1 + random.uniform(-0.1, 0.1)  # Closer to Klaipeda
        
        # Generate track duration (1-6 hours)
        duration_hours = random.uniform(1, 6)
        start_time = datetime.now() - timedelta(hours=random.uniform(1, 24))
        
        # Generate waypoints
        waypoints = self._generate_waypoints(start_lat, start_lon, duration_hours, ship_chars)
        
        # Create position reports along the track
        positions = []
        current_time = start_time
        
        for i in range(len(waypoints) - 1):
            start_wp = waypoints[i]
            end_wp = waypoints[i + 1]
            
            # Calculate course and distance
            lat_diff = end_wp[0] - start_wp[0]
            lon_diff = end_wp[1] - start_wp[1]
            
            course = np.degrees(np.arctan2(lon_diff, lat_diff))
            if course < 0:
                course += 360
            
            distance_nm = np.sqrt(lat_diff**2 + lon_diff**2) * 60
            
            # Generate positions along this segment
            num_positions = max(3, int(distance_nm / ship_chars['position_interval']))
            
            for j in range(num_positions):
                progress = j / (num_positions - 1) if num_positions > 1 else 0
                
                lat = start_wp[0] + lat_diff * progress
                lon = start_wp[1] + lon_diff * progress
                
                # Add realistic variation
                lat += random.uniform(-0.0005, 0.0005)
                lon += random.uniform(-0.0005, 0.0005)
                
                # Calculate time
                time_offset = (distance_nm * progress) / ship_chars['avg_speed']
                position_time = start_time + timedelta(hours=time_offset)
                
                # Randomly mark some positions as missing for dead reckoning
                is_missing = random.random() < 0.2  # 20% missing positions
                
                positions.append({
                    'timestamp': position_time,
                    'lat': None if is_missing else lat,
                    'lon': None if is_missing else lon,
                    'sog': ship_chars['avg_speed'] + random.uniform(-2, 2),
                    'cog': course + random.uniform(-5, 5),
                    'nav_status': random.choice([0, 1, 2, 3, 4, 5]),
                    'position_accuracy': random.choice([0, 1]),
                    'true_heading': course + random.uniform(-10, 10),
                    'is_dead_reckoned': False,
                    'is_synthetic': True
                })
        
        return positions
    
    def _get_ship_characteristics(self, ship_type: str) -> Dict:
        """Get realistic characteristics for different ship types"""
        
        characteristics = {
            'Cargo': {'avg_speed': 12, 'position_interval': 1.5},
            'Tanker': {'avg_speed': 10, 'position_interval': 2.0},
            'Passenger': {'avg_speed': 16, 'position_interval': 1.0},
            'Fishing': {'avg_speed': 6, 'position_interval': 2.5},
            'Pleasure craft': {'avg_speed': 8, 'position_interval': 2.0},
            'Tug': {'avg_speed': 8, 'position_interval': 1.5},
            'Pilot vessel': {'avg_speed': 10, 'position_interval': 1.0},
            'Search and rescue': {'avg_speed': 14, 'position_interval': 1.0},
            'Military ops': {'avg_speed': 12, 'position_interval': 1.0},
            'Unknown': {'avg_speed': 10, 'position_interval': 2.0}
        }
        
        return characteristics.get(ship_type, characteristics['Unknown'])
    
    def _generate_waypoints(self, start_lat: float, start_lon: float, 
                           duration_hours: float, ship_chars: Dict) -> List[Tuple[float, float]]:
        """Generate realistic waypoints for ship track near Klaipeda"""
        
        waypoints = [(start_lat, start_lon)]
        
        # Calculate total distance based on speed and duration
        total_distance_nm = ship_chars['avg_speed'] * duration_hours
        
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
        
        # Scale the route to match the desired distance
        route_distance = 0
        for i in range(len(chosen_route) - 1):
            lat_diff = chosen_route[i+1][0] - chosen_route[i][0]
            lon_diff = chosen_route[i+1][1] - chosen_route[i][1]
            route_distance += np.sqrt(lat_diff**2 + lon_diff**2) * 60
        
        # Scale factor to match desired distance
        scale_factor = total_distance_nm / route_distance if route_distance > 0 else 1
        
        # Generate scaled waypoints
        for i in range(1, len(chosen_route)):
            lat_diff = chosen_route[i][0] - chosen_route[0][0]
            lon_diff = chosen_route[i][1] - chosen_route[0][1]
            
            scaled_lat = start_lat + lat_diff * scale_factor
            scaled_lon = start_lon + lon_diff * scale_factor
            
            waypoints.append((scaled_lat, scaled_lon))
        
        return waypoints
    
    def _apply_dead_reckoning(self):
        """Apply dead reckoning to fill missing positions"""
        
        print("Applying dead reckoning to fill missing positions...")
        
        for mmsi, positions in self.ship_positions.items():
            last_lat = None
            last_lon = None
            last_time = None
            
            for i, pos in enumerate(positions):
                if pos['lat'] is None or pos['lon'] is None:
                    # Missing position - try dead reckoning
                    if last_lat is not None and last_lon is not None:
                        time_diff = (pos['timestamp'] - last_time).total_seconds()
                        
                        if time_diff > 0 and time_diff < 3600:  # Within 1 hour
                            new_lat, new_lon = self.dead_reckoning.calculate_position(
                                last_lat, last_lon,
                                pos['sog'], pos['cog'],
                                time_diff
                            )
                            
                            positions[i]['lat'] = new_lat
                            positions[i]['lon'] = new_lon
                            positions[i]['is_dead_reckoned'] = True
                            
                            # Update last known position
                            last_lat = new_lat
                            last_lon = new_lon
                else:
                    # Valid position - update last known position
                    last_lat = pos['lat']
                    last_lon = pos['lon']
                    last_time = pos['timestamp']
    
    def _create_dataframe(self) -> pd.DataFrame:
        """Convert processed data to DataFrame"""
        
        all_data = []
        
        for mmsi, positions in self.ship_positions.items():
            static_data = self.ship_static_data.get(mmsi, {})
            
            for pos in positions:
                all_data.append({
                    'timestamp': pos['timestamp'],
                    'mmsi': mmsi,
                    'ship_type': static_data.get('ship_type', 0),
                    'ship_type_name': self._get_ship_type_name(static_data.get('ship_type', 0)),
                    'vessel_name': self._generate_vessel_name(mmsi),
                    'lat': pos['lat'],
                    'lon': pos['lon'],
                    'sog': pos['sog'],
                    'cog': pos['cog'],
                    'nav_status': pos['nav_status'],
                    'position_accuracy': pos['position_accuracy'],
                    'true_heading': pos['true_heading'],
                    'is_dead_reckoned': pos['is_dead_reckoned'],
                    'is_synthetic': pos['is_synthetic']
                })
        
        if not all_data:
            # Create empty DataFrame with proper structure if no data
            df = pd.DataFrame(columns=[
                'timestamp', 'mmsi', 'ship_type', 'ship_type_name', 'vessel_name',
                'lat', 'lon', 'sog', 'cog', 'nav_status', 'position_accuracy',
                'true_heading', 'is_dead_reckoned', 'is_synthetic'
            ])
            print("No ship data found - created empty dataset")
            return df
        
        df = pd.DataFrame(all_data)
        df = df.sort_values('timestamp')
        
        print(f"Created hybrid dataset with {len(df)} position reports from {df['mmsi'].nunique()} ships")
        print(f"Real positions: {len(df[~df['is_synthetic']])}")
        print(f"Synthetic positions: {len(df[df['is_synthetic']])}")
        print(f"Dead reckoned positions: {df['is_dead_reckoned'].sum()}")
        
        return df
    
    def _generate_vessel_name(self, mmsi: int) -> str:
        """Generate a realistic vessel name based on MMSI"""
        import random
        
        # Debug: Print when this method is called
        print(f"DEBUG: Generating vessel name for MMSI {mmsi}")
        
        # Common vessel name prefixes
        prefixes = [
            "MV", "MS", "SS", "RV", "FV", "SY", "MY", "ATB", "MT", "VLCC"
        ]
        
        # Common vessel name suffixes
        suffixes = [
            "Explorer", "Navigator", "Voyager", "Mariner", "Seafarer", 
            "Adventure", "Discovery", "Endeavour", "Enterprise", "Pioneer",
            "Challenger", "Horizon", "Ocean", "Sea", "Wave", "Current",
            "Trade", "Cargo", "Express", "Star", "Sun", "Moon", "Wind"
        ]
        
        # Generate a realistic name
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)
        number = random.randint(1, 99)
        
        generated_name = f"{prefix} {suffix} {number}"
        print(f"DEBUG: Generated name '{generated_name}' for MMSI {mmsi}")
        return generated_name
    
    def _get_ship_type_name(self, ship_type: int) -> str:
        """Convert ship type code to readable name"""
        ship_types = {
            20: "Wing in ground (WIG)",
            21: "Wing in ground (WIG)",
            22: "Wing in ground (WIG)",
            23: "Wing in ground (WIG)",
            24: "Wing in ground (WIG)",
            25: "Wing in ground (WIG)",
            26: "Wing in ground (WIG)",
            27: "Wing in ground (WIG)",
            28: "Wing in ground (WIG)",
            29: "Wing in ground (WIG)",
            30: "Fishing",
            31: "Towing",
            32: "Towing",
            33: "Dredging or underwater ops",
            34: "Diving ops",
            35: "Military ops",
            36: "Sailing",
            37: "Pleasure craft",
            40: "High speed craft (HSC)",
            41: "High speed craft (HSC)",
            42: "High speed craft (HSC)",
            43: "High speed craft (HSC)",
            44: "High speed craft (HSC)",
            45: "High speed craft (HSC)",
            46: "High speed craft (HSC)",
            47: "High speed craft (HSC)",
            48: "High speed craft (HSC)",
            49: "High speed craft (HSC)",
            50: "Pilot vessel",
            51: "Search and rescue",
            52: "Tug",
            53: "Port tender",
            54: "Anti-pollution equipment",
            55: "Law enforcement",
            56: "Spare - Local vessel",
            57: "Spare - Local vessel",
            58: "Medical transport",
            59: "Noncombatant ship",
            60: "Passenger",
            61: "Passenger",
            62: "Passenger",
            63: "Passenger",
            64: "Passenger",
            69: "Passenger",
            70: "Cargo",
            71: "Cargo",
            72: "Cargo",
            73: "Cargo",
            74: "Cargo",
            75: "Cargo",
            76: "Cargo",
            77: "Cargo",
            78: "Cargo",
            79: "Cargo",
            80: "Tanker",
            81: "Tanker",
            82: "Tanker",
            83: "Tanker",
            84: "Tanker",
            85: "Tanker",
            86: "Tanker",
            87: "Tanker",
            88: "Tanker",
            89: "Tanker",
            90: "Other type"
        }
        
        return ship_types.get(ship_type, "Unknown")


def process_hybrid_ais_data(log_file_path: str, output_file: str = None) -> pd.DataFrame:
    """Process AIS log file and create hybrid dataset"""
    
    processor = HybridAISProcessor()
    df = processor.process_log_file(log_file_path)
    
    if output_file:
        df.to_csv(output_file, index=False)
        print(f"Hybrid dataset saved to: {output_file}")
    
    return df


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python hybrid_ais_processor.py <ais_log_file> [output_file]")
        sys.exit(1)
    
    log_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(log_file):
        print(f"Error: File {log_file} not found")
        sys.exit(1)
    
    df = process_hybrid_ais_data(log_file, output_file)
    
    # Print summary
    print("\n=== HYBRID AIS PROCESSING SUMMARY ===")
    print(f"Total ships: {df['mmsi'].nunique()}")
    print(f"Total positions: {len(df)}")
    print(f"Real positions: {len(df[~df['is_synthetic']])}")
    print(f"Synthetic positions: {len(df[df['is_synthetic']])}")
    print(f"Dead reckoned positions: {df['is_dead_reckoned'].sum()}")
    print(f"DR percentage: {(df['is_dead_reckoned'].sum() / len(df)) * 100:.1f}%")
    
    print("\nShip types:")
    ship_summary = df.groupby('ship_type_name').agg({
        'mmsi': 'nunique',
        'is_synthetic': 'sum',
        'is_dead_reckoned': 'sum',
        'timestamp': 'count'
    }).rename(columns={'mmsi': 'ships', 'timestamp': 'positions'})
    print(ship_summary)
