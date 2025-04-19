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
video_dir = "/Users/nickmarucci/CodeProjects/MicroServers/videos"
arduino_port = "/dev/tty.usbmodem11101"
baud_rate = 9600
vlc_password = str(random.randint(10000, 99999))  # Random password for this session
http_port = 8080
http_host = "127.0.0.1"

# === Load .mov files ===
video_files = sorted([
    os.path.join(video_dir, f) for f in os.listdir(video_dir)
    if f.lower().endswith('.mov')
])

video_count = len(video_files)
if video_count == 0:
    raise Exception("No .mov files found in directory.")

print(f"Found {video_count} .mov video(s):")
for i, f in enumerate(video_files):
    print(f"  [{i}] {os.path.basename(f)}")

# === Connect to Arduino ===
try:
    ser = serial.Serial(arduino_port, baud_rate, timeout=1)
    print(f"Connected to Arduino on {arduino_port}")
except Exception as e:
    print(f"Error connecting to Arduino: {e}")
    print("Continuing without Arduino connection for testing...")
    ser = None

current_index = -1
vlc_process = None

# === Launch VLC ===
def start_vlc():
    global vlc_process
    
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
        "--playlist-autostart"
    ]
    
    print("Starting VLC with HTTP interface...")
    vlc_process = subprocess.Popen(vlc_command)
    
    # Give VLC time to start
    time.sleep(3)
    
    # Add all videos to playlist
    for video in video_files:
        add_to_playlist(video)
    
    print("VLC started successfully with HTTP interface")

# === VLC HTTP Control Functions ===
def make_vlc_request(command, params=None):
    url = f"http://{http_host}:{http_port}/requests/status.json"
    if params:
        command_url = f"{url}?command={command}&{params}"
    else:
        command_url = f"{url}?command={command}"
    
    try:
        response = requests.get(command_url, auth=('', vlc_password), timeout=2)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error from VLC: {response.status_code}")
            return None
    except Exception as e:
        print(f"Failed to communicate with VLC: {e}")
        return None

def add_to_playlist(video_path):
    encoded_path = f"file://{video_path}".replace(" ", "%20")
    make_vlc_request("in_enqueue", f"input={encoded_path}")
    print(f"Added to playlist: {os.path.basename(video_path)}")

def play_video_at_index(index):
    global current_index
    
    # If index is already playing, do nothing
    if index == current_index:
        return
    
    print(f"Switching to video: {index} ({os.path.basename(video_files[index])})")
    
    # VLC playlist indices start at 0
    result = make_vlc_request("pl_play", f"id={index}")
    
    if result:
        current_index = index
        print(f"Now playing: {os.path.basename(video_files[index])}")
        
        # Hide the interface after changing videos (wait a moment for video to start)
        time.sleep(0.5)
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
            try:
                vlc_process.kill()
                subprocess.run(["killall", "VLC"], check=False)
            except:
                pass
    
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
while True:
    try:
        if ser:
            line = ser.readline().decode('utf-8').strip()
            if not line:
                time.sleep(0.1)
                continue
            
            try:
                val = int(line)
                index = get_video_index(val)
                if index != current_index:
                    play_video_at_index(index)
            except ValueError:
                print(f"Received non-integer value: {line}")
        else:
            # If no Arduino connected, cycle through videos for testing
            time.sleep(10)  # Longer delay to see videos
            next_index = (current_index + 1) % video_count
            play_video_at_index(next_index)
            
    except Exception as e:
        print("Error:", e)
        time.sleep(1)
