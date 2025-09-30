"""
AIS (Automatic Identification System) NMEA Message Parser
Parses AIS messages from NMEA format and extracts ship position data
"""

import re
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd


class AISParser:
    """Parser for AIS NMEA messages"""
    
    def __init__(self):
        self.ship_types = {
            20: "Wing in ground (WIG)",
            21: "Wing in ground (WIG)",
            22: "Wing in ground (WIG)",
            23: "Wing in ground (WIG)",
            30: "Fishing",
            31: "Towing",
            32: "Towing (large)",
            33: "Dredging or underwater ops",
            34: "Diving ops",
            35: "Military ops",
            36: "Sailing",
            37: "Pleasure craft",
            50: "Pilot vessel",
            51: "Search and rescue",
            52: "Tug",
            53: "Port tender",
            54: "Anti-pollution equipment",
            55: "Law enforcement",
            56: "Spare - local vessel",
            57: "Spare - local vessel",
            58: "Medical transport",
            59: "Non-combatant ship",
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
            90: "Other"
        }
    
    def parse_nmea_line(self, line: str) -> Optional[Dict]:
        """Parse a single NMEA AIS line"""
        try:
            # Handle the specific format: \s:KlaipedaVTS,c:1758574798*59\!AIVDM,1,1,,B,24SR`F0000QPgE0OoVBUUrUj0@R9,0*75
            # Extract timestamp from line
            timestamp_match = re.search(r'c:(\d+)', line)
            if not timestamp_match:
                return None
            
            timestamp = int(timestamp_match.group(1))
            dt = datetime.fromtimestamp(timestamp)
            
            # Extract AIS message - look for the data part after the channel
            ais_match = re.search(r'!AIVDM,\d+,\d+,,.,([^,]+)', line)
            if not ais_match:
                return None
            
            ais_data = ais_match.group(1)
            return self.parse_ais_message(ais_data, dt)
            
        except Exception as e:
            print(f"Error parsing line: {e}")
            return None
    
    def parse_ais_message(self, ais_data: str, timestamp: datetime) -> Optional[Dict]:
        """Parse AIS message data"""
        try:
            # Convert 6-bit ASCII to binary
            binary = self._ais_to_binary(ais_data)
            if not binary:
                return None
            
            # Extract message type (first 6 bits)
            message_type = int(binary[:6], 2)
            
            if message_type == 1 or message_type == 2 or message_type == 3:
                return self._parse_position_report(binary, timestamp, message_type)
            elif message_type == 5:
                return self._parse_static_voyage_data(binary, timestamp)
            else:
                return None
                
        except Exception as e:
            print(f"Error parsing AIS message: {e}")
            return None
    
    def _ais_to_binary(self, ais_data: str) -> Optional[str]:
        """Convert AIS 6-bit ASCII to binary string"""
        try:
            binary = ""
            for char in ais_data:
                if char == '@':
                    val = 0
                elif char >= 'A' and char <= 'W':
                    val = ord(char) - ord('A') + 1
                elif char >= 'a' and char <= 'w':
                    val = ord(char) - ord('a') + 33
                elif char >= '0' and char <= '9':
                    val = ord(char) - ord('0') + 48
                else:
                    continue
                
                binary += format(val, '06b')
            
            return binary
        except:
            return None
    
    def _parse_position_report(self, binary: str, timestamp: datetime, msg_type: int) -> Optional[Dict]:
        """Parse position report messages (types 1, 2, 3)"""
        try:
            if len(binary) < 168:  # Minimum length for position report
                return None
            
            # Extract fields
            mmsi = int(binary[8:38], 2)
            nav_status = int(binary[38:42], 2)
            rot = int(binary[42:50], 2)
            sog = int(binary[50:60], 2) / 10.0  # Speed over ground (knots)
            position_accuracy = int(binary[60:61], 2)
            lon_raw = int(binary[61:89], 2)
            lat_raw = int(binary[89:116], 2)
            cog = int(binary[116:128], 2) / 10.0  # Course over ground (degrees)
            true_heading = int(binary[128:137], 2)
            timestamp_sec = int(binary[137:143], 2)
            
            # Convert coordinates
            if lat_raw == 0x3412140:  # Invalid latitude
                lat = None
            else:
                lat = lat_raw / 600000.0
                if lat > 90:
                    lat = lat - 180
            
            if lon_raw == 0x6791AC0:  # Invalid longitude
                lon = None
            else:
                lon = lon_raw / 600000.0
                if lon > 180:
                    lon = lon - 360
            
            # Validate coordinates
            if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:
                return None
            
            return {
                'timestamp': timestamp,
                'mmsi': mmsi,
                'message_type': msg_type,
                'nav_status': nav_status,
                'rot': rot,
                'sog': sog,
                'position_accuracy': position_accuracy,
                'lat': lat,
                'lon': lon,
                'cog': cog,
                'true_heading': true_heading,
                'timestamp_sec': timestamp_sec
            }
            
        except Exception as e:
            print(f"Error parsing position report: {e}")
            return None
    
    def _parse_static_voyage_data(self, binary: str, timestamp: datetime) -> Optional[Dict]:
        """Parse static and voyage data message (type 5)"""
        try:
            if len(binary) < 424:  # Minimum length for static data
                return None
            
            mmsi = int(binary[8:38], 2)
            ais_version = int(binary[38:40], 2)
            imo = int(binary[40:70], 2)
            call_sign = self._decode_text(binary[70:112])
            vessel_name = self._decode_text(binary[112:232])
            ship_type = int(binary[232:240], 2)
            dim_to_bow = int(binary[240:249], 2)
            dim_to_stern = int(binary[249:258], 2)
            dim_to_port = int(binary[258:264], 2)
            dim_to_starboard = int(binary[264:270], 2)
            eta_month = int(binary[270:274], 2)
            eta_day = int(binary[274:279], 2)
            eta_hour = int(binary[279:284], 2)
            eta_minute = int(binary[284:290], 2)
            draught = int(binary[290:298], 2) / 10.0
            destination = self._decode_text(binary[298:422])
            dte = int(binary[422:423], 2)
            spare = int(binary[423:424], 2)
            
            return {
                'timestamp': timestamp,
                'mmsi': mmsi,
                'message_type': 5,
                'ais_version': ais_version,
                'imo': imo,
                'call_sign': call_sign,
                'vessel_name': vessel_name,
                'ship_type': ship_type,
                'ship_type_name': self.ship_types.get(ship_type, f"Unknown ({ship_type})"),
                'dim_to_bow': dim_to_bow,
                'dim_to_stern': dim_to_stern,
                'dim_to_port': dim_to_port,
                'dim_to_starboard': dim_to_starboard,
                'eta_month': eta_month,
                'eta_day': eta_day,
                'eta_hour': eta_hour,
                'eta_minute': eta_minute,
                'draught': draught,
                'destination': destination,
                'dte': dte,
                'spare': spare
            }
            
        except Exception as e:
            print(f"Error parsing static data: {e}")
            return None
    
    def _decode_text(self, binary: str) -> str:
        """Decode AIS text field"""
        text = ""
        for i in range(0, len(binary), 6):
            if i + 6 > len(binary):
                break
            char_bits = binary[i:i+6]
            char_val = int(char_bits, 2)
            
            if char_val == 0:
                break
            elif char_val <= 26:
                text += chr(ord('A') + char_val - 1)
            elif char_val <= 36:
                text += chr(ord('0') + char_val - 27)
            elif char_val == 32:
                text += ' '
            elif char_val == 37:
                text += '@'
            elif char_val == 38:
                text += '['
            elif char_val == 39:
                text += '\\'
            elif char_val == 40:
                text += ']'
            elif char_val == 41:
                text += '^'
            elif char_val == 42:
                text += '_'
        
        return text.strip()


