"""
Interactive Dead Reckoning Demo Map
Creates an interactive map showing ship tracks with dead reckoning predictions
"""

import folium
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import os


class DeadReckoningMap:
    """Interactive map for dead reckoning demo"""
    
    def __init__(self):
        self.ship_colors = {
            'Cargo': '#FF6B6B',      # Red
            'Tanker': '#4ECDC4',     # Teal
            'Passenger': '#45B7D1',  # Blue
            'Fishing': '#96CEB4',    # Green
            'Pleasure craft': '#FFEAA7',  # Yellow
            'Tug': '#DDA0DD',        # Plum
            'Pilot vessel': '#98D8C8',   # Mint
            'Search and rescue': '#F7DC6F',  # Gold
            'Military ops': '#BB8FCE',     # Purple
            'Unknown': '#BDC3C7'     # Gray
        }
        
        self.map = None
        self.ship_data = None
        self.ship_tracks = {}
        self.time_range = None
        
    def load_ship_data(self, csv_file: str):
        """Load processed ship data from CSV"""
        print(f"Loading ship data from: {csv_file}")
        self.ship_data = pd.read_csv(csv_file)
        
        # Convert timestamp to datetime
        self.ship_data['timestamp'] = pd.to_datetime(self.ship_data['timestamp'])
        
        # Sort by timestamp
        self.ship_data = self.ship_data.sort_values('timestamp')
        
        # Create ship tracks
        self._create_ship_tracks()
        
        # Set time range
        self.time_range = {
            'start': self.ship_data['timestamp'].min(),
            'end': self.ship_data['timestamp'].max()
        }
        
        print(f"Loaded {len(self.ship_data)} position reports from {self.ship_data['mmsi'].nunique()} ships")
        print(f"Time range: {self.time_range['start']} to {self.time_range['end']}")
        print(f"Dead reckoned positions: {self.ship_data['is_dead_reckoned'].sum()}")
    
    def _create_ship_tracks(self):
        """Create track data for each ship"""
        self.ship_tracks = {}
        
        for mmsi in self.ship_data['mmsi'].unique():
            ship_data = self.ship_data[self.ship_data['mmsi'] == mmsi].copy()
            ship_data = ship_data.sort_values('timestamp')
            
            # Create track points
            track_points = []
            for _, row in ship_data.iterrows():
                track_points.append({
                    'timestamp': row['timestamp'],
                    'lat': row['lat'],
                    'lon': row['lon'],
                    'sog': row['sog'],
                    'cog': row['cog'],
                    'is_dead_reckoned': row['is_dead_reckoned'],
                    'nav_status': row['nav_status']
                })
            
            # Get ship info
            ship_info = ship_data.iloc[0]
            
            self.ship_tracks[mmsi] = {
                'mmsi': mmsi,
                'vessel_name': ship_info['vessel_name'],
                'ship_type': ship_info['ship_type'],
                'ship_type_name': ship_info['ship_type_name'],
                'track_points': track_points,
                'total_positions': len(track_points),
                'dead_reckoned_positions': sum(1 for p in track_points if p['is_dead_reckoned'])
            }
    
    def create_map(self, center_lat: float = None, center_lon: float = None, zoom: int = 10):
        """Create the interactive map"""
        if self.ship_data is None:
            raise ValueError("No ship data loaded. Call load_ship_data() first.")
        
        # Calculate center if not provided
        if center_lat is None or center_lon is None:
            center_lat = self.ship_data['lat'].mean()
            center_lon = self.ship_data['lon'].mean()
        
        # Create base map with fixed height
        self.map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom,
            tiles='OpenStreetMap'
        )
        
        # Add ship tracks
        self._add_ship_tracks()
        
        # Add legend
        self._add_legend()
        
        # Add interactive controls
        self._add_time_controls()
        self._add_vessel_controls()
        self._add_info_panel()
        
        return self.map
    
    def _add_ship_tracks(self):
        """Add ship tracks to the map"""
        for mmsi, ship_info in self.ship_tracks.items():
            track_points = ship_info['track_points']
            if len(track_points) < 2:
                continue
            
            # Get ship color
            ship_type = ship_info['ship_type_name']
            color = self.ship_colors.get(ship_type, self.ship_colors['Unknown'])
            
            # Create track coordinates (filter out NaN values)
            track_coords = [(p['lat'], p['lon']) for p in track_points 
                          if not (pd.isna(p['lat']) or pd.isna(p['lon']))]
            
            # Add track line
            folium.PolyLine(
                track_coords,
                color=color,
                weight=3,
                opacity=0.7,
                popup=f"{ship_info['vessel_name']} ({ship_info['ship_type_name']})"
            ).add_to(self.map)
            
            # Add markers for start, end, and dead reckoned positions
            self._add_ship_markers(ship_info, track_points, color)
    
    def _add_ship_markers(self, ship_info: Dict, track_points: List[Dict], color: str):
        """Add markers for ship positions"""
        mmsi = ship_info['mmsi']
        
        # Start position marker (find first valid position)
        start_point = None
        for point in track_points:
            if not (pd.isna(point['lat']) or pd.isna(point['lon'])):
                start_point = point
                break
        
        if start_point:
            # Create detailed popup with vessel information
            popup_html = self._create_vessel_popup(ship_info, start_point, "Start Position")
            
            folium.Marker(
                [start_point['lat'], start_point['lon']],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color='green', icon='play', prefix='fa'),
                tooltip=f"Start: {ship_info['vessel_name']} (Click for details)"
            ).add_to(self.map)
        
        # End position marker (find last valid position)
        end_point = None
        for point in reversed(track_points):
            if not (pd.isna(point['lat']) or pd.isna(point['lon'])):
                end_point = point
                break
        
        if end_point:
            # Create detailed popup with vessel information
            popup_html = self._create_vessel_popup(ship_info, end_point, "End Position")
            
            folium.Marker(
                [end_point['lat'], end_point['lon']],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color='red', icon='stop', prefix='fa'),
                tooltip=f"End: {ship_info['vessel_name']} (Click for details)"
            ).add_to(self.map)
        
        # Dead reckoned position markers
        for i, point in enumerate(track_points):
            if point['is_dead_reckoned'] and not (pd.isna(point['lat']) or pd.isna(point['lon'])):
                folium.CircleMarker(
                    [point['lat'], point['lon']],
                    radius=4,
                    color='orange',
                    fill=True,
                    fillColor='orange',
                    popup=f"<b>Dead Reckoned:</b> {ship_info['vessel_name']}<br>"
                          f"<b>Time:</b> {point['timestamp']}<br>"
                          f"<b>SOG:</b> {point['sog']:.1f} knots<br>"
                          f"<b>COG:</b> {point['cog']:.1f}°",
                    tooltip=f"DR: {ship_info['vessel_name']}"
                ).add_to(self.map)
    
    def _add_legend(self):
        """Add legend to the map"""
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 200px; height: 300px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <h4>Ship Types</h4>
        '''
        
        for ship_type, color in self.ship_colors.items():
            legend_html += f'''
            <p><i class="fa fa-circle" style="color:{color}"></i> {ship_type}</p>
            '''
        
        legend_html += '''
        <h4>Markers</h4>
        <p><i class="fa fa-play" style="color:green"></i> Start Position</p>
        <p><i class="fa fa-stop" style="color:red"></i> End Position</p>
        <p><i class="fa fa-circle" style="color:orange"></i> Dead Reckoned</p>
        </div>
        '''
        
        self.map.get_root().html.add_child(folium.Element(legend_html))
    
    def _add_time_controls(self):
        """Add interactive time controls"""
        if self.time_range:
            # Calculate time steps for the slider
            total_seconds = int((self.time_range['end'] - self.time_range['start']).total_seconds())
            time_steps = min(100, max(10, total_seconds // 60))  # 1-minute steps, max 100 steps
            
            time_controls_html = f'''
            <div style="position: fixed; 
                        top: 20px; left: 20px; width: 300px; height: 120px; 
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:12px; padding: 10px; border-radius: 5px;">
            <h4 style="margin-top: 0;">Time Controls</h4>
            <div style="margin-bottom: 10px;">
                <input type="range" id="timeSlider" min="0" max="{time_steps-1}" value="0" 
                       style="width: 100%;" onchange="updateTime(this.value)">
                <div style="text-align: center; font-size: 10px;">
                    <span id="currentTime">{self.time_range['start'].strftime('%H:%M:%S')}</span>
                </div>
            </div>
            <div style="text-align: center;">
                <button onclick="playAnimation()" id="playBtn" style="margin-right: 5px;">▶ Play</button>
                <button onclick="pauseAnimation()" id="pauseBtn" style="margin-right: 5px;">⏸ Pause</button>
                <button onclick="resetAnimation()">⏹ Reset</button>
            </div>
            </div>
            
            <script>
            let animationInterval = null;
            let currentStep = 0;
            const totalSteps = {time_steps};
            const startTime = new Date('{self.time_range['start']}');
            const endTime = new Date('{self.time_range['end']}');
            
            function updateTime(step) {{
                currentStep = parseInt(step);
                const timeDiff = endTime - startTime;
                const currentTime = new Date(startTime.getTime() + (timeDiff * currentStep / totalSteps));
                document.getElementById('currentTime').textContent = currentTime.toLocaleTimeString();
                updateMapDisplay(currentTime);
            }}
            
            function playAnimation() {{
                if (animationInterval) return;
                document.getElementById('playBtn').textContent = '⏸ Playing';
                animationInterval = setInterval(() => {{
                    currentStep = (currentStep + 1) % totalSteps;
                    document.getElementById('timeSlider').value = currentStep;
                    updateTime(currentStep);
                    if (currentStep === 0) {{
                        pauseAnimation();
                    }}
                }}, 200);
            }}
            
            function pauseAnimation() {{
                if (animationInterval) {{
                    clearInterval(animationInterval);
                    animationInterval = null;
                }}
                document.getElementById('playBtn').textContent = '▶ Play';
            }}
            
            function resetAnimation() {{
                pauseAnimation();
                currentStep = 0;
                document.getElementById('timeSlider').value = 0;
                updateTime(0);
            }}
            
            function updateMapDisplay(currentTime) {{
                // This will be implemented to show/hide markers based on time
                console.log('Updating map for time:', currentTime);
            }}
            </script>
            '''
            
            self.map.get_root().html.add_child(folium.Element(time_controls_html))
    
    def _add_vessel_controls(self):
        """Add vessel selection controls"""
        vessel_options = []
        vessel_options.append('<option value="all">All Vessels</option>')
        
        for mmsi, ship_info in self.ship_tracks.items():
            vessel_name = ship_info['vessel_name'] or f"Ship {mmsi}"
            vessel_options.append(f'<option value="{mmsi}">{vessel_name} ({mmsi})</option>')
        
        vessel_controls_html = f'''
        <div style="position: fixed; 
                    top: 160px; left: 20px; width: 300px; height: 80px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px; border-radius: 5px;">
        <h4 style="margin-top: 0;">Vessel Selection</h4>
        <select id="vesselSelect" onchange="selectVessel(this.value)" style="width: 100%; padding: 5px;">
            {''.join(vessel_options)}
        </select>
        <div style="margin-top: 5px; font-size: 10px;">
            <label><input type="checkbox" id="showTracks" checked onchange="toggleTracks()"> Show Tracks</label>
            <label style="margin-left: 10px;"><input type="checkbox" id="showMarkers" checked onchange="toggleMarkers()"> Show Markers</label>
        </div>
        </div>
        
        <script>
        function selectVessel(mmsi) {{
            console.log('Selected vessel:', mmsi);
            // This will be implemented to filter map display
            updateVesselInfo(mmsi);
        }}
        
        function toggleTracks() {{
            const showTracks = document.getElementById('showTracks').checked;
            console.log('Toggle tracks:', showTracks);
            // This will be implemented to show/hide tracks
        }}
        
        function toggleMarkers() {{
            const showMarkers = document.getElementById('showMarkers').checked;
            console.log('Toggle markers:', showMarkers);
            // This will be implemented to show/hide markers
        }}
        
        // updateVesselInfo function will be defined later in the info panel
        </script>
        '''
        
        self.map.get_root().html.add_child(folium.Element(vessel_controls_html))
    
    def _add_info_panel(self):
        """Add vessel information panel"""
        vessel_data_json = self._get_vessel_data_json()
        info_panel_html = '''
        <div style="position: fixed; 
                    top: 20px; right: 20px; width: 350px; height: 500px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 15px; border-radius: 5px; overflow-y: auto;">
        <h4 style="margin-top: 0;">Vessel Information</h4>
        <div id="vesselInfo">
            <p style="color: #666; font-style: italic;">Select a vessel to view details</p>
        </div>
        
        <hr style="margin: 15px 0;">
        
        <h5>Navigation Status Codes:</h5>
        <div style="font-size: 10px; line-height: 1.4;">
            <p><strong>0</strong> = Under way using engine</p>
            <p><strong>1</strong> = At anchor</p>
            <p><strong>2</strong> = Not under command</p>
            <p><strong>3</strong> = Restricted maneuverability</p>
            <p><strong>4</strong> = Constrained by her draught</p>
            <p><strong>5</strong> = Moored</p>
            <p><strong>6</strong> = Aground</p>
            <p><strong>7</strong> = Engaged in fishing</p>
            <p><strong>8</strong> = Under way sailing</p>
            <p><strong>9-14</strong> = Reserved for future use</p>
            <p><strong>15</strong> = Undefined</p>
        </div>
        
        <hr style="margin: 15px 0;">
        
        <h5>Data Fields:</h5>
        <div style="font-size: 10px; line-height: 1.4;">
            <p><strong>SOG:</strong> Speed over Ground (0.0 to 102.3 knots)</p>
            <p><strong>COG:</strong> Course over Ground (0° to 360°)</p>
            <p><strong>True Heading:</strong> Ship's actual heading (0° to 360°, 511 = N/A)</p>
            <p><strong>MMSI:</strong> Maritime Mobile Service Identity (unique ship ID)</p>
            <p><strong>Message Type:</strong> AIS message type (1,2,3 = position reports)</p>
            <p><strong>Position Accuracy:</strong> GPS accuracy (0 = DGPS, 1 = GPS)</p>
        </div>
        </div>
        
        <script>
        // Vessel data from Python backend
        const vesselData = {vessel_data_json};
        
        function updateVesselInfo(mmsi) {
            const vesselInfoDiv = document.getElementById('vesselInfo');
            
            if (mmsi === 'all') {
                vesselInfoDiv.innerHTML = '<p style="color: #666; font-style: italic;">All vessels selected</p>';
                return;
            }
            
            const vessel = vesselData[mmsi];
            if (!vessel) {
                vesselInfoDiv.innerHTML = '<p style="color: #e74c3c;">Vessel data not found</p>';
                return;
            }
            
            // Get latest position data
            const latestPosition = vessel.track_points[vessel.track_points.length - 1];
            
            vesselInfoDiv.innerHTML = `
                <div style="border: 1px solid #ddd; padding: 10px; border-radius: 3px; background-color: #f9f9f9;">
                    <h5 style="margin-top: 0;">${vessel.vessel_name || 'Unknown Vessel'}</h5>
                    <p><strong>MMSI:</strong> ${vessel.mmsi}</p>
                    <p><strong>Ship Type:</strong> ${vessel.ship_type_name}</p>
                    <hr style="margin: 8px 0;">
                    <h6 style="margin: 5px 0; color: #2c3e50;">Latest Position Data</h6>
                    <p><strong>Time:</strong> ${new Date(latestPosition.timestamp).toLocaleString()}</p>
                    <p><strong>Speed (SOG):</strong> ${latestPosition.sog !== null ? latestPosition.sog.toFixed(1) + ' knots' : 'N/A'}</p>
                    <p><strong>Course (COG):</strong> ${latestPosition.cog !== null ? latestPosition.cog.toFixed(1) + '°' : 'N/A'}</p>
                    <p><strong>Navigation Status:</strong> ${getNavStatusText(latestPosition.nav_status)}</p>
                    <hr style="margin: 8px 0;">
                    <h6 style="margin: 5px 0; color: #2c3e50;">Track Statistics</h6>
                    <p><strong>Total Positions:</strong> ${vessel.total_positions}</p>
                    <p><strong>Dead Reckoned:</strong> ${vessel.dead_reckoned_positions}</p>
                    <p><strong>DR Percentage:</strong> ${(vessel.dead_reckoned_positions/vessel.total_positions*100).toFixed(1)}%</p>
                </div>
            `;
        }
        
        function getNavStatusText(status) {
            const statusMap = {
                0: "Under way using engine",
                1: "At anchor", 
                2: "Not under command",
                3: "Restricted maneuverability",
                4: "Constrained by her draught",
                5: "Moored",
                6: "Aground",
                7: "Engaged in fishing",
                8: "Under way sailing",
                15: "Undefined"
            };
            return statusMap[status] || `Status ${status}`;
        }
        </script>
        '''
        
        # Format the HTML with the vessel data
        info_panel_html = info_panel_html.replace('{vessel_data_json}', vessel_data_json)
        
        self.map.get_root().html.add_child(folium.Element(info_panel_html))
    
    def _get_vessel_data_json(self) -> str:
        """Convert vessel data to JSON for JavaScript"""
        import json
        from datetime import datetime
        
        vessel_data = {}
        for mmsi, ship_info in self.ship_tracks.items():
            # Convert track points to JSON-serializable format
            track_points = []
            for point in ship_info['track_points']:
                track_points.append({
                    'timestamp': point['timestamp'].isoformat() if hasattr(point['timestamp'], 'isoformat') else str(point['timestamp']),
                    'lat': float(point['lat']) if not pd.isna(point['lat']) else None,
                    'lon': float(point['lon']) if not pd.isna(point['lon']) else None,
                    'sog': float(point['sog']) if not pd.isna(point['sog']) else None,
                    'cog': float(point['cog']) if not pd.isna(point['cog']) else None,
                    'nav_status': int(point['nav_status']) if not pd.isna(point['nav_status']) else None,
                    'is_dead_reckoned': bool(point['is_dead_reckoned'])
                })
            
            vessel_data[str(mmsi)] = {
                'mmsi': str(mmsi),
                'vessel_name': ship_info['vessel_name'] or f"Ship {mmsi}",
                'ship_type_name': ship_info['ship_type_name'],
                'total_positions': ship_info['total_positions'],
                'dead_reckoned_positions': ship_info['dead_reckoned_positions'],
                'track_points': track_points
            }
        
        return json.dumps(vessel_data)
    
    def _create_vessel_popup(self, ship_info: Dict, point: Dict, position_type: str) -> str:
        """Create detailed vessel popup HTML"""
        mmsi = ship_info['mmsi']
        vessel_name = ship_info['vessel_name'] or f"Ship {mmsi}"
        
        # Format navigation status
        nav_status = point.get('nav_status', 'N/A')
        nav_status_text = self._get_nav_status_text(nav_status)
        
        # Format data values
        sog = point.get('sog', 'N/A')
        sog_text = f"{sog:.1f} knots" if isinstance(sog, (int, float)) and not pd.isna(sog) else "N/A"
        
        cog = point.get('cog', 'N/A')
        cog_text = f"{cog:.1f}°" if isinstance(cog, (int, float)) and not pd.isna(cog) else "N/A"
        
        # Format timestamp
        timestamp = point.get('timestamp', 'N/A')
        if hasattr(timestamp, 'strftime'):
            timestamp_text = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp_text = str(timestamp)
        
        popup_html = f'''
        <div style="font-family: Arial, sans-serif; font-size: 12px; max-width: 280px;">
            <h4 style="margin: 0 0 10px 0; color: #2c3e50;">{vessel_name}</h4>
            <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <p style="margin: 2px 0;"><strong>Position:</strong> {position_type}</p>
                <p style="margin: 2px 0;"><strong>MMSI:</strong> {mmsi}</p>
                <p style="margin: 2px 0;"><strong>Ship Type:</strong> {ship_info['ship_type_name']}</p>
                <p style="margin: 2px 0;"><strong>Time:</strong> {timestamp_text}</p>
            </div>
            
            <div style="background-color: #e8f4fd; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <h5 style="margin: 0 0 8px 0; color: #1e3a8a;">Navigation Data</h5>
                <p style="margin: 2px 0;"><strong>Speed (SOG):</strong> {sog_text}</p>
                <p style="margin: 2px 0;"><strong>Course (COG):</strong> {cog_text}</p>
                <p style="margin: 2px 0;"><strong>Status:</strong> {nav_status_text}</p>
            </div>
            
            <div style="background-color: #f0f9ff; padding: 10px; border-radius: 5px;">
                <h5 style="margin: 0 0 8px 0; color: #1e3a8a;">Track Statistics</h5>
                <p style="margin: 2px 0;"><strong>Total Positions:</strong> {ship_info['total_positions']}</p>
                <p style="margin: 2px 0;"><strong>Dead Reckoned:</strong> {ship_info['dead_reckoned_positions']}</p>
                <p style="margin: 2px 0;"><strong>DR Percentage:</strong> {(ship_info['dead_reckoned_positions']/ship_info['total_positions']*100):.1f}%</p>
            </div>
            
            <div style="text-align: center; margin-top: 10px;">
                <button onclick="selectVesselFromPopup('{mmsi}')" 
                        style="background-color: #3498db; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">
                    View Details
                </button>
            </div>
        </div>
        
        <script>
        function selectVesselFromPopup(mmsi) {{
            // Update vessel selection dropdown
            document.getElementById('vesselSelect').value = mmsi;
            // Update vessel info panel
            updateVesselInfo(mmsi);
            // Note: Popup will close automatically when user clicks elsewhere
        }}
        </script>
        '''
        
        return popup_html
    
    def _get_nav_status_text(self, nav_status) -> str:
        """Convert navigation status code to text"""
        status_map = {
            0: "Under way using engine",
            1: "At anchor", 
            2: "Not under command",
            3: "Restricted maneuverability",
            4: "Constrained by her draught",
            5: "Moored",
            6: "Aground",
            7: "Engaged in fishing",
            8: "Under way sailing",
            15: "Undefined"
        }
        
        if isinstance(nav_status, (int, float)) and not pd.isna(nav_status):
            return status_map.get(int(nav_status), f"Status {int(nav_status)}")
        return "N/A"
    
    def save_map(self, filename: str = "dead_reckoning_map.html"):
        """Save the map to an HTML file with height fix"""
        if self.map is None:
            raise ValueError("No map created. Call create_map() first.")
        
        # Save the map first
        self.map.save(filename)
        
        # Read the saved file and inject CSS fix
        try:
            with open(filename, 'r') as f:
                html_content = f.read()
            
            # Find the map div ID and inject height CSS
            import re
            map_id_match = re.search(r'class="folium-map" id="([^"]+)"', html_content)
            if map_id_match:
                map_id = map_id_match.group(1)
                print(f"Found map ID: {map_id}")
                
                # Create CSS override
                height_css = f"""
        <style>
            #{map_id} {{
                height: 600px !important;
                min-height: 600px !important;
            }}
            .folium-map {{
                height: 600px !important;
                min-height: 600px !important;
            }}
        </style>"""
                
                # Insert CSS before </head>
                if '</head>' in html_content:
                    html_content = html_content.replace('</head>', height_css + '\n</head>')
                    
                    # Write back the modified content
                    with open(filename, 'w') as f:
                        f.write(html_content)
                    print("CSS height fix applied successfully")
                else:
                    print("Warning: Could not find </head> tag")
            else:
                print("Warning: Could not find map ID in HTML content")
                # Debug: print first 1000 chars to see what's in the file
                print(f"HTML content preview: {html_content[:1000]}...")
        except Exception as e:
            print(f"Error applying CSS height fix: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"Map saved to: {filename}")
        return filename
    
    def get_ship_summary(self) -> pd.DataFrame:
        """Get summary statistics for all ships"""
        if self.ship_tracks is None:
            raise ValueError("No ship data loaded.")
        
        summary_data = []
        for mmsi, ship_info in self.ship_tracks.items():
            summary_data.append({
                'MMSI': mmsi,
                'Vessel Name': ship_info['vessel_name'],
                'Ship Type': ship_info['ship_type_name'],
                'Total Positions': ship_info['total_positions'],
                'Dead Reckoned Positions': ship_info['dead_reckoned_positions'],
                'DR Percentage': (ship_info['dead_reckoned_positions'] / ship_info['total_positions']) * 100
            })
        
        return pd.DataFrame(summary_data).sort_values('DR Percentage', ascending=False)


def create_dead_reckoning_demo(ais_log_file: str, output_dir: str = "."):
    """Create a complete dead reckoning demo"""
    print("Creating Dead Reckoning Demo...")
    
    # Step 1: Process AIS data
    from ais_parser import process_ais_log_file
    
    print("Step 1: Processing AIS data...")
    df = process_ais_log_file(ais_log_file)
    
    # Save processed data
    csv_file = os.path.join(output_dir, "processed_ship_data.csv")
    df.to_csv(csv_file, index=False)
    print(f"Processed data saved to: {csv_file}")
    
    # Step 2: Create interactive map
    print("Step 2: Creating interactive map...")
    map_demo = DeadReckoningMap()
    map_demo.load_ship_data(csv_file)
    map_demo.create_map()
    
    # Save map
    map_file = os.path.join(output_dir, "dead_reckoning_map.html")
    map_demo.save_map(map_file)
    
    # Step 3: Generate summary
    print("Step 3: Generating summary...")
    summary = map_demo.get_ship_summary()
    summary_file = os.path.join(output_dir, "ship_summary.csv")
    summary.to_csv(summary_file, index=False)
    print(f"Summary saved to: {summary_file}")
    
    print("\n=== DEAD RECKONING DEMO SUMMARY ===")
    print(f"Total ships: {len(summary)}")
    print(f"Total position reports: {len(df)}")
    print(f"Dead reckoned positions: {df['is_dead_reckoned'].sum()}")
    print(f"DR percentage: {(df['is_dead_reckoned'].sum() / len(df)) * 100:.1f}%")
    
    print("\nTop 5 ships by dead reckoning usage:")
    print(summary.head().to_string(index=False))
    
    print(f"\nFiles created:")
    print(f"- Interactive map: {map_file}")
    print(f"- Processed data: {csv_file}")
    print(f"- Summary: {summary_file}")
    
    return map_file, csv_file, summary_file


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dead_reckoning_map.py <ais_log_file> [output_dir]")
        sys.exit(1)
    
    ais_log_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    
    if not os.path.exists(ais_log_file):
        print(f"Error: File {ais_log_file} not found")
        sys.exit(1)
    
    create_dead_reckoning_demo(ais_log_file, output_dir)
