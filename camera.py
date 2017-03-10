#!/usr/bin/env python3

import random
import string
import os
from picamera import PiCamera

camera = PiCamera()

def random_string(n=12):
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(n))

def capture():
    dest_path = "/tmp/{}.jpg".format(random_string())
    camera.capture(dest_path)
    return dest_path

