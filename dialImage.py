import serial
import os
import time
import signal
import sys
import cv2
import numpy as np

# === SETTINGS ===
image_dir = "/Users/nickmarucci/CodeProjects/MicroServers/images"
arduino_port = "/dev/tty.usbmodem1201"
baud_rate = 9600
display_time = 10  # Time to display each image in seconds

# === Load image files ===
supported_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
try:
    image_files = sorted([
        os.path.join(image_dir, f) for f in os.listdir(image_dir)
        if any(f.lower().endswith(ext) for ext in supported_extensions)
    ])
    
    image_count = len(image_files)
    if image_count == 0:
        raise Exception("No image files found in directory.")
    
    print(f"Found {image_count} image(s):")
    for i, f in enumerate(image_files):
        print(f"  [{i}] {os.path.basename(f)}")
except Exception as e:
    print(f"Error loading images: {e}")
    sys.exit(1)

# === Connect to Arduino ===
try:
    ser = serial.Serial(arduino_port, baud_rate, timeout=1)
    print(f"Connected to Arduino on {arduino_port}")
except Exception as e:
    print(f"Error connecting to Arduino: {e}")
    print("Continuing without Arduino connection for testing...")
    ser = None

# === Setup window ===
window_name = "Image Slideshow"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# Get screen size (hardcoded as fallback if we can't get through OpenCV)
screen_width = 1920  # Increased from 1728
screen_height = 1200  # Increased from 1117
try:
    # Try to set the window size before getting dimensions
    cv2.resizeWindow(window_name, screen_width, screen_height)
except Exception as e:
    print(f"Warning: Could not resize window: {e}")

# === Dial Logic ===
def get_image_index(val):
    zone = val // (1024 // image_count)
    return min(zone, image_count - 1)

# === Handle Ctrl+C Cleanly ===
def handle_exit(sig, frame):
    print("\nExiting image viewer.")
    
    # Close all OpenCV windows
    cv2.destroyAllWindows()
    
    # Close serial connection if open
    if ser:
        ser.close()
    
    print("Cleanup complete")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

def display_image(image_path):
    try:
        print(f"Loading image: {os.path.basename(image_path)}")
        img = cv2.imread(image_path)
        
        if img is None:
            print(f"Failed to load image: {image_path}")
            return False
        
        # Get image dimensions
        img_h, img_w = img.shape[:2]
        
        # Calculate resize ratio to fit screen
        scale = min(screen_width / img_w, screen_height / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        
        # Resize image
        img_resized = cv2.resize(img, (new_w, new_h))
        
        # Create black background
        background = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)
        
        # Calculate position to center image
        y_offset = (screen_height - new_h) // 2
        x_offset = (screen_width - new_w) // 2
        
        # Place image on background
        background[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = img_resized
        
        # Display image
        cv2.imshow(window_name, background)
        print(f"Successfully displayed: {os.path.basename(image_path)}")
        return True
    except Exception as e:
        print(f"Error displaying image {image_path}: {e}")
        return False

# Display first image
current_index = 0
first_display = display_image(image_files[current_index])
if not first_display:
    print("Failed to display first image, exiting.")
    handle_exit(None, None)

print("Starting image viewer. Press 'q' to exit.")

# Main loop
last_update = time.time()
while True:
    # Check for key press (wait 20ms)
    key = cv2.waitKey(20) & 0xFF  # Use & 0xFF for compatibility
    if key == ord('q') or key == 27:  # 'q' or ESC to quit
        break
    
    try:
        # Handle Arduino input (if connected)
        if ser:
            line = ser.readline().decode('utf-8').strip()
            if line:
                try:
                    val = int(line)
                    index = get_image_index(val)
                    if index != current_index:
                        if display_image(image_files[index]):
                            current_index = index
                except ValueError:
                    print(f"Received non-integer value: {line}")
        # Auto-advance in test mode
        elif time.time() - last_update > display_time:
            next_index = (current_index + 1) % image_count
            if display_image(image_files[next_index]):
                current_index = next_index
                last_update = time.time()
    except Exception as e:
        print(f"Error in main loop: {e}")

# Ensure clean exit
handle_exit(None, None) 