class DeadReckoningCalculator:
    """Calculate ship positions using dead reckoning when actual positions are missing"""
    
    def __init__(self):
        self.EARTH_RADIUS_KM = 6371.0
    
    def calculate_position(self, lat1: float, lon1: float, sog: float, cog: float, 
                          time_diff_seconds: float) -> Tuple[float, float]:
        """
        Calculate new position using dead reckoning
        
        Args:
            lat1, lon1: Starting position (degrees)
            sog: Speed over ground (knots)
            cog: Course over ground (degrees)
            time_diff_seconds: Time difference in seconds
            
        Returns:
            Tuple of (new_lat, new_lon) in degrees
        """
        # Convert speed from knots to km/h, then to km/s
        speed_km_s = (sog * 1.852) / 3600.0
        
        # Calculate distance traveled
        distance_km = speed_km_s * time_diff_seconds
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        cog_rad = math.radians(cog)
        
        # Calculate new position using flat-earth approximation for short distances
        # For longer distances, we'd use the haversine formula
        if distance_km < 100:  # Use flat-earth approximation for distances < 100km
            # Convert distance to degrees (approximate)
            lat_diff = distance_km * math.cos(cog_rad) / 111.0  # ~111 km per degree latitude
            lon_diff = distance_km * math.sin(cog_rad) / (111.0 * math.cos(lat1_rad))
            
            new_lat = lat1 + lat_diff
            new_lon = lon1 + lon_diff
        else:
            # Use haversine formula for longer distances
            new_lat, new_lon = self._haversine_calculate(lat1, lon1, distance_km, cog)
        
        return new_lat, new_lon
    
    def _haversine_calculate(self, lat1: float, lon1: float, distance_km: float, 
                           bearing_deg: float) -> Tuple[float, float]:
        """Calculate position using haversine formula"""
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        bearing_rad = math.radians(bearing_deg)
        
        angular_distance = distance_km / self.EARTH_RADIUS_KM
        
        lat2_rad = math.asin(
            math.sin(lat1_rad) * math.cos(angular_distance) +
            math.cos(lat1_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
        )
        
        lon2_rad = lon1_rad + math.atan2(
            math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat1_rad),
            math.cos(angular_distance) - math.sin(lat1_rad) * math.sin(lat2_rad)
        )
        
        return math.degrees(lat2_rad), math.degrees(lon2_rad)


