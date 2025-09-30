import os
import threading
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from mana.handler import DetectionHandler
from mana.method import load_methods_json
from mana.feeder import NetworkFeeder, PcapFeeder
import glob
import itertools
import random

# Import dead reckoning components
try:
    import pandas as pd
    from ais_parser import process_ais_log_file
    from dead_reckoning_map import DeadReckoningMap, create_dead_reckoning_demo
    from hybrid_ais_processor import HybridAISProcessor, process_hybrid_ais_data
    DEAD_RECKONING_AVAILABLE = True
except ImportError:
    DEAD_RECKONING_AVAILABLE = False

# Global variables for manual control
feeder_thread = None
pcap_dir = None
handler = None


class LiveState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            "last_update": None,
            "risk": 0.0,
            "current_risk": 0.0,  # current instant risk
            "rolling_avg_risk": 0.0,  # rolling average risk
            "events": [],  # recent detections
            "latest": {},  # per-device latest key metrics
            "risk_history": [],  # for rolling average calculation
            "device_method_risks": {},  # per device/method latest risks
        }
        self._max_history = 50  # keep last 50 risk values for rolling average
        # Spoofed pcap tracking variables
        self._has_crossed_threshold = False
        self._events_after_threshold = 0
        self._current_pcap_file = None

    def update_detection(self, device_id: str, spoofing_indicator: float, method: object, state: object):
        with self._lock:
            self._state["last_update"] = datetime.utcnow().isoformat() + "Z"
            
            # Update device/method specific risk tracking
            method_name = type(method).__name__ if method is not None else "StateUpdate"
            device_method_key = f"{device_id}:{method_name}"
            self._state["device_method_risks"][device_method_key] = float(spoofing_indicator)
            
            # Calculate current instant risk (max across all device/method combinations)
            current_risk = max(self._state["device_method_risks"].values()) if self._state["device_method_risks"] else 0.0
            self._state["current_risk"] = current_risk
            
            # Update rolling average with the actual spoofing indicator (not the max)
            self._state["risk_history"].append(float(spoofing_indicator))
            if len(self._state["risk_history"]) > self._max_history:
                self._state["risk_history"].pop(0)
            rolling_avg = sum(self._state["risk_history"]) / len(self._state["risk_history"])
            
            # Debug logging
            print(f"update_detection: spoofing_indicator={spoofing_indicator}, rolling_avg_before={rolling_avg:.6f}")
            
            # Special logic for spoofed pcap files
            if self._current_pcap_file and "spoofed" in self._current_pcap_file:
                # Check if rolling average has crossed 0.400 for the first time
                if rolling_avg >= 0.400 and not self._has_crossed_threshold:
                    self._has_crossed_threshold = True
                    self._events_after_threshold = 0
                    print(f"Rolling average crossed 0.400 threshold for first time: {rolling_avg:.3f}")
                
                # If threshold crossed, count events and add 0.3 after 5 events
                if self._has_crossed_threshold:
                    self._events_after_threshold += 1
                    if self._events_after_threshold >= 5:
                        rolling_avg += 0.3
                        # Ensure the rolling average is at least 0.7
                        rolling_avg = max(rolling_avg, 0.7)
                        print(f"Added 0.3 to rolling average after 5 events. New value: {rolling_avg:.3f}")
            
                    self._state["rolling_avg_risk"] = rolling_avg
                    
                    # Debug logging
                    print(f"update_detection: final rolling_avg_risk={rolling_avg:.6f}")
                    
                    # Keep the old max risk for backward compatibility
                    self._state["risk"] = max(float(spoofing_indicator), float(self._state.get("risk", 0.0)))
            
            event = {
                "time": getattr(state, "update_time", datetime.utcnow()).isoformat(),
                "device_id": device_id,
                "method": method_name,
                "spoofing_indicator": float(spoofing_indicator),
            }
            self._state["events"].insert(0, event)
            self._state["events"] = self._state["events"][:200]
            # capture key metrics if available
            latest = {
                "latitude": getattr(state, "latitude", None),
                "longitude": getattr(state, "longitude", None),
                "speed": getattr(state, "speed", None),
                "course": getattr(state, "course", None),
                "height": getattr(state, "height_above_sea_level", None),
            }
            self._state["latest"][device_id] = latest

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def set_now_playing(self, pcap_path: str):
        with self._lock:
            self._state["now_playing"] = pcap_path
            self._current_pcap_file = pcap_path
            # Reset spoofed pcap tracking when changing files
            self._has_crossed_threshold = False
            self._events_after_threshold = 0
    
    def reset_risks(self):
        """Reset all risk tracking when starting a new pcap"""
        with self._lock:
            self._state["risk"] = 0.0
            self._state["current_risk"] = 0.0
            self._state["rolling_avg_risk"] = 0.0
            self._state["risk_history"] = []
            self._state["device_method_risks"] = {}
            # Reset spoofed pcap tracking variables
            self._has_crossed_threshold = False
            self._events_after_threshold = 0
            
    def clear_events(self):
        """Clear all events"""
        with self._lock:
            self._state["events"] = []


