#!/usr/bin/env python3

import time
import serial
import requests
import re
from os import environ

DATA_ENDPOINT = environ["API_URL"]
SEND_TIME_INTERVAL = 0.9
SERIAL_DEVICE = "/dev/ttyACM0"

sensor_data_buffer = []
last_send_time = time.time()

def current_milli_time():
    return int((time.time() - last_send_time) * 1000)

def send_sensor_packet_buffered():
    global last_send_time

    data = get_sensor_data()
    print("sending {} data points".format(len(data)))

    resp = requests.post(DATA_ENDPOINT, get_sensor_data())
    last_send_time = time.time()

    if resp.status_code != 200:
        print("Failed post sensor data")

def put_sensor_data(data):
    global sensor_data_buffer
    sensor_data_buffer += [data]

def get_sensor_data():
    global sensor_data_buffer
    ret = sensor_data_buffer

    sensor_data_buffer = []

    return ret

def is_float(num):
    if re.match("^\d+?\.\d+?$", num) is None:
        return False
    return True

def store_data(data):
    if time.time() - last_send_time >= SEND_TIME_INTERVAL:
        send_sensor_packet_buffered()

    data = data.split(":")
    if len(data) != 2 or data[0] == "":
        return

    sensor_name, sensor_data = data

    if not is_float(sensor_data):
        return

    sensor_packet = {
        "name": sensor_name,
        "data": sensor_data,
        "time": current_milli_time()
    }

    put_sensor_data(sensor_packet)

def decode_line(line):
    try:
        return line.decode("utf-8").rstrip()
    except UnicodeDecodeError:
        return None

def main():
    global last_send_time
    with serial.Serial(SERIAL_DEVICE) as ser:
        last_send_time = time.time()
        while True:
            line = decode_line(ser.readline())
            if not line:
                continue

            store_data(line)

if __name__ == "__main__":
    main()
