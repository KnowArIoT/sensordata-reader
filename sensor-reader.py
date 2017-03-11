#!/usr/bin/env python3

import time
import serial
import requests
import re
import json
import datetime
from slackclient import SlackClient

from os import environ, remove
from concurrent.futures import ThreadPoolExecutor
from camera import capture
from s3 import upload

SEND_TIME_INTERVAL = 0.9
SERIAL_DEVICE = "/dev/ttyACM0"
S3_BUCKET_NAME = "ariot-bucket"
IMAGES_URL = "https://s3-eu-west-1.amazonaws.com/{}".format(S3_BUCKET_NAME)

SLACK_API_TOKEN = environ["SLACK_API_TOKEN"]

SAMPLE_BUFFER_SIZE = 2
CAMERA_TRIGGER_SLEEP = 1.0 # seconds
CAMERA_TRIGGER_SENSITIFITY = 0.1

API_USER, API_PASS = environ["API_USER"], environ["API_PASS"]
DATA_ENDPOINT = environ["API_URL"]
SENSORDATA_ENDPOINT = "{}/save".format(DATA_ENDPOINT)
IMAGE_META_ENDPOINT = "{}/s3".format(DATA_ENDPOINT)

SLACK_CHANNEL = "#knowiot-pi3bot"

API_SUPPORTED_SENSORS = [
'u1',
'u2',
'gas',
'mag',
'accl',
'gyro',
#"gpsTime",
#"gpsDate",
#"gpsFix",
#"gpsSignalQuality",
"gpsLatLong",
]

sensor_data_buffer = []
last_send_time = time.time()
last_gps_lat_long = None

def current_time():
    t = time.time()
    millisecs = int((t - last_send_time) * 1000)
    date = datetime.datetime.fromtimestamp(int(t)).strftime('%Y-%m-%d %H:%M:%S')
    return date, millisecs

def send_sensor_packet_buffered():
    global last_send_time

    data = get_sensor_data()
    print("sending {} data points".format(len(data)))

    print("post to {}".format("{}".format(SENSORDATA_ENDPOINT)))
    print(data[:3])
    print("last gps latlong: {}".format(last_gps_lat_long))
    resp = requests.post(SENSORDATA_ENDPOINT, json=data, auth=(API_USER, API_PASS))

    last_send_time = time.time()
    #return

    print(resp.status_code)
    if resp.status_code != 200:
        print("Failed post sensor data")

def send_image_meta(image_file_name, date, millisecs):
    data = {
        "url": "{}/{}".format(IMAGES_URL, image_file_name),
        "latlong": last_gps_lat_long,
        "time": date,
        "miliseconds": millisecs
    }

    from json import dumps
    print("sending image meta: {}".format(dumps(data)))
    response = requests.post(IMAGE_META_ENDPOINT, data=data, auth=(API_USER, API_PASS))

    if response.status_code != 200:
        print("Failed to send image meta ({})".format(response.status_code))

def put_sensor_data(data):
    global sensor_data_buffer
    sensor_data_buffer += [data]

def get_sensor_data():
    global sensor_data_buffer
    ret = sensor_data_buffer

    sensor_data_buffer = []

    return ret

def store_data(sensor_name, sensor_data, date, millisecs):
    if time.time() - last_send_time >= SEND_TIME_INTERVAL:
        send_sensor_packet_buffered()

    sensor_packet = {
        "name": sensor_name,
        "data": sensor_data,
        "time": date,
        "milliseconds": millisecs
    }

    put_sensor_data(sensor_packet)

def capture_and_upload_image():
    imgpath = capture()
    dest_path = upload(S3_BUCKET_NAME, imgpath)
    remove(imgpath)
    return dest_path

class FixedFIFO:
    def __init__(self, size):
        self._size = size
        self._buffer = []

    def push(self, data):
        self._buffer += [data]
        if len(self._buffer) > self._size:
            self._buffer.pop(0)

    def avg(self):
        return sum(self._buffer) / len(self._buffer)

sample_buffer = FixedFIFO(SAMPLE_BUFFER_SIZE)
last_sample_avg = 1
last_trigger_time = time.time()

sample_count = 0
def process_sensordata(name, data, date, millisecs):
    global last_trigger_time

    if name not in ["u1"]:
        return

    global sample_count
    global sample_buffer
    global last_sample_avg

    sample_buffer.push(float(data))
    avg = sample_buffer.avg()

    diff = abs(avg - last_sample_avg)

    sample_count += 1
    if sample_count % 50 == 0:
        print("{}: {} {} {}".format(name, float(data), avg, diff))

    last_sample_avg = avg

    if diff < CAMERA_TRIGGER_SENSITIFITY or time.time() - last_trigger_time < CAMERA_TRIGGER_SLEEP:
        return None

    last_trigger_time = time.time()
    img = capture_and_upload_image()

    print("triggered camera ({})".format(diff))
    send_image_meta(img, date, millisecs)

def decode_line(line):
    try:
        line = line.decode("utf-8").rstrip()
        idx = line.find(":")
        if idx < 0:
            return None
        name, data = line[:idx], line[idx + 1:].strip()

        if name not in API_SUPPORTED_SENSORS or len(data) == 0:
            return None

        #if name in ["u1", "u2"]:
            #print("{}: {}".format(name, data))

        global last_gps_lat_long
        if name == "gpsLatLong":
            last_gps_lat_long = data
            name = "gps"

        date, millis = current_time()
        return name, data.strip(), date, millis
    except UnicodeDecodeError:
        return None

def slack_post_msg(msg, sc):
    return sc.api_call("chat.postMessage", channel=SLACK_CHANNEL, text=msg)
   
bot_start_time = time.time()
def parse_message(event, sc):
    if "content" not in event.keys():
        return

    message = event["content"]
    if "@knowiotrpi3 snap" not in message:
        return

    if "event_ts" not in event or float(event["event_ts"]) < bot_start_time:
        print("event is too old!")
        return

    img_name = capture_and_upload_image()
    gmaps_link = "https://www.google.no/maps/dir/{}".format(last_gps_lat_long)
    imgurl = "{} - {}/{}".format(gmaps_link, IMAGES_URL, img_name)
    slack_post_msg(imgurl, sc)

def slack_test():
    sc = SlackClient(SLACK_API_TOKEN)
    
    ret = sc.api_call("channels.list", channel=SLACK_CHANNEL)
    ret = sc.api_call("channels.join", channel=SLACK_CHANNEL)

    slack_post_msg("hello", sc)

    if not sc.rtm_connect():
        print("Connection Failed, invalid token?")

    while True:
        events = sc.rtm_read()
        print(events)
        for event in events:
            parse_message(event, sc)
        time.sleep(1)

def main():
    global last_send_time
    ThreadPoolExecutor(max_workers=1).submit(slack_test)

    th = ThreadPoolExecutor(max_workers=1)

    with serial.Serial(SERIAL_DEVICE, 115200) as ser:
        last_send_time = time.time()
        while True:
            data = decode_line(ser.readline())
            if not data:
                continue

            process_sensordata(*data)
            #th.submit(process_sensordata, *data)
            store_data(*data)

if __name__ == "__main__":
    #print(capture_and_upload_image())
    main()
