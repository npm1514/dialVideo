import serial
import os
import time
import signal
import sys
import subprocess
import requests
import random
import json

# === SETTINGS ===
# video_dir = "/Users/nickmarucci/CodeProjects/MicroServers/videos"
# video_dir = "/Users/nickmarucci/CodeProjects/MicroServers/beat"
video_dir = "/Users/nickmarucci/CodeProjects/MicroServers/frameofmynd"

arduino_port = "/dev/tty.usbmodem11201"
baud_rate = 9600
vlc_password = str(random.randint(10000, 99999))  # Random password for this session
http_port = 8080
http_host = "127.0.0.1"

# === Load video files (.mov and .mp4) ===
video_files = sorted([
    os.path.join(video_dir, f) for f in os.listdir(video_dir)
    if f.lower().endswith(('.mov', '.mp4'))
])

video_count = len(video_files)
if video_count == 0:
    raise Exception("No .mov or .mp4 files found in directory.")

print(f"Found {video_count} video(s):")
for i, f in enumerate(video_files):
    print(f"  [{i}] {os.path.basename(f)}")

# === Connect to Arduino ===
try:
    print(f"Attempting to connect to Arduino on {arduino_port} at {baud_rate} baud...")
    # Reduced timeout to 0.1 seconds for more responsive reading
    ser = serial.Serial(arduino_port, baud_rate, timeout=0.05, exclusive=True)
    print(f"Connected to Arduino on {arduino_port}")
    # Clear any initial data
    ser.reset_input_buffer()
    print("Arduino connection successful")
except Exception as e:
    print(f"Error connecting to Arduino: {e}")
    print("Continuing without Arduino connection for testing...")
    ser = None

current_index = -1
vlc_process = None

# === Launch VLC ===
def kill_existing_vlc():
    try:
        subprocess.run(["killall", "VLC"], check=False)
        time.sleep(1)  # Wait for VLC to terminate
    except:
        pass

def start_vlc():
    global vlc_process
    
    # Kill any existing VLC processes that might be running
    kill_existing_vlc()
    
    # First check if VLC executable exists
    vlc_path = "/Applications/VLC.app/Contents/MacOS/VLC"
    if not os.path.exists(vlc_path):
        print(f"ERROR: VLC executable not found at {vlc_path}")
        sys.exit(1)
    
    # Start VLC with HTTP interface enabled
    vlc_command = [
        vlc_path,
        "--fullscreen",
        "--no-video-title-show",
        "--no-osd",
        "--http-host", http_host,
        "--http-port", str(http_port),
        "--http-password", vlc_password,
        "--extraintf", "http",
        "--playlist-autostart",
        "--no-video-deco",  # No window decoration
        "--quiet",          # Less console output
        "--video-filter", "transform",  # Enable transform filter
        "--transform-type", "hflip"     # Horizontal flip (mirror effect)
    ]
    
    print("Starting VLC with HTTP interface...")
    vlc_process = subprocess.Popen(vlc_command)
    
    # Give VLC time to start up
    print("Waiting for VLC to initialize...")
    time.sleep(5)  # Need to wait for VLC to fully initialize
    
    # Test if VLC HTTP interface is working
    max_retries = 10
    for attempt in range(max_retries):
        try:
            response = requests.get(f"http://{http_host}:{http_port}/requests/status.json", 
                                   auth=('', vlc_password), 
                                   timeout=1)
            if response.status_code == 200:
                print("VLC HTTP interface is ready")
                break
            else:
                print(f"VLC HTTP not ready yet (status: {response.status_code})")
        except Exception as e:
            print(f"VLC HTTP not ready yet (attempt {attempt+1}/{max_retries}): {e}")
        time.sleep(2)
    else:
        print("Warning: Could not connect to VLC HTTP interface after multiple attempts")
    
    # Add all videos to playlist
    for video in video_files:
        add_to_playlist(video)
    
    print("VLC started successfully")

