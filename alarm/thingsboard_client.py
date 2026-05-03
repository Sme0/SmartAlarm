"""MQTT client wrapper for optional ThingsBoard telemetry uploads."""

import json
import time
import logging

from dotenv import load_dotenv
import os
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)
load_dotenv()

class ThingsBoardClient:
    """Publish telemetry to ThingsBoard when enabled via environment variables."""

    def __init__(self, host=None, token=None):
        # Check if ThingsBoard is enabled
        self.enabled = str(os.getenv("THINGSBOARD_ENABLED", "False")).lower() in ["true", "y", "yes"]

        self.client = None
        self.host = host or os.getenv("THINGSBOARD_HOST")
        self.access_token = token or os.getenv("THINGSBOARD_ACCESS_TOKEN")

        # Only initialize MQTT client if enabled
        if self.enabled:
            self.client = mqtt.Client()
        else:
            logger.info("Disabled via THINGSBOARD_ENABLED=False")

    def _on_connect(self, client, userdata, flags, rc, *extra_params):
        """
        Called after the client attempts to connect to the MQTT broker.
        rc (result code) = 0 means a successful connection.
        """
        logger.debug('Connected with result code ' + str(rc))

    def _on_publish(self, client, userdata, result):
        """
        Called whenever a message is successfully published to the MQTT broker.
        Prints to confirm the publish event, helping verify
        that data actually reached the server.
        """
        logger.debug("Published to MQTT broker")

    def _on_message(self, client, userdata, msg):
        logger.debug("Payload: " + str(msg.payload))
        data = json.loads(msg.payload)


    def connect(self):
        """Connect to the MQTT broker and start the background loop."""
        # Skip if ThingsBoard is disabled
        if not self.enabled:
            return

        self.client.username_pw_set(self.access_token)
        self.client.on_connect = self._on_connect
        self.client.on_publish = self._on_publish
        self.client.on_message = self._on_message

        self.client.subscribe('v1/devices/me/attributes')
        self.client.subscribe('v1/devices/me/rpc/request/+')

        self.client.connect(self.host, 1883, 60)
        self.client.loop_start()

    def disconnect(self):
        """Disconnect from the broker and stop the background loop."""
        # Skip if ThingsBoard is disabled
        if not self.enabled or not self.client:
            return

        self.client.loop_stop()
        self.client.disconnect()

    def post(self, data: dict):
        """Publish telemetry data to ThingsBoard."""
        # Skip if ThingsBoard is disabled
        if not self.enabled or not self.client:
            return

        self.client.publish('v1/devices/me/telemetry', json.dumps(data), qos=1)

    def request_shared_attributes(self, keys: list):
        """Request shared attribute values for the given keys."""
        # Skip if ThingsBoard is disabled
        if not self.enabled or not self.client:
            return

        payload = {"sharedKeys": ",".join(keys)}
        self.client.publish(
            'v1/devices/me/attributes/request/1',
            json.dumps(payload),
            qos=1
        )