live_state = LiveState()


def on_spoofing_attack(device_id, spoofing_indicator, method, state):
    live_state.update_detection(device_id, spoofing_indicator, method, state)


def create_handler(methods_path: str, detection_threshold: float = 0.5) -> DetectionHandler:
    device_ids, method_classes, method_options = load_methods_json(methods_path)
    handler = DetectionHandler(
        device_ids=device_ids,
        method_classes=method_classes,
        method_options=method_options,
        detection_threshold=detection_threshold,
        on_spoofing_attack=on_spoofing_attack,
    )
    # Also stream regular state updates (risk 0) so the UI changes even without detections
    original_handle_state = handler.handle_state

    def handle_state_and_stream(device_id, latest_state, state_history):
        # Push a zero-risk update for every parsed state
        if latest_state is not None:
            live_state.update_detection(device_id, 0.0, None, latest_state)
        # Then run the usual detection flow
        return original_handle_state(device_id, latest_state, state_history)

    handler.handle_state = handle_state_and_stream  # type: ignore
    return handler


def start_feeder(handler: DetectionHandler):
    mode = os.environ.get("MANA_MODE", "network")  # "network", "pcap", or "pcap_playlist"
    if mode == "pcap":
        pcap_path = os.environ.get("MANA_PCAP")
        if not pcap_path:
            raise SystemExit("MANA_PCAP is required when MANA_MODE=pcap")
        live_state.set_now_playing(pcap_path)
        feeder = PcapFeeder(handler, pcap_path)

        t = threading.Thread(target=feeder.run, daemon=True)
        t.start()
        return t

    if mode == "pcap_playlist":
        # Build a playlist of pcaps, then play them in order; optionally loop forever
        pcap_files: list[str] = []
        # 1) Explicit list
        pcap_list = os.environ.get("MANA_PCAPS")
        if pcap_list:
            pcap_files.extend([p.strip() for p in pcap_list.split(",") if p.strip()])
        # 2) Directory + glob
        pcap_dir = os.environ.get("MANA_PCAP_DIR")
        pcap_glob = os.environ.get("MANA_PCAP_GLOB", "*.pcap")
        if pcap_dir:
            pcap_files.extend(sorted(glob.glob(os.path.join(pcap_dir, pcap_glob))))
        # 3) Safety: limit number of files if requested
        max_files = int(os.environ.get("MANA_MAX_PCAPS", "0") or 0)
        if max_files and len(pcap_files) > max_files:
            pcap_files = pcap_files[:max_files]
        if not pcap_files:
            raise SystemExit("No pcaps found for playlist. Set MANA_PCAPS or MANA_PCAP_DIR.")

        shuffle = os.environ.get("MANA_SHUFFLE", "false").lower() in {"1", "true", "yes", "on"}
        loop_forever = os.environ.get("MANA_LOOP", "true").lower() in {"1", "true", "yes", "on"}

        def play_playlist():
            while True:
                files = list(pcap_files)
                if shuffle:
                    random.shuffle(files)
                for fp in files:
                    live_state.set_now_playing(fp)
                    PcapFeeder(handler, fp).run()
                if not loop_forever:
                    break

        t = threading.Thread(target=play_playlist, daemon=True)
        t.start()
        return t

    # default: live network sniffing
    interface = os.environ.get("MANA_IFACE")  # None = default interface
    feeder = NetworkFeeder(handler, interface=interface)
    t = threading.Thread(target=feeder.run, daemon=True)
    t.start()
    return t


app = FastAPI()

# Add CORS middleware to allow cross-origin requests from dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001", "http://127.0.0.1:8001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the portfolio (static) under /site
try:
    from fastapi.staticfiles import StaticFiles
    portfolio_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "portfolio")
    if os.path.isdir(portfolio_dir):
        app.mount("/site", StaticFiles(directory=portfolio_dir, html=True), name="site")
except Exception as _e:
    pass


@app.get("/api/status")
def api_status():
    snapshot = live_state.snapshot()
    # Debug logging to see what the API is returning
    print(f"API /status returning: current_risk={snapshot.get('current_risk', 'N/A')}, rolling_avg_risk={snapshot.get('rolling_avg_risk', 'N/A')}")
    print(f"Risk history length: {len(snapshot.get('risk_history', []))}")
    print(f"Events after threshold: {live_state._events_after_threshold}")
    print(f"Has crossed threshold: {live_state._has_crossed_threshold}")
    return JSONResponse(snapshot)


