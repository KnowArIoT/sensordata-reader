# sensordata-reader
Reads sensordata and forwards it to an API

## Goal
Read sensordata from over a serial connection and forward it to an external REST API

## Protocol
Assumes the serial connection follows a plain-text protocol:
```
<sensor name>:<sensor data>\n
```
where `sensor name` is the name of the sensor. `sensor data` is the floating point data, followed by a newline.
The serial stream might look like this:
```
u1:15.0
u2:10.4
u2:10.4
gas:10.4
temp:10.4
temp:10.4
gas:10.4
u1:10.4
u2:10.4
```

## How to run
```
$ export API_URL=http://api-url
$ pip3 install -r requirements.txt$ 
$ ./sensor-reader.py

```