def process_ais_log_file(file_path: str) -> pd.DataFrame:
    """Process an AIS log file and return a DataFrame with ship data"""
    parser = AISParser()
    dead_reckoning = DeadReckoningCalculator()
    
    ship_data = []
    ship_static_data = {}  # Store static data (ship names, types) by MMSI
    ship_last_positions = {}  # Store last known positions for dead reckoning
    
    print(f"Processing AIS log file: {file_path}")
    
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f):
            if line_num % 10000 == 0:
                print(f"Processed {line_num} lines...")
            
            parsed = parser.parse_nmea_line(line.strip())
            if not parsed:
                if line_num < 10:  # Debug first 10 lines
                    print(f"Failed to parse line {line_num}: {line.strip()[:100]}")
                continue
            
            mmsi = parsed['mmsi']
            
            # Handle static data (message type 5)
            if parsed['message_type'] == 5:
                ship_static_data[mmsi] = parsed
                continue
            
            # Handle position reports (message types 1, 2, 3)
            if parsed['message_type'] in [1, 2, 3]:
                # Get static data if available
                static_data = ship_static_data.get(mmsi, {})
                
                # Check if we have valid position data
                if parsed['lat'] is not None and parsed['lon'] is not None:
                    # Valid position - update last known position
                    ship_last_positions[mmsi] = {
                        'lat': parsed['lat'],
                        'lon': parsed['lon'],
                        'sog': parsed['sog'],
                        'cog': parsed['cog'],
                        'timestamp': parsed['timestamp']
                    }
                    
                    ship_data.append({
                        'timestamp': parsed['timestamp'],
                        'mmsi': mmsi,
                        'ship_type': static_data.get('ship_type', 0),
                        'ship_type_name': static_data.get('ship_type_name'),
                        'vessel_name': static_data.get('vessel_name'),
                        'lat': parsed['lat'],
                        'lon': parsed['lon'],
                        'sog': parsed['sog'],
                        'cog': parsed['cog'],
                        'nav_status': parsed['nav_status'],
                        'position_accuracy': parsed['position_accuracy'],
                        'true_heading': parsed['true_heading'],
                        'is_dead_reckoned': False
                    })
                else:
                    # Missing position - try dead reckoning
                    last_pos = ship_last_positions.get(mmsi)
                    if last_pos:
                        # Calculate time difference
                        time_diff = (parsed['timestamp'] - last_pos['timestamp']).total_seconds()
                        
                        if time_diff > 0 and time_diff < 3600:  # Within 1 hour
                            # Use dead reckoning
                            new_lat, new_lon = dead_reckoning.calculate_position(
                                last_pos['lat'], last_pos['lon'],
                                last_pos['sog'], last_pos['cog'],
                                time_diff
                            )
                            
                            # Update last known position
                            ship_last_positions[mmsi] = {
                                'lat': new_lat,
                                'lon': new_lon,
                                'sog': parsed['sog'] if parsed['sog'] > 0 else last_pos['sog'],
                                'cog': parsed['cog'] if parsed['cog'] >= 0 else last_pos['cog'],
                                'timestamp': parsed['timestamp']
                            }
                            
                            ship_data.append({
                                'timestamp': parsed['timestamp'],
                                'mmsi': mmsi,
                                'ship_type': static_data.get('ship_type', 0),
                                'ship_type_name': static_data.get('ship_type_name'),
                                'vessel_name': static_data.get('vessel_name'),
                                'lat': new_lat,
                                'lon': new_lon,
                                'sog': parsed['sog'] if parsed['sog'] > 0 else last_pos['sog'],
                                'cog': parsed['cog'] if parsed['cog'] >= 0 else last_pos['cog'],
                                'nav_status': parsed['nav_status'],
                                'position_accuracy': parsed['position_accuracy'],
                                'true_heading': parsed['true_heading'],
                                'is_dead_reckoned': True
                            })
    
    print(f"Processed {len(ship_data)} position reports")
    return pd.DataFrame(ship_data)


if __name__ == "__main__":
    # Test the parser
    import sys
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        df = process_ais_log_file(file_path)
        print(f"\nProcessed data shape: {df.shape}")
        print(f"Unique ships: {df['mmsi'].nunique()}")
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"Dead reckoned positions: {df['is_dead_reckoned'].sum()}")
        
        # Save to CSV
        output_file = file_path.replace('.log', '_processed.csv')
        df.to_csv(output_file, index=False)
        print(f"Saved processed data to: {output_file}")
    else:
        print("Usage: python ais_parser.py <ais_log_file>")