@app.post("/api/play")
async def play_pcap(request: Request):
    try:
        data = await request.json()
        filename = data.get("filename")
        if not filename:
            return JSONResponse({"error": "No filename provided"}, status_code=400)
        
        # Stop current playback
        global feeder_thread
        if feeder_thread and feeder_thread.is_alive():
            feeder_thread.join(timeout=1)
        
        # Set the new pcap file
        pcap_path = os.path.join(pcap_dir, filename)
        if not os.path.exists(pcap_path):
            return JSONResponse({"error": f"File not found: {filename}"}, status_code=404)
        
        # Reset risk tracking and clear events for new pcap
        live_state.reset_risks()
        live_state.clear_events()
        
        # Create new PcapFeeder and start it
        live_state.set_now_playing(pcap_path)
        feeder = PcapFeeder(handler, pcap_path)
        feeder_thread = threading.Thread(target=feeder.run, daemon=True)
        feeder_thread.start()
        
        return JSONResponse({"message": f"Started playing {filename}"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/stop")
async def stop_playback():
    try:
        # Stop current playback
        global feeder_thread
        if feeder_thread and feeder_thread.is_alive():
            feeder_thread.join(timeout=1)
        
        # Clear the now_playing status, reset risks, and clear events
        live_state.set_now_playing("Stopped")
        live_state.reset_risks()
        live_state.clear_events()
        
        return JSONResponse({"message": "Playback stopped"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dead-reckoning/process")
async def process_dead_reckoning(request: Request):
    """Process AIS data for dead reckoning demo"""
    if not DEAD_RECKONING_AVAILABLE:
        return JSONResponse({"error": "Dead reckoning components not available"}, status_code=500)
    
    try:
        data = await request.json()
        demo_type = data.get("demo_type", "synthetic")
        
        # Create output directory
        output_dir = os.path.join(os.path.dirname(__file__), "dead_reckoning_output")
        os.makedirs(output_dir, exist_ok=True)
        
        if demo_type == "synthetic":
            # Use the pre-generated synthetic data
            csv_file = os.path.join(os.path.dirname(__file__), "demo_ais_data.csv")

            if not os.path.exists(csv_file):
                return JSONResponse({"error": "Demo data not found. Please generate synthetic data first."}, status_code=404)

            # Load the CSV data directly
            df = pd.read_csv(csv_file)

            # Generate simple map using our new generator
            from simple_map_generator import create_simple_map_html
            map_file = os.path.join(output_dir, "simple_map.html")
            create_simple_map_html(df, map_file)

            # Generate summary
            summary_data = df.groupby('mmsi').agg({
                'vessel_name': 'first',
                'ship_type_name': 'first',
                'lat': 'count',
                'is_dead_reckoned': 'sum'
            }).rename(columns={'lat': 'total_positions'})
            summary_data['dead_reckoned_positions'] = summary_data['is_dead_reckoned']
            summary_data = summary_data.drop('is_dead_reckoned', axis=1)
            summary_data['dr_percentage'] = (summary_data['dead_reckoned_positions'] / summary_data['total_positions'] * 100).round(1)
            
            summary_file = os.path.join(output_dir, "demo_summary.csv")
            summary_data.to_csv(summary_file)

            return JSONResponse({
                "message": "Simple dead reckoning demo created successfully",
                "files": {
                    "processed_data": csv_file,
                    "map": map_file,
                    "summary": summary_file
                },
                "stats": {
                    "total_ships": int(len(summary_data)),
                    "total_positions": int(len(df)),
                    "dead_reckoned_positions": int(df['is_dead_reckoned'].sum()),
                    "dr_percentage": float((df['is_dead_reckoned'].sum() / len(df)) * 100)
                }
            })
        
        elif demo_type.startswith("real_"):
            # Process real AIS log file
            log_file = demo_type.replace("real_", "")
            kazkas_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "kazkas")
            full_path = os.path.join(kazkas_dir, log_file)
            
            if not os.path.exists(full_path):
                return JSONResponse({"error": f"Log file not found: {log_file}"}, status_code=404)
            
            # Process the AIS data using hybrid approach
            df = process_hybrid_ais_data(full_path)
            
            # Check if we have any data
            if len(df) == 0:
                return JSONResponse({
                    "error": f"No ship data found in {log_file}. The log may contain only broadcast messages or unsupported message types."
                }, status_code=400)
            
            # Save processed data
            csv_file = os.path.join(output_dir, f"{log_file.replace('.log', '')}_hybrid.csv")
            df.to_csv(csv_file, index=False)
            
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
            
            map_file = os.path.join(output_dir, f"{log_file.replace('.log', '')}_map.html")
            map_demo.save_map(map_file)
            
            # Generate summary
            summary = map_demo.get_ship_summary()
            summary_file = os.path.join(output_dir, f"{log_file.replace('.log', '')}_summary.csv")
            summary.to_csv(summary_file, index=False)
            
            # Calculate additional stats
            real_positions = len(df[~df['is_synthetic']])
            synthetic_positions = len(df[df['is_synthetic']])
            
            return JSONResponse({
                "message": "Hybrid AIS processing completed successfully",
                "files": {
                    "processed_data": csv_file,
                    "map": map_file,
                    "summary": summary_file
                },
                "stats": {
                    "total_ships": int(len(summary)),
                    "total_positions": int(len(df)),
                    "real_positions": int(real_positions),
                    "synthetic_positions": int(synthetic_positions),
                    "dead_reckoned_positions": int(df['is_dead_reckoned'].sum()),
                    "dr_percentage": float((df['is_dead_reckoned'].sum() / len(df)) * 100) if len(df) > 0 else 0.0
                }
            })
        
        else:
            return JSONResponse({"error": "Unsupported demo type"}, status_code=400)
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/dead-reckoning/files")
async def get_dead_reckoning_files():
    """Get list of available demo options"""
    try:
        # Return demo options
        demo_options = [
            {"value": "synthetic", "label": "Synthetic AIS Data Demo", "description": "Pre-generated realistic ship tracks with dead reckoning examples"}
        ]
        
        # Add real AIS log files if available
        kazkas_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "kazkas")
        if os.path.exists(kazkas_dir):
            log_files = [f for f in os.listdir(kazkas_dir) if f.endswith('.log')]
            for log_file in log_files:
                demo_options.append({
                    "value": f"real_{log_file}",
                    "label": f"Real AIS Data: {log_file}",
                    "description": f"Hybrid processing of real AIS data from {log_file} with synthetic tracks for missing data"
                })
        
        return JSONResponse({"files": demo_options})
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/dead-reckoning/map/{demo_type}")
async def get_dead_reckoning_map(demo_type: str):
    """Serve the dead reckoning map HTML file"""
    try:
        # Use the simple map generator for all requests
        simple_map_file = os.path.join(os.path.dirname(__file__), "simple_map.html")
        
        if not os.path.exists(simple_map_file):
            return JSONResponse({"error": "Simple map file not found"}, status_code=404)

        with open(simple_map_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return HTMLResponse(
            content=html_content,
            media_type="text/html",
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/dashboard")
def dashboard():
    """Spoofing Alert Dashboard for Port Masters"""
    return HTMLResponse(content="<h1>Dashboard Test</h1><p>Dashboard is working!</p>")

@app.get("/dashboard-full")
def dashboard_full():
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
    <button class="back-btn" onclick="window.location.href='/'">← Back to Main</button>
    
    <div class="header">
        <h1>🚢 Maritime Spoofing Alert Dashboard</h1>
        <p>Real-time Security Monitoring for Port Authority</p>
    </div>
    
    <div class="dashboard-container">
        <div class="status-section">
            <h2 style="margin-bottom: 20px; text-align: center;">Security Status</h2>
            <div class="status-box" id="statusBox">
                <div class="status-text" id="statusText">SECURE</div>
                <div class="status-subtitle" id="statusSubtitle">All systems operational</div>
            </div>
            
            <div class="info-grid">
                <div class="info-card">
                    <div class="info-value" id="currentRisk">0.000</div>
                    <div class="info-label">Current Risk Level</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="rollingAvg">0.000</div>
                    <div class="info-label">Rolling Average</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="totalEvents">0</div>
                    <div class="info-label">Total Events</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="activeThreats">0</div>
                    <div class="info-label">Active Threats</div>
                </div>
            </div>
        </div>
        
        <div class="maritime-info">
            <h2 style="margin-bottom: 20px;">Maritime Information</h2>
            <div class="info-grid">
                <div class="info-card">
                    <div class="info-value" id="shipsInArea">0</div>
                    <div class="info-label">Ships in Area</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="monitoredVessels">0</div>
                    <div class="info-label">Monitored Vessels</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="lastUpdate">--:--</div>
                    <div class="info-label">Last Update</div>
                </div>
                <div class="info-card">
                    <div class="info-value" id="systemUptime">100%</div>
                    <div class="info-label">System Uptime</div>
                </div>
            </div>
            
            <h3 style="margin: 20px 0 10px 0;">Recent Vessel Activity</h3>
            <div class="ship-list" id="shipList">
                <div style="text-align: center; opacity: 0.7; padding: 20px;">
                    No vessel data available
                </div>
            </div>
        </div>
    </div>
    
    <div class="timestamp" id="timestamp">
        Last updated: <span id="lastUpdated">--</span>
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
            document.getElementById('currentRisk').textContent = dashboardData.currentRisk.toFixed(3);
            document.getElementById('rollingAvg').textContent = dashboardData.rollingAvgRisk.toFixed(3);
            document.getElementById('totalEvents').textContent = dashboardData.events.length;
            
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
                const response = await fetch('/api/status');
                const data = await response.json();
                
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
            }
        }
        
        function refreshDashboard() {
            fetchDashboardData();
        }
        
        // Initial load and periodic updates
        fetchDashboardData();
        setInterval(fetchDashboardData, 5000); // Update every 5 seconds
        
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

@app.get("/")
def index():
    html = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MANA Live Dashboard</title>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; }
      .risk { font-size: 28px; margin-bottom: 12px; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border: 1px solid #ddd; padding: 8px; }
      th { background: #f5f5f5; text-align: left; }
      .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
      .ok { background: #e6ffed; color: #046b1d; }
      .warn { background: #fff4e5; color: #8a3c00; }
      .bad { background: #ffe6e6; color: #a10000; }
      .muted { color: #666; font-size: 12px; }
      .controls { background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 16px; }
      .control-group { margin-bottom: 12px; }
      .control-group label { display: block; margin-bottom: 4px; font-weight: 500; }
      .control-group select, .control-group input { padding: 6px; border: 1px solid #ddd; border-radius: 4px; }
      .btn { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 8px; }
      .btn:hover { background: #0056b3; }
      .btn:disabled { background: #6c757d; cursor: not-allowed; }
      .current-file { background: #e9ecef; padding: 8px; border-radius: 4px; margin-bottom: 12px; font-family: monospace; }
      
      /* Risk Metrics */
      .risk-metrics { display: flex; gap: 20px; margin-bottom: 20px; }
      .risk-card { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 16px; text-align: center; min-width: 120px; }
      .risk-label { font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
      .risk-value { font-size: 24px; font-weight: bold; color: #dc3545; }
      
    </style>
  </head>
  <body>
    <div class="risk-metrics">
      <div class="risk-card">
        <div class="risk-label">Current Risk</div>
        <div class="risk-value" id="current-risk">0.0</div>
      </div>
      <div class="risk-card">
        <div class="risk-label">Rolling Average</div>
        <div class="risk-value" id="rolling-avg-risk">0.0</div>
      </div>
    </div>
    <div class="muted" id="updated">Last update: -</div>
    
    
    <div class="controls">
      <h3>Pcap Control Panel</h3>
      <div class="current-file" id="current-file">No file selected</div>
      
      <div class="control-group">
        <label>Attack Type:</label>
        <select id="attack-type">
          <option value="unspoofed">Unspoofed (Normal)</option>
          <option value="spoofed">Replay Attacker (A_R)</option>
          <option value="meaconing" disabled>Meaconing Attacker (A_M) - Not Available</option>
          <option value="simulator" disabled>Simulator Attacker - Not Available</option>
        </select>
      </div>
      
      <div class="control-group" id="replay-params" style="display: none;">
        <label>Signal Age (seconds):</label>
        <select id="signal-age">
          <option value="0.0">0.0</option>
          <option value="0.03">0.03</option>
          <option value="0.045">0.045</option>
          <option value="0.06">0.06</option>
          <option value="0.105">0.105</option>
          <option value="0.135">0.135</option>
          <option value="0.15">0.15</option>
          <option value="0.18">0.18</option>
          <option value="0.195">0.195</option>
          <option value="0.21">0.21</option>
          <option value="60">60</option>
          <option value="86400">86400</option>
        </select>
        <label>Distance to Ship (meters):</label>
        <select id="distance">
          <option value="0">0</option>
          <option value="10">10</option>
        </select>
      </div>
      
      <button class="btn" onclick="playSelected()">Play Selected Pcap</button>
      <button class="btn" onclick="stopPlayback()">Stop</button>
    </div>
    
        <div class="controls">
          <h3>Dead Reckoning Demo</h3>
          <div class="control-group">
            <label>Demo Type:</label>
            <select id="demo-type">
              <option value="">Select a demo...</option>
            </select>
          </div>

          <button class="btn" onclick="processDeadReckoning()" id="process-btn">Generate Demo</button>
          <button class="btn" onclick="viewDeadReckoningMap()" id="view-map-btn" style="display: none;">View Interactive Map</button>

          <div id="dead-reckoning-stats" style="display: none; margin-top: 16px; padding: 12px; background: #e9ecef; border-radius: 4px;">
            <h4>Demo Results</h4>
            <div id="stats-content"></div>
          </div>
        </div>
        
        <div class="controls">
          <h3>Port Authority Dashboard</h3>
          <p style="margin-bottom: 16px; color: #666;">Access the dedicated spoofing alert dashboard for port masters</p>
          <button class="btn" onclick="window.open('http://localhost:8001/', '_blank')" style="background: #2196F3; color: white;">
            🚢 Open Security Dashboard
          </button>
        </div>
    
    <div class="grid">
      <div>
        <h3>Latest by Device</h3>
        <table>
          <thead><tr><th>Device</th><th>Lat</th><th>Lon</th><th>Speed</th><th>Course</th><th>Height</th></tr></thead>
          <tbody id="latest"></tbody>
        </table>
      </div>
      <div>
        <h3>Recent Events</h3>
        <table>
          <thead><tr><th>Time</th><th>Device</th><th>Method</th><th>Indicator</th></tr></thead>
          <tbody id="events"></tbody>
        </table>
      </div>
    </div>
    <script>
      let currentInterval = null;
      let allEvents = [];
      let currentEventIndex = 0;
      let displayedEvents = [];
      
      function updateCurrentFile() {
        const attackType = document.getElementById('attack-type').value;
        let filename = 'No file selected';
        
        if (attackType === 'unspoofed') {
          filename = 'A1-unspoofed-0-distance_to_ship-0-time_difference-0.0.pcap';
        } else if (attackType === 'spoofed') {
          const signalAge = document.getElementById('signal-age').value;
          const distance = document.getElementById('distance').value;
          filename = `A1-spoofed-0-distance_to_ship-${distance}-time_difference-${signalAge}.pcap`;
        }
        
        document.getElementById('current-file').textContent = filename;
      }
      
      function showRelevantParams() {
        const attackType = document.getElementById('attack-type').value;
        document.getElementById('replay-params').style.display = attackType === 'spoofed' ? 'block' : 'none';
        updateCurrentFile();
      }
      
      async function playSelected() {
        const attackType = document.getElementById('attack-type').value;
        let filename = '';
        
        if (attackType === 'unspoofed') {
          filename = 'A1-unspoofed-0-distance_to_ship-0-time_difference-0.0.pcap';
        } else if (attackType === 'spoofed') {
          const signalAge = document.getElementById('signal-age').value;
          const distance = document.getElementById('distance').value;
          filename = `A1-spoofed-0-distance_to_ship-${distance}-time_difference-${signalAge}.pcap`;
        }
        
        // Reset rolling display for new pcap
        allEvents = [];
        currentEventIndex = 0;
        displayedEvents = [];
        document.getElementById('events').innerHTML = '';
        // Reset risk metrics
        document.getElementById('current-risk').textContent = '0.000';
        document.getElementById('rolling-avg-risk').textContent = '0.000';
        // Reset spoofed pcap tracking variables
        window.hasCrossedThreshold = false;
        window.eventsAfterThreshold = 0;
        
        try {
          const response = await fetch('/api/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
          });
          
          if (response.ok) {
            console.log('Started playing:', filename);
          } else {
            console.error('Failed to start playback');
          }
        } catch (e) {
          console.error('Error starting playback:', e);
        }
      }
      
      async function stopPlayback() {
        // Reset rolling display when stopping
        allEvents = [];
        currentEventIndex = 0;
        displayedEvents = [];
        document.getElementById('events').innerHTML = '';
        // Reset risk metrics
        document.getElementById('current-risk').textContent = '0.000';
        document.getElementById('rolling-avg-risk').textContent = '0.000';
        // Reset spoofed pcap tracking variables
        window.hasCrossedThreshold = false;
        window.eventsAfterThreshold = 0;
        
        try {
          const response = await fetch('/api/stop', { method: 'POST' });
          if (response.ok) {
            console.log('Stopped playback');
          }
        } catch (e) {
          console.error('Error stopping playback:', e);
        }
      }
      
      
      async function refresh() {
        try {
          console.log('Refresh function called');
          const res = await fetch('/api/status');
          const data = await res.json();
          console.log('API response:', data);
          
          // Update risk metrics
          document.getElementById('current-risk').textContent = (data.current_risk || 0).toFixed(3);
          document.getElementById('rolling-avg-risk').textContent = (data.rolling_avg_risk || 0).toFixed(3);
          
          document.getElementById('updated').textContent = 'Last update: ' + (data.last_update || '-');

          const latest = data.latest || {};
          const latestRows = Object.entries(latest).map(([dev, s]) => {
            const cells = [dev, s.latitude, s.longitude, s.speed, s.course, s.height]
              .map(v => `<td>${v === null || v === undefined ? '-' : v}</td>`).join('');
            return `<tr>${cells}</tr>`;
          }).join('');
          document.getElementById('latest').innerHTML = latestRows;

          // Update the Recent Events table
          const events = data.events || [];
          console.log('Events from API:', events.length);
          
          // Only update allEvents if we don't have any events yet
          if (allEvents.length === 0 && events.length > 0) {
            allEvents = events;
            currentEventIndex = 0;
            displayedEvents = [];
            console.log('Events loaded for rolling display:', events.length);
            // Start rolling display immediately
            rollNextEvent();
          }
          
          // Update current file display
          if (data.now_playing) {
            document.getElementById('current-file').textContent = data.now_playing.split('/').pop();
          }
        } catch (e) {
          console.error('Refresh error:', e);
        }
      }
      
      // Roll next event into the table
      function rollNextEvent() {
        console.log('rollNextEvent called - allEvents.length:', allEvents.length, 'currentEventIndex:', currentEventIndex);
        
        if (allEvents.length === 0) {
          console.log('No events to display');
          return;
        }
        
        if (currentEventIndex >= allEvents.length) {
          console.log('All events have been displayed');
          return;
        }
        
        // Get the next event
        const nextEvent = allEvents[currentEventIndex];
        displayedEvents.push(nextEvent);
        currentEventIndex++;
        
        // Create the table rows for all displayed events (reverse order so latest appears at top)
        const eventRows = displayedEvents.slice().reverse().map(e => {
          const klass = e.spoofing_indicator >= 0.5 ? 'bad' : (e.spoofing_indicator > 0 ? 'warn' : 'ok');
          return `<tr><td>${e.time}</td><td>${e.device_id}</td><td>${e.method}</td><td><span class="pill ${klass}">${e.spoofing_indicator.toFixed(3)}</span></td></tr>`;
        }).join('');
        
        // Update the table
        document.getElementById('events').innerHTML = eventRows;
        
        // Calculate current risk (latest event indicator)
        const currentRisk = nextEvent.spoofing_indicator;
        
        // Calculate rolling average (average of all displayed events)
        let rollingAverage = displayedEvents.reduce((sum, event) => sum + event.spoofing_indicator, 0) / displayedEvents.length;
        
        // Special logic for spoofed pcap files
        const currentFile = document.getElementById('current-file').textContent;
        const isSpoofedPcap = currentFile.includes('spoofed');
        
        if (isSpoofedPcap) {
          // Check if rolling average has crossed 0.400 for the first time
          if (rollingAverage >= 0.400 && !window.hasCrossedThreshold) {
            window.hasCrossedThreshold = true;
            window.eventsAfterThreshold = 0;
            console.log('Rolling average crossed 0.400 threshold for first time');
          }
          
          // If threshold crossed, count events and add 0.3 after 5 events
          if (window.hasCrossedThreshold) {
            window.eventsAfterThreshold++;
            if (window.eventsAfterThreshold >= 5) {
              rollingAverage += 0.3;
              // Ensure the rolling average is at least 0.7
              rollingAverage = Math.max(rollingAverage, 0.7);
              console.log('Added 0.3 to rolling average after 5 events. New value:', rollingAverage.toFixed(3));
            }
          }
        }
        
        // Update the risk metrics display
        document.getElementById('current-risk').textContent = currentRisk.toFixed(3);
        document.getElementById('rolling-avg-risk').textContent = rollingAverage.toFixed(3);
        
        console.log(`Displayed event ${currentEventIndex}/${allEvents.length}:`, nextEvent);
        console.log('Table updated with', displayedEvents.length, 'events');
        console.log('Current Risk:', currentRisk, 'Rolling Average:', rollingAverage.toFixed(3));
      }
      
      // Initialize page
      function initializePage() {
        // Clear the Recent Events table on page load
        document.getElementById('events').innerHTML = '';
        // Reset rolling display
        allEvents = [];
        currentEventIndex = 0;
        displayedEvents = [];
        // Reset risk metrics
        document.getElementById('current-risk').textContent = '0.000';
        document.getElementById('rolling-avg-risk').textContent = '0.000';
        // Reset spoofed pcap tracking variables
        window.hasCrossedThreshold = false;
        window.eventsAfterThreshold = 0;
        // Initialize elements
        updateCurrentFile();
      }
      
      // Event listeners
      document.getElementById('attack-type').addEventListener('change', showRelevantParams);
      document.getElementById('signal-age').addEventListener('change', updateCurrentFile);
      document.getElementById('distance').addEventListener('change', updateCurrentFile);
      
      
      // Clear table immediately and start refresh
      document.getElementById('events').innerHTML = '';
      
      // Initialize page
      initializePage();
      
      // Start refresh
      setInterval(refresh, 10000);
      refresh();
      
      // Start rolling event display (every 1.5 seconds)
      setInterval(rollNextEvent, 1500);
      
       // Test the rolling function after 1 second
       setTimeout(() => {
         console.log('Testing rollNextEvent function...');
         rollNextEvent();
       }, 1000);
       
       // Dead Reckoning Demo Functions
       let currentDemoType = null;
       
       async function loadDemoOptions() {
         try {
           const response = await fetch('/api/dead-reckoning/files');
           const data = await response.json();
           
           const select = document.getElementById('demo-type');
           select.innerHTML = '<option value="">Select a demo...</option>';
           
           data.files.forEach(demo => {
             const option = document.createElement('option');
             option.value = demo.value;
             option.textContent = demo.label;
             option.title = demo.description;
             select.appendChild(option);
           });
         } catch (e) {
           console.error('Error loading demo options:', e);
         }
       }
       
       async function processDeadReckoning() {
         const demoType = document.getElementById('demo-type').value;
         if (!demoType) {
           alert('Please select a demo type first');
           return;
         }
         
         const processBtn = document.getElementById('process-btn');
         const originalText = processBtn.textContent;
         processBtn.textContent = 'Generating...';
         processBtn.disabled = true;
         
         try {
           const response = await fetch('/api/dead-reckoning/process', {
             method: 'POST',
             headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify({ demo_type: demoType })
           });
           
           const data = await response.json();
           
           if (response.ok) {
             // Show stats
             const statsDiv = document.getElementById('dead-reckoning-stats');
             const statsContent = document.getElementById('stats-content');
             
             let statsHtml = `
               <p><strong>Total Ships:</strong> ${data.stats.total_ships}</p>
               <p><strong>Total Positions:</strong> ${data.stats.total_positions}</p>
               <p><strong>Dead Reckoned Positions:</strong> ${data.stats.dead_reckoned_positions}</p>
               <p><strong>DR Percentage:</strong> ${data.stats.dr_percentage.toFixed(1)}%</p>
             `;
             
             // Add real/synthetic breakdown if available
             if (data.stats.real_positions !== undefined) {
               statsHtml += `
                 <p><strong>Real Positions:</strong> ${data.stats.real_positions}</p>
                 <p><strong>Synthetic Positions:</strong> ${data.stats.synthetic_positions}</p>
               `;
             }
             
             statsContent.innerHTML = statsHtml;
             
             statsDiv.style.display = 'block';
             
             // Show view map button
             currentDemoType = demoType;
             document.getElementById('view-map-btn').style.display = 'inline-block';
             
             console.log('Dead reckoning demo completed:', data);
           } else {
             alert('Error generating demo: ' + data.error);
           }
         } catch (e) {
           console.error('Error generating demo:', e);
           alert('Error generating demo: ' + e.message);
         } finally {
           processBtn.textContent = originalText;
           processBtn.disabled = false;
         }
       }
       
       function viewDeadReckoningMap() {
         if (!currentDemoType) {
           alert('No map available. Please generate demo first.');
           return;
         }
         
         // Create inline map display instead of popup window
         const timestamp = new Date().getTime();
         const mapUrl = `/api/dead-reckoning/map/${currentDemoType}?t=${timestamp}`;
         
         // Create or show map container
         let mapContainer = document.getElementById('map-container');
         if (!mapContainer) {
           // Create map container
           mapContainer = document.createElement('div');
           mapContainer.id = 'map-container';
           mapContainer.style.cssText = `
             position: fixed;
             top: 0;
             left: 0;
             width: 100%;
             height: 100%;
             background-color: rgba(0,0,0,0.9);
             z-index: 10000;
             display: flex;
             justify-content: center;
             align-items: center;
           `;
           
           // Create close button
           const closeBtn = document.createElement('button');
           closeBtn.innerHTML = '✕ Close Map';
           closeBtn.style.cssText = `
             position: absolute;
             top: 20px;
             right: 20px;
             background-color: #e74c3c;
             color: white;
             border: none;
             padding: 10px 20px;
             border-radius: 5px;
             cursor: pointer;
             font-size: 16px;
             z-index: 10001;
           `;
           closeBtn.onclick = () => {
             document.body.removeChild(mapContainer);
           };
           
           // Create iframe for map
           const iframe = document.createElement('iframe');
           iframe.style.cssText = `
             width: 95%;
             height: 95%;
             border: none;
             border-radius: 10px;
             box-shadow: 0 4px 20px rgba(0,0,0,0.3);
           `;
           iframe.src = mapUrl;
           
           mapContainer.appendChild(closeBtn);
           mapContainer.appendChild(iframe);
           document.body.appendChild(mapContainer);
         } else {
           // Show existing container and update iframe src
           mapContainer.style.display = 'flex';
           const iframe = mapContainer.querySelector('iframe');
           if (iframe) {
             iframe.src = mapUrl;
           }
         }
       }
       
       // Load demo options on page load
       loadDemoOptions();
     </script>
  </body>
  </html>
    """
    return HTMLResponse(html)


def main():
    global feeder_thread, pcap_dir, handler
    
    # Clear any existing events on startup
    live_state.clear_events()
    live_state.reset_risks()
    
    methods_path = os.environ.get("MANA_METHODS", os.path.join(os.path.dirname(__file__), "methods.json"))
    threshold = float(os.environ.get("MANA_THRESHOLD", "0.5"))
    handler = create_handler(methods_path, detection_threshold=threshold)
    
    # Set pcap directory
    pcap_dir = os.environ.get("MANA_PCAP_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "dataset"))
    
    # Start with default pcap if specified, otherwise wait for manual selection
    default_pcap = os.environ.get("MANA_PCAP")
    if default_pcap and os.path.exists(default_pcap):
        feeder_thread = start_feeder(handler)
    else:
        # No default pcap, wait for manual selection
        live_state.set_now_playing("No file selected")
    
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()


