from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import os

load_dotenv()

class ThingsBoardClient:
    def __init__(self, host=None, token=None):
        self.client = mqtt.Client()
        self.host = host or os.getenv("THINGSBOARD_HOST")
        self.access_token = token or os.getenv("THINGSBOARD_ACCESS_TOKEN")

    def _on_connect(client, userdata, flags, rc, *extra_params):
        """
        Called after the client attempts to connect to the MQTT broker.
        rc (result code) = 0 means a successful connection.
        This is a good place to log or print a message indicating the connection status.
        """
        print('Connected with result code ' + str(rc))

    def _on_publish(client, userdata, result):
        """
        Called whenever a message is successfully published to the MQTT broker.
        Prints 'Success' to confirm the publish event, helping you verify
        that data actually reached the server.
        """
        print("Published to MQTT broker")

    def connect(self):
        self.client.username_pw_set(self.access_token)
        self.client.on_connect = self._on_connect
        self.client.on_publish = self._on_publish
        #TODO: self.client.on_message =

        #TODO: self.client.subscribe('')
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()





