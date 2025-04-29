import serial
import time

port = '/dev/tty.usbmodem1201'  # Change to your port
baud = 1200

ser = serial.Serial(port, baud)
ser.close()
time.sleep(1)  # Give it a moment to reset