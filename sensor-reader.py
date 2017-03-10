#!/usr/bin/env python3

import time
import serial
import requests
import re
import math
from os import environ, remove
import json

#from camera import capture
from s3 import upload

DATA_ENDPOINT = environ["API_URL"]
SEND_TIME_INTERVAL = 0.9
SERIAL_DEVICE = "/dev/ttyACM0"
S3_BUCKET_NAME = "ariot-bucket"

sensor_data_buffer = []
last_send_time = time.time()

def current_milli_time():
    return int((time.time() - last_send_time) * 1000)

def send_sensor_packet_buffered():
    global last_send_time

    data = get_sensor_data()
    print("sending {} data points".format(len(data)))

    print("post to {}".format(DATA_ENDPOINT))
    resp = requests.post(DATA_ENDPOINT, json=data)
    last_send_time = time.time()

    print(resp.status_code)
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

def store_data(sensor_name, sensor_data, millisecs):
    if time.time() - last_send_time >= SEND_TIME_INTERVAL:
        send_sensor_packet_buffered()

    if not is_float(sensor_data):
        return

    sensor_packet = {
        "name": sensor_name,
        "data": sensor_data,
        "time": millisecs
    }

    put_sensor_data(sensor_packet)

def capture_and_upload_image():
    imgpath = capture()
    upload(S3_BUCKET_NAME, imgpath)
    remove(imgpath)
    return imgpath

def decode_line(line):
    try:
        line = line.decode("utf-8").rstrip().split(":")
        if len(line) != 2 or line[0] == "":
            return None

        name, data = line
        return name, data, current_milli_time()
    except UnicodeDecodeError:
        return None

last_10 = []
last_avg = 0
def process_sensordata(name, data, millisecs): # {
    if name != "u1":
        return

    last_10 += [data]
    last_10.pop(0)

    avg = sum(last_10) / len(last_10)

    global last_avg
    if math.abs(avg - last_avg) < 5:
        return None

    last_avg = avg
    return capture_and_upload_image()
# }

def main():
    global last_send_time
    #th = ThreadPoolExecutor(max_workers=1)

    with serial.Serial(SERIAL_DEVICE) as ser:
        last_send_time = time.time()
        while True:
            data = decode_line(ser.readline())
            if not data:
                continue
            store_data(*data)

            #th.submit(process_sensordata, *data)
            #th.submit(store_data, *data)

if __name__ == "__main__":
    #print(capture_and_upload_image())
    main()
