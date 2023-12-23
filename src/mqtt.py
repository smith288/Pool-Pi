# python 3.6

import json
import logging
import random
import time

from paho.mqtt import client as mqtt_client

BROKER = 'homebridge'
PORT = 1883
TOPIC = "poolpi"
# generate client ID with pub prefix randomly
CLIENT_ID = f'python-mqtt-tcp-pub-sub-{random.randint(0, 1000)}'

FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60

FLAG_EXIT = False

class MQTTClient:
    def __init__(self, callback=None):
        self.callback = callback
        self.client = mqtt_client.Client(CLIENT_ID)
        self.last_publish_time = time.time()
    
    def on_connect(self, client, userdata, flags, rc):
        print(f'Connected with result code {rc}')
        if rc == 0 and client.is_connected():
            print("Connected to MQTT Broker!")
            client.subscribe(f"{TOPIC}/#")
        else:
            print(f'Failed to connect, return code {rc}')

    def on_disconnect(client, userdata, rc):
        logging.info("Disconnected with result code: %s", rc)
        reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
        while reconnect_count < MAX_RECONNECT_COUNT:
            logging.info("Reconnecting in %d seconds...", reconnect_delay)
            time.sleep(reconnect_delay)

            try:
                client.reconnect()
                logging.info("Reconnected successfully!")
                return
            except Exception as err:
                logging.error("%s. Reconnect failed. Retrying...", err)

            reconnect_delay *= RECONNECT_RATE
            reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
            reconnect_count += 1
        logging.info("Reconnect failed after %s attempts. Exiting...", reconnect_count)
        global FLAG_EXIT
        FLAG_EXIT = True


    def on_message(self, client, userdata, msg):
        # emit this back out to the class caller
        if self.callback:
            if msg.topic == f"{TOPIC}/command":
                print(f'Received `{msg.payload}` from `{msg.topic}` topic')
                self.callback(TOPIC + "/command", msg.payload.decode())
                #Wait 5 seconds then respond with current state

    def connect_mqtt(self):
        self.client = mqtt_client.Client(CLIENT_ID)
        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.connect(BROKER, PORT, keepalive=120)
        self.client.on_disconnect = self.on_disconnect
        
    def publish(self, msg):
        
        if not self.client.is_connected():
            logging.error("publish: MQTT client is not connected!")
            return

        result = self.client.publish(TOPIC, msg)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            logging.debug(f'Send msg to topic `{TOPIC}`')
        else:
            print(f'Failed to send message to topic {TOPIC}')

    def run(self):
        logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s',
                            level=logging.CRITICAL)
        self.connect_mqtt()  # Call the connect_mqtt function from the MQTTClient class
        self.client.loop_start()