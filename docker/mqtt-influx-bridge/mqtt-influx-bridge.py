#!/usr/bin/python

import re
import os
from typing import NamedTuple
import time

import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient

# INFLUXDB_ADDRESS = '127.0.0.1'
INFLUXDB_ADDRESS = 'influxdb'  # hostname of the docker container
INFLUXDB_PORT = int(os.environ['INFLUXDB_PORT'])
INFLUXDB_USER = os.environ['INFLUXDB_USER']
INFLUXDB_USER_PASSWORD = os.environ['INFLUXDB_USER_PASSWORD']
INFLUXDB_DATABASE = os.environ['INFLUXDB_DATABASE']

# MQTT_ADDRESS = '127.0.0.1'
MQTT_ADDRESS = os.environ['MQTT_ADDRESS']  # hostname of the docker container
MQTT_PORT = int(os.environ['MQTT_PORT'])
MQTT_USER = os.environ['MQTT_USER']
MQTT_PASSWORD = os.environ['MQTT_PASSWORD']
MQTT_TOPIC = 'home/+/+'
MQTT_REGEX = 'home/([^/]+)/([^/]+)'
MQTT_TASMOTA_TOPIC_STATE_REGEX = 'tasmota/([^/]+)/STATE'
MQTT_TASMOTA_TOPIC_SENSOR_REGEX = 'tasmota/([^/]+)/SENSOR'
MQTT_CLIENT_ID = 'MQTTInfluxDBBridge'

influxdb_client = InfluxDBClient(INFLUXDB_ADDRESS, INFLUXDB_PORT, INFLUXDB_USER, INFLUXDB_USER_PASSWORD, None)

class SensorData(NamedTuple):
    location: str
    measurement: str
    value: float

def on_connect(client, userdata, flags, rc):
    """ The callback for when the client receives a CONN ACK response."""
    print('Connected with result code ' + str(rc))
    client.subscribe(MQTT_TOPIC)

def parse_mqtt_message(topic, payload):
    match = re.match(MQTT_REGEX, topic)
    if match:
        location = match.group(1)
        measurement = match.group(2)
        if measurement == 'status':
            return None
        return SensorData(location, measurement, float(payload))
    else:
        return None

def send_sensor_data_to_influxdb(sensor_data):
    json_body = [
        {
            'measurement': sensor_data.measurement,
            'tags': {
                'location': sensor_data.location
            },
            'fields': {
                'value': sensor_data.value
            }
        }
    ]
    influxdb_client.write_points(json_body)

def on_message(client, userdata, msg):
    """The callback for when a PUBLISH message is received from the server."""
    print(msg.topic + ' ' + str(msg.payload))
    sensor_data = parse_mqtt_message(msg.topic, msg.payload.decode('utf-8'))
    if sensor_data is not None:
        send_sensor_data_to_influxdb(sensor_data)

def init_influxdb_database():
    databases = influxdb_client.get_list_database()
    if len(list(filter(lambda x: x['name'] == INFLUXDB_DATABASE, databases))) == 0:
        influxdb_client.create_database(INFLUXDB_DATABASE)
    influxdb_client.switch_database(INFLUXDB_DATABASE)

def main():
    
    while True:
        try:
            print('Starting MQTT to InfluxDB bridge.')
            init_influxdb_database()

            mqtt_client = mqtt.Client(MQTT_CLIENT_ID)
            mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
            mqtt_client.on_connect = on_connect
            mqtt_client.on_message = on_message

            mqtt_client.connect(MQTT_ADDRESS, MQTT_PORT)
            mqtt_client.loop_forever()
        except Exception as error:
            print("MQTT to InfluxDB bridge threw error: {}\nRestarting in 60 seconds.".format(error))
            try:
                mqtt_client.disconnect()
            except:
                pass
            try:
                influxdb_client.close()
            except:
                pass
            time.sleep(5.0)
            print('Restarting MQTT to InfluxDB bridge.')


if __name__ == '__main__':
    main()