# === VLC HTTP Control Functions ===
def make_vlc_request(command, params=None, max_retries=3):
    url = f"http://{http_host}:{http_port}/requests/status.json"
    if params:
        command_url = f"{url}?command={command}&{params}"
    else:
        command_url = f"{url}?command={command}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(command_url, auth=('', vlc_password), timeout=1)
            if response.status_code == 200:
                # Check if the response is empty
                if not response.text.strip():
                    if attempt == max_retries - 1:
                        print(f"Empty response from VLC")
                    return {}
                
                # Try to parse JSON
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    if attempt == max_retries - 1:
                        # Only print error on the last attempt
                        print(f"JSON decode error: {e}")
                    time.sleep(0.2)  # Wait before retry
            else:
                if attempt == max_retries - 1:
                    print(f"Error from VLC: {response.status_code}")
                time.sleep(0.2)  # Wait before retry
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to communicate with VLC: {e}")
            time.sleep(0.2)  # Wait before retry
    
    return None  # All retries failed

def add_to_playlist(video_path):
    encoded_path = f"file://{video_path}".replace(" ", "%20")
    result = make_vlc_request("in_enqueue", f"input={encoded_path}")
    print(f"Added to playlist: {os.path.basename(video_path)}")
    return result

def play_video_at_index(index):
    global current_index
    
    # If index is already playing, do nothing
    if index == current_index:
        return
    
    print(f"Switching to video: {index} ({os.path.basename(video_files[index])})")
    
    # VLC playlist indices start at 0
    result = make_vlc_request("pl_play", f"id={index}")
    
    if result is not None:
        current_index = index
        print(f"Now playing: {os.path.basename(video_files[index])}")
        
        # Hide the interface after changing videos
        time.sleep(0.1)  # Brief delay for video to start
        make_vlc_request("key", "key=h")  # Press 'h' to hide interface
    else:
        print("Failed to switch videos")

# === Handle Ctrl+C Cleanly ===
def handle_exit(sig, frame):
    print("\nExiting... shutting down VLC.")
    if vlc_process:
        try:
            vlc_process.terminate()
            vlc_process.wait(timeout=3)
        except:
            # Try to kill VLC more forcefully
            kill_existing_vlc()
    
    if ser:
        ser.close()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)

# === Dial Logic ===
def get_video_index(val):
    zone = val // (1024 // video_count)
    return min(zone, video_count - 1)

# === Start VLC and Main Loop ===
print("Starting VLC and main loop. Press Ctrl+C to exit.")
start_vlc()

# Play the first video to start
play_video_at_index(0)

# === Main Loop ===
last_dial_value = -1
debounce_time = 0.05  # Reduced debounce time for faster response
last_change_time = time.time()
buffer_size = 2       # Reduced buffer size for faster response
recent_values = []    # Store recent values for smoothing

print("Entering main loop. Ready to read dial values.")

while True:
    try:
        if ser:
            # Direct reading approach - read only once per loop for fast response
            raw_data = ser.readline()
            
            if raw_data:
                try:
                    line = raw_data.decode('utf-8', errors='replace').strip()
                    val = int(line)
                    
                    # Add to recent values for smoothing
                    recent_values.append(val)
                    if len(recent_values) > buffer_size:
                        recent_values.pop(0)
                    
                    # Only use the smoothed value if we have enough readings
                    if len(recent_values) >= buffer_size:
                        # Use the last value to be more responsive
                        val = recent_values[-1]
                        
                        # Only process if value changed by more than threshold
                        if abs(val - last_dial_value) > 3:
                            current_time = time.time()
                            # If enough time has passed since last change (debounce)
                            if current_time - last_change_time > debounce_time:
                                # Calculate the video index based on potentiometer value
                                index = get_video_index(val)
                                
                                # Only switch videos if the index changed
                                if index != current_index:
                                    print(f"Dial: {val} → Video: {index}")
                                    play_video_at_index(index)
                                
                                last_dial_value = val
                                last_change_time = current_time
                
                except ValueError:
                    pass  # Silently ignore non-integer values for faster response
                except Exception as e:
                    pass  # Silently ignore other errors for faster response
            
            # Minimal delay to avoid high CPU usage
            time.sleep(0.005)  # Reduced delay for faster response
        else:
            # If no Arduino connected, cycle through videos for testing
            time.sleep(10)
            next_index = (current_index + 1) % video_count
            play_video_at_index(next_index)
            
    except KeyboardInterrupt:
        handle_exit(None, None)
    except Exception as e:
        # Silent error handling to avoid delays
        pass
