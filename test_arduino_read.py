import serial
import time

try:
    # Open serial port
    ser = serial.Serial('/dev/tty.usbmodem11201', 9600, timeout=1, exclusive=True)
    print(f"Connected to Arduino on {ser.port}")
    
    # Clear any initial data
    ser.reset_input_buffer()
    
    print("Listening for data for 30 seconds...")
    start_time = time.time()
    data_count = 0
    
    # Listen for data for 30 seconds
    while time.time() - start_time < 30:
        # Read a line
        raw_data = ser.readline()
        
        # If we got data, print it
        if raw_data:
            data_count += 1
            data_str = raw_data.decode('utf-8', errors='replace').strip()
            print(f"Data [{data_count}]: '{data_str}'")
        
        # Small delay
        time.sleep(0.1)
    
    print(f"Done. Received {data_count} data points in 30 seconds.")
    ser.close()
    
except Exception as e:
    print(f"Error: {e}") 