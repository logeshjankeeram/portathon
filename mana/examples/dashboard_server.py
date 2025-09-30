#!/usr/bin/env python3
"""
Simple Dashboard Server for Maritime Spoofing Alert Dashboard
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

@app.get("/")
def dashboard():
    """Spoofing Alert Dashboard for Port Masters"""
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Maritime Spoofing Alert Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .header {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .dashboard-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            padding: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .status-section {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .status-box {
            width: 100%;
            height: 200px;
            border-radius: 15px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            margin-bottom: 20px;
            transition: all 0.3s ease;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        
        .status-green {
            background: linear-gradient(135deg, #4CAF50, #45a049);
        }
        
        .status-amber {
            background: linear-gradient(135deg, #FF9800, #F57C00);
        }
        
        .status-red {
            background: linear-gradient(135deg, #F44336, #D32F2F);
        }
        
        .status-text {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }
        
        .status-subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        .info-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .info-value {
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
            color: #64B5F6;
        }
        
        .info-label {
            font-size: 0.9em;
            opacity: 0.8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .maritime-info {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .ship-list {
            max-height: 300px;
            overflow-y: auto;
            margin-top: 20px;
        }
        
        .ship-item {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .ship-name {
            font-weight: bold;
        }
        
        .ship-status {
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
        }
        
        .status-normal {
            background: #4CAF50;
            color: white;
        }
        
        .status-warning {
            background: #FF9800;
            color: white;
        }
        
        .status-danger {
            background: #F44336;
            color: white;
        }
        
        .timestamp {
            text-align: center;
            margin-top: 20px;
            font-size: 1.1em;
            opacity: 0.8;
        }
        
        .refresh-btn {
            background: #2196F3;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
            cursor: pointer;
            margin: 20px auto;
            display: block;
            transition: all 0.3s ease;
        }
        
        .refresh-btn:hover {
            background: #1976D2;
            transform: translateY(-2px);
        }
        
        .back-btn {
            position: fixed;
            top: 20px;
            left: 20px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 20px;
            cursor: pointer;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        
        .back-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        @media (max-width: 768px) {
            .dashboard-container {
                grid-template-columns: 1fr;
                padding: 20px;
            }
            
            .info-grid {
                grid-template-columns: 1fr;
            }
            
            .header h1 {
                font-size: 2em;
            }
        }
    </style>
</head>
<body>
    <button class="back-btn" onclick="window.location.href='http://localhost:8000/'">← Back to Main</button>
    
    <div class="header">
        <h1>🚢 Maritime Spoofing Alert Dashboard</h1>
        <p>Real-time Security Monitoring for Port Authority</p>
    </div>
    
    <div class="dashboard-container">
        <div class="status-section">
            <h2 style="margin-bottom: 20px; text-align: center;">Security Status</h2>
            <div class="status-box status-red" id="statusBox">
                <div class="status-text" id="statusText">ALERT</div>
                <div class="status-subtitle" id="statusSubtitle">High risk detected - Immediate attention required</div>
            </div>
            
            <div class="info-grid">
                <div class="info-card">
                    <div class="info-value" id="currentRisk">1.000</div>
                    <div class="info-label">Current Risk Level</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="rollingAvg">0.427</div>
                    <div class="info-label">Rolling Average</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="totalEvents">120</div>
                    <div class="info-label">Total Events</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="activeThreats">45</div>
                    <div class="info-label">Active Threats</div>
                </div>
            </div>
        </div>
        
        <div class="maritime-info">
            <h2 style="margin-bottom: 20px;">Maritime Information</h2>
            <div class="info-grid">
                <div class="info-card">
                    <div class="info-value" id="shipsInArea">2</div>
                    <div class="info-label">Ships in Area</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="monitoredVessels">2</div>
                    <div class="info-label">Monitored Vessels</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="lastUpdate">13:36</div>
                    <div class="info-label">Last Update</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="systemUptime">100%</div>
                    <div class="info-label">System Uptime</div>
                </div>
            </div>
            
            <h3 style="margin: 20px 0 10px 0;">Recent Vessel Activity</h3>
            <div class="ship-list" id="shipList">
                <div class="ship-item">
                    <div>
                        <div class="ship-name">192.168.0.11</div>
                        <div style="font-size: 0.8em; opacity: 0.7;">OrbitPositionsMethod • 2018-09-21T13:01:59</div>
                    </div>
                    <div class="ship-status status-danger">High Risk</div>
                </div>
                <div class="ship-item">
                    <div>
                        <div class="ship-name">192.168.0.10</div>
                        <div style="font-size: 0.8em; opacity: 0.7;">CarrierToNoiseDensityMethod • 2018-09-21T13:01:59</div>
                    </div>
                    <div class="ship-status status-warning">Caution</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="timestamp" id="timestamp">
        Last updated: <span id="lastUpdated">2025-09-27 13:36:46</span>
    </div>
    
    <button class="refresh-btn" onclick="refreshDashboard()">🔄 Refresh Data</button>

    <script>
        let dashboardData = {
            risk: 0.0,
            currentRisk: 0.0,
            rollingAvgRisk: 0.0,
            events: [],
            shipsInArea: 0,
            monitoredVessels: 0,
            lastUpdate: null
        };
        
        function updateStatusBox() {
            const statusBox = document.getElementById('statusBox');
            const statusText = document.getElementById('statusText');
            const statusSubtitle = document.getElementById('statusSubtitle');
            
            const risk = dashboardData.currentRisk;
            
            if (risk < 0.3) {
                statusBox.className = 'status-box status-green';
                statusText.textContent = 'SECURE';
                statusSubtitle.textContent = 'All systems operational - Low risk detected';
            } else if (risk < 0.7) {
                statusBox.className = 'status-box status-amber';
                statusText.textContent = 'CAUTION';
                statusSubtitle.textContent = 'Moderate risk detected - Enhanced monitoring active';
            } else {
                statusBox.className = 'status-box status-red';
                statusText.textContent = 'ALERT';
                statusSubtitle.textContent = 'High risk detected - Immediate attention required';
            }
        }
        
        function updateDashboard() {
            // Update risk metrics
            console.log('Updating dashboard with:', {
                currentRisk: dashboardData.currentRisk,
                rollingAvgRisk: dashboardData.rollingAvgRisk,
                eventsCount: dashboardData.events.length
            });
            
            // Add visual indicator that values are updating
            const currentRiskEl = document.getElementById('currentRisk');
            const rollingAvgEl = document.getElementById('rollingAvg');
            const totalEventsEl = document.getElementById('totalEvents');
            
            // Flash the elements to show they're updating
            currentRiskEl.style.backgroundColor = '#e3f2fd';
            rollingAvgEl.style.backgroundColor = '#e3f2fd';
            totalEventsEl.style.backgroundColor = '#e3f2fd';
            
            setTimeout(() => {
                currentRiskEl.style.backgroundColor = '';
                rollingAvgEl.style.backgroundColor = '';
                totalEventsEl.style.backgroundColor = '';
            }, 200);
            
            currentRiskEl.textContent = dashboardData.currentRisk.toFixed(3);
            rollingAvgEl.textContent = dashboardData.rollingAvgRisk.toFixed(3);
            totalEventsEl.textContent = dashboardData.events.length;
            
            // Calculate active threats (events with risk > 0.5)
            const activeThreats = dashboardData.events.filter(e => e.spoofing_indicator > 0.5).length;
            document.getElementById('activeThreats').textContent = activeThreats;
            
            // Update maritime info
            document.getElementById('shipsInArea').textContent = dashboardData.shipsInArea;
            document.getElementById('monitoredVessels').textContent = dashboardData.monitoredVessels;
            
            // Update timestamp
            const now = new Date();
            document.getElementById('lastUpdated').textContent = now.toLocaleString();
            document.getElementById('lastUpdate').textContent = now.toLocaleTimeString();
            
            // Update status box
            updateStatusBox();
            
            // Update ship list
            updateShipList();
        }
        
        function updateShipList() {
            const shipList = document.getElementById('shipList');
            
            if (dashboardData.events.length === 0) {
                shipList.innerHTML = '<div style="text-align: center; opacity: 0.7; padding: 20px;">No vessel data available</div>';
                return;
            }
            
            // Get unique vessels from recent events
            const vesselMap = new Map();
            dashboardData.events.slice(-20).forEach(event => {
                if (!vesselMap.has(event.device_id)) {
                    vesselMap.set(event.device_id, {
                        name: event.device_id,
                        risk: event.spoofing_indicator,
                        time: event.time,
                        method: event.method
                    });
                }
            });
            
            const vessels = Array.from(vesselMap.values()).sort((a, b) => b.risk - a.risk);
            
            shipList.innerHTML = vessels.map(vessel => {
                let statusClass = 'status-normal';
                let statusText = 'Normal';
                
                if (vessel.risk > 0.7) {
                    statusClass = 'status-danger';
                    statusText = 'High Risk';
                } else if (vessel.risk > 0.3) {
                    statusClass = 'status-warning';
                    statusText = 'Caution';
                }
                
                return `
                    <div class="ship-item">
                        <div>
                            <div class="ship-name">${vessel.name}</div>
                            <div style="font-size: 0.8em; opacity: 0.7;">${vessel.method} • ${vessel.time}</div>
                        </div>
                        <div class="ship-status ${statusClass}">${statusText}</div>
                    </div>
                `;
            }).join('');
        }
        
        async function fetchDashboardData() {
            try {
                // Add timestamp to prevent caching
                const timestamp = new Date().getTime();
                const response = await fetch(`http://localhost:8000/api/status?t=${timestamp}`);
                const data = await response.json();
                
                console.log('Dashboard fetched data:', {
                    current_risk: data.current_risk,
                    rolling_avg_risk: data.rolling_avg_risk,
                    events_count: data.events ? data.events.length : 0,
                    timestamp: new Date().toISOString()
                });
                
                // Check if values are actually changing
                if (dashboardData.rollingAvgRisk !== data.rolling_avg_risk) {
                    console.log(`Rolling average changed: ${dashboardData.rollingAvgRisk} -> ${data.rolling_avg_risk}`);
                }
                
                dashboardData = {
                    risk: data.risk || 0.0,
                    currentRisk: data.current_risk || 0.0,
                    rollingAvgRisk: data.rolling_avg_risk || 0.0,
                    events: data.events || [],
                    shipsInArea: data.events ? new Set(data.events.map(e => e.device_id)).size : 0,
                    monitoredVessels: data.events ? new Set(data.events.map(e => e.device_id)).size : 0,
                    lastUpdate: data.last_update
                };
                
                updateDashboard();
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
                // Update timestamp even if fetch fails
                const now = new Date();
                document.getElementById('lastUpdated').textContent = now.toLocaleString();
                document.getElementById('lastUpdate').textContent = now.toLocaleTimeString();
            }
        }
        
        function refreshDashboard() {
            fetchDashboardData();
        }
        
        // Initial load and periodic updates
        fetchDashboardData();
        setInterval(fetchDashboardData, 1000); // Update every 1 second
        
        // Update timestamp every second
        setInterval(() => {
            const now = new Date();
            document.getElementById('lastUpdated').textContent = now.toLocaleString();
        }, 1000);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
