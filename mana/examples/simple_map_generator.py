#!/usr/bin/env python3
"""
Simple Map Generator - Creates a working HTML map without Folium dependencies
"""

import pandas as pd
import json
import os
from datetime import datetime
import random

def create_simple_map_html(ship_data, output_file="simple_map.html"):
    """Create a simple HTML map using Leaflet directly"""
    
    # Convert ship data to JSON for JavaScript
    ships_json = []
    for _, row in ship_data.iterrows():
        # Skip rows with invalid coordinates
        if pd.isna(row['lat']) or pd.isna(row['lon']):
            continue
            
        ships_json.append({
            'mmsi': str(row['mmsi']),
            'vessel_name': row.get('vessel_name', f"Ship {row['mmsi']}"),
            'ship_type': row.get('ship_type_name', 'Unknown'),
            'lat': float(row['lat']),
            'lon': float(row['lon']),
            'sog': float(row.get('sog', 0)),
            'cog': float(row.get('cog', 0)),
            'true_heading': float(row.get('true_heading', 511)),  # 511 = N/A
            'timestamp': str(row['timestamp']),
            'message_type': int(row.get('message_type', 2)),  # Default to Type 2
            'nav_status': int(row.get('nav_status', 0)),
            'is_dead_reckoned': bool(row.get('is_dead_reckoned', False))
        })
    
    # Calculate map center
    center_lat = ship_data['lat'].mean()
    center_lon = ship_data['lon'].mean()
    
    # Create ship tracks by MMSI
    ship_tracks = {}
    for ship in ships_json:
        mmsi = ship['mmsi']
        if mmsi not in ship_tracks:
            ship_tracks[mmsi] = []
        ship_tracks[mmsi].append([ship['lat'], ship['lon']])
    
    # Generate colors for different ship types
    ship_type_colors = {
        'Cargo': '#FF6B6B',
        'Tanker': '#4ECDC4', 
        'Passenger': '#45B7D1',
        'Fishing': '#96CEB4',
        'Pleasure craft': '#FFEAA7',
        'Unknown': '#DDA0DD'
    }
    
    # Get unique timestamps for time controls
    timestamps = sorted(ship_data['timestamp'].unique())
    time_range = {
        'start': timestamps[0] if len(timestamps) > 0 else '',
        'end': timestamps[-1] if len(timestamps) > 0 else '',
        'count': len(timestamps)
    }

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Dead Reckoning Map</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background: #f5f5f5;
        }}
        #map {{
            height: 100vh;
            width: 100%;
        }}
        .controls {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            z-index: 1000;
            min-width: 280px;
        }}
        .info {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            z-index: 1000;
            max-width: 350px;
            max-height: 80vh;
            overflow-y: auto;
        }}
        .time-controls {{
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }}
        .vessel-controls {{
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }}
        button {{
            margin: 3px;
            padding: 8px 12px;
            border: none;
            border-radius: 4px;
            background: #007cba;
            color: white;
            cursor: pointer;
            font-size: 12px;
        }}
        button:hover {{
            background: #005a87;
        }}
        button:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        button.active {{
            background: #28a745;
        }}
        select {{
            margin: 3px;
            padding: 6px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 100%;
        }}
        input[type="range"] {{
            width: 100%;
            margin: 5px 0;
        }}
        .ship-info {{
            font-size: 12px;
            margin: 8px 0;
        }}
        .ship-info h5 {{
            margin: 0 0 8px 0;
            color: #2c3e50;
            font-size: 14px;
        }}
        .ship-info p {{
            margin: 3px 0;
            color: #555;
        }}
        .ship-info strong {{
            color: #2c3e50;
        }}
        .nav-status {{
            background: #e8f4fd;
            padding: 8px;
            border-radius: 4px;
            margin: 8px 0;
        }}
        .time-display {{
            font-weight: bold;
            color: #2c3e50;
            text-align: center;
            margin: 8px 0;
        }}
        .legend {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 3px 0;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            margin-right: 8px;
            border-radius: 2px;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="controls">
        <h4 style="margin-top: 0;">Map Controls</h4>
        
        <div class="time-controls">
            <h5>Time Controls</h5>
            <div class="time-display" id="currentTime">{time_range['start']}</div>
            <input type="range" id="timeSlider" min="0" max="{time_range['count']-1}" value="0" onchange="updateTime(this.value)">
            <div style="text-align: center;">
                <button onclick="playAnimation()" id="playBtn">▶ Play</button>
                <button onclick="pauseAnimation()" id="pauseBtn">⏸ Pause</button>
                <button onclick="resetAnimation()">⏹ Reset</button>
            </div>
        </div>
        
        <div class="vessel-controls">
            <h5>Vessel Selection</h5>
            <select id="shipSelect" onchange="selectShip(this.value)">
                <option value="">All Vessels</option>
            </select>
            <div style="margin-top: 8px;">
                <button onclick="showAllShips()">Show All</button>
                <button onclick="hideAllShips()">Hide All</button>
                <button onclick="toggleDeadReckoned()" id="drBtn">Show DR Only</button>
            </div>
        </div>
    </div>
    
    <div class="info">
        <h4 style="margin-top: 0;">Vessel Information</h4>
        <div id="shipInfo">Select a vessel to view details</div>
        
        <div class="nav-status">
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
        </div>
    </div>

    <script>
        // Ship data
        const ships = {json.dumps(ships_json)};
        const shipTracks = {json.dumps(ship_tracks)};
        const shipTypeColors = {json.dumps(ship_type_colors)};
        const timestamps = {json.dumps(timestamps)};
        
        // Initialize map
        const map = L.map('map').setView([{center_lat}, {center_lon}], 10);
        
        // Add tile layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);
        
        // Store ship markers and tracks
        const shipMarkers = {{}};
        const shipPolylines = {{}};
        let currentTimeIndex = 0;
        let animationInterval = null;
        let showDeadReckonedOnly = false;
        
        // Group ships by MMSI for better organization
        const shipsByMmsi = {{}};
        const uniqueVessels = new Set();
        
        ships.forEach(ship => {{
            if (!shipsByMmsi[ship.mmsi]) {{
                shipsByMmsi[ship.mmsi] = [];
            }}
            shipsByMmsi[ship.mmsi].push(ship);
            uniqueVessels.add(ship.mmsi);
        }});
        
        // Create ship markers and tracks
        Object.keys(shipsByMmsi).forEach(mmsi => {{
            const shipGroup = shipsByMmsi[mmsi];
            const firstShip = shipGroup[0];
            const color = shipTypeColors[firstShip.ship_type] || '#DDA0DD';
            
            // Create markers for each position
            shipGroup.forEach((ship, index) => {{
                const marker = L.circleMarker([ship.lat, ship.lon], {{
                    radius: 6,
                    fillColor: color,
                    color: '#000',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8,
                    timestamp: ship.timestamp,
                    mmsi: ship.mmsi,
                    isDeadReckoned: ship.is_dead_reckoned
                }});
                
                // Add popup
                const popupContent = createShipPopup(ship);
                marker.bindPopup(popupContent);
                
                // Add click handler
                marker.on('click', () => {{
                    selectShip(mmsi);
                }});
                
                if (!shipMarkers[mmsi]) {{
                    shipMarkers[mmsi] = [];
                }}
                shipMarkers[mmsi].push(marker);
                marker.addTo(map);
            }});
            
            // Create track from ship positions
            if (shipGroup.length > 1) {{
                const trackCoords = shipGroup.map(ship => [ship.lat, ship.lon]);
                const polyline = L.polyline(trackCoords, {{
                    color: color,
                    weight: 3,
                    opacity: 0.7
                }});
                shipPolylines[mmsi] = polyline;
                polyline.addTo(map);
            }}
        }});
        
        // Populate ship select dropdown
        const shipSelect = document.getElementById('shipSelect');
        Array.from(uniqueVessels).forEach(mmsi => {{
            const shipGroup = shipsByMmsi[mmsi];
            const firstShip = shipGroup[0];
            const option = document.createElement('option');
            option.value = mmsi;
            option.textContent = `${{firstShip.vessel_name}} (${{mmsi}}) - ${{shipGroup.length}} positions`;
            shipSelect.appendChild(option);
        }});
        
        // Time control functions
        function updateTime(timeIndex) {{
            currentTimeIndex = parseInt(timeIndex);
            const currentTimestamp = timestamps[currentTimeIndex];
            document.getElementById('currentTime').textContent = currentTimestamp;
            
            // Show/hide markers based on current time
            Object.keys(shipMarkers).forEach(mmsi => {{
                shipMarkers[mmsi].forEach(marker => {{
                    const markerTime = marker.options.timestamp;
                    const timeIndex = timestamps.indexOf(markerTime);
                    
                    if (timeIndex <= currentTimeIndex) {{
                        if (!showDeadReckonedOnly || marker.options.isDeadReckoned) {{
                            marker.addTo(map);
                        }}
                    }} else {{
                        map.removeLayer(marker);
                    }}
                }});
                
                // Update track visibility - show track if any markers are visible
                const polyline = shipPolylines[mmsi];
                if (polyline) {{
                    const hasVisibleMarkers = shipMarkers[mmsi].some(marker => {{
                        const markerTime = marker.options.timestamp;
                        const timeIndex = timestamps.indexOf(markerTime);
                        return timeIndex <= currentTimeIndex && 
                               (!showDeadReckonedOnly || marker.options.isDeadReckoned);
                    }});
                    
                    if (hasVisibleMarkers) {{
                        polyline.addTo(map);
                    }} else {{
                        map.removeLayer(polyline);
                    }}
                }}
            }});
        }}
        
        function playAnimation() {{
            if (animationInterval) return;
            
            document.getElementById('playBtn').textContent = '⏸ Playing';
            animationInterval = setInterval(() => {{
                currentTimeIndex = (currentTimeIndex + 1) % timestamps.length;
                document.getElementById('timeSlider').value = currentTimeIndex;
                updateTime(currentTimeIndex);
                
                if (currentTimeIndex === 0) {{
                    pauseAnimation();
                }}
            }}, 500);
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
            currentTimeIndex = 0;
            document.getElementById('timeSlider').value = 0;
            updateTime(0);
        }}
        
        // Ship selection functions
        function selectShip(mmsi) {{
            if (!mmsi) {{
                document.getElementById('shipInfo').innerHTML = 'Select a vessel to view details';
                return;
            }}
            
            const shipGroup = shipsByMmsi[mmsi];
            if (shipGroup && shipGroup.length > 0) {{
                // Get the latest position for this ship
                const latestShip = shipGroup[shipGroup.length - 1];
                document.getElementById('shipInfo').innerHTML = createShipInfoHTML(latestShip, shipGroup.length);
                
                // Center map on ship
                map.setView([latestShip.lat, latestShip.lon], 12);
            }}
        }}
        
        function showAllShips() {{
            Object.values(shipMarkers).forEach(markerGroup => {{
                markerGroup.forEach(marker => {{
                    if (!showDeadReckonedOnly || marker.options.isDeadReckoned) {{
                        marker.addTo(map);
                    }}
                }});
            }});
            Object.values(shipPolylines).forEach(polyline => polyline.addTo(map));
        }}
        
        function hideAllShips() {{
            Object.values(shipMarkers).forEach(markerGroup => {{
                markerGroup.forEach(marker => map.removeLayer(marker));
            }});
            Object.values(shipPolylines).forEach(polyline => map.removeLayer(polyline));
        }}
        
        function toggleDeadReckoned() {{
            showDeadReckonedOnly = !showDeadReckonedOnly;
            const btn = document.getElementById('drBtn');
            
            if (showDeadReckonedOnly) {{
                btn.textContent = 'Show All';
                btn.classList.add('active');
                // Hide all markers first
                Object.values(shipMarkers).forEach(markerGroup => {{
                    markerGroup.forEach(marker => map.removeLayer(marker));
                }});
                // Show only dead reckoned markers
                Object.values(shipMarkers).forEach(markerGroup => {{
                    markerGroup.forEach(marker => {{
                        if (marker.options.isDeadReckoned) {{
                            marker.addTo(map);
                        }}
                    }});
                }});
            }} else {{
                btn.textContent = 'Show DR Only';
                btn.classList.remove('active');
                showAllShips();
            }}
        }}
        
        // Helper functions
        function createShipPopup(ship) {{
            return `
                <div class="ship-info">
                    <h5>${{ship.vessel_name}}</h5>
                    <p><strong>MMSI:</strong> ${{ship.mmsi}}</p>
                    <p><strong>Type:</strong> ${{ship.ship_type}}</p>
                    <p><strong>SOG:</strong> ${{ship.sog.toFixed(1)}} knots</p>
                    <p><strong>COG:</strong> ${{ship.cog.toFixed(1)}}°</p>
                    <p><strong>True Heading:</strong> ${{ship.true_heading === 511 ? 'N/A' : ship.true_heading.toFixed(1) + '°'}}</p>
                    <p><strong>Message Type:</strong> ${{ship.message_type}}</p>
                    <p><strong>Nav Status:</strong> ${{getNavStatusText(ship.nav_status)}}</p>
                    <p><strong>Time:</strong> ${{ship.timestamp}}</p>
                    <p><strong>Dead Reckoned:</strong> ${{ship.is_dead_reckoned ? 'Yes' : 'No'}}</p>
                </div>
            `;
        }}
        
        function createShipInfoHTML(ship, totalPositions) {{
            return `
                <div class="ship-info">
                    <h5>${{ship.vessel_name}}</h5>
                    <p><strong>MMSI:</strong> ${{ship.mmsi}}</p>
                    <p><strong>Ship Type:</strong> ${{ship.ship_type}}</p>
                    <hr style="margin: 8px 0;">
                    <h6 style="margin: 5px 0; color: #2c3e50;">Latest Position Data</h6>
                    <p><strong>Speed over Ground (SOG):</strong> ${{ship.sog.toFixed(1)}} knots</p>
                    <p><strong>Course over Ground (COG):</strong> ${{ship.cog.toFixed(1)}}°</p>
                    <p><strong>True Heading:</strong> ${{ship.true_heading === 511 ? 'N/A' : ship.true_heading.toFixed(1) + '°'}}</p>
                    <p><strong>Message Type:</strong> ${{ship.message_type}} (Class A position report)</p>
                    <p><strong>Navigation Status:</strong> ${{getNavStatusText(ship.nav_status)}}</p>
                    <p><strong>Position:</strong> ${{ship.lat.toFixed(6)}}, ${{ship.lon.toFixed(6)}}</p>
                    <p><strong>Time:</strong> ${{ship.timestamp}}</p>
                    <hr style="margin: 8px 0;">
                    <h6 style="margin: 5px 0; color: #2c3e50;">Track Statistics</h6>
                    <p><strong>Total Positions:</strong> ${{totalPositions}}</p>
                    <p><strong>Dead Reckoned:</strong> ${{ship.is_dead_reckoned ? 'Yes' : 'No'}}</p>
                </div>
            `;
        }}
        
        function getNavStatusText(status) {{
            const statusMap = {{
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
            }};
            return statusMap[status] || `Status ${{status}}`;
        }}
        
        // Add legend
        const legend = L.control({{position: 'bottomright'}});
        legend.onAdd = function (map) {{
            const div = L.DomUtil.create('div', 'legend');
            div.style.backgroundColor = 'white';
            div.style.padding = '10px';
            div.style.borderRadius = '5px';
            div.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
            
            let legendHTML = '<h4>Ship Types</h4>';
            Object.entries(shipTypeColors).forEach(([type, color]) => {{
                legendHTML += `<div class="legend-item"><span class="legend-color" style="background-color: ${{color}};"></span>${{type}}</div>`;
            }});
            
            div.innerHTML = legendHTML;
            return div;
        }};
        legend.addTo(map);
        
        // Initialize display
        updateTime(0);
    </script>
</body>
</html>
"""
    
    # Write the HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Simple map created: {output_file}")
    return output_file

def load_demo_data():
    """Load the demo AIS data"""
    csv_file = "/Users/logeshjankeeram/Desktop/Portathon/Spoofing/mana/examples/demo_ais_data.csv"
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        return df
    else:
        print("Demo data not found. Please generate it first.")
        return None

if __name__ == "__main__":
    # Load demo data
    df = load_demo_data()
    if df is not None:
        # Create simple map
        output_file = "/Users/logeshjankeeram/Desktop/Portathon/Spoofing/mana/examples/simple_map.html"
        create_simple_map_html(df, output_file)
        print(f"Map created successfully: {output_file}")
    else:
        print("Failed to create map - no data available")
