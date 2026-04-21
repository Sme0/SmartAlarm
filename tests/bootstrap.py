import os
import sys
import types
from datetime import timezone


def configure_test_environment():
    """Configure app imports for lightweight unit tests."""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["SECRET_KEY"] = "test-secret-key"


def stub_optional_ml_dependencies():
    """Avoid requiring the ML packages for tests that do not exercise ML code."""
    if "joblib" not in sys.modules:
        joblib = types.ModuleType("joblib")
        joblib.dump = lambda *args, **kwargs: None
        joblib.load = lambda *args, **kwargs: None
        sys.modules["joblib"] = joblib

    if "numpy" not in sys.modules:
        numpy = types.ModuleType("numpy")
        numpy.array = lambda values, *args, **kwargs: values
        sys.modules["numpy"] = numpy

    if "sklearn" not in sys.modules:
        sys.modules["sklearn"] = types.ModuleType("sklearn")

    pipeline = types.ModuleType("sklearn.pipeline")
    pipeline.Pipeline = _FakePipeline
    sys.modules.setdefault("sklearn.pipeline", pipeline)

    ensemble = types.ModuleType("sklearn.ensemble")
    ensemble.RandomForestRegressor = _FakeEstimator
    sys.modules.setdefault("sklearn.ensemble", ensemble)

    preprocessing = types.ModuleType("sklearn.preprocessing")
    preprocessing.StandardScaler = _FakeEstimator
    sys.modules.setdefault("sklearn.preprocessing", preprocessing)


class _FakePipeline:
    def __init__(self, steps=None):
        self.steps = steps or []

    def fit(self, *args, **kwargs):
        return self

    def predict(self, rows):
        return [0 for _ in rows]


class _FakeEstimator:
    def __init__(self, *args, **kwargs):
        pass


def stub_optional_device_dependencies():
    """Avoid requiring device-only packages for tests."""
    if "pytz" not in sys.modules:
        pytz = types.ModuleType("pytz")
        pytz.UnknownTimeZoneError = ValueError
        pytz.timezone = lambda name: timezone.utc
        sys.modules["pytz"] = pytz

    if "mathgenerator" not in sys.modules:
        mathgenerator = types.ModuleType("mathgenerator")
        mathgenerator.mathgen = lambda *args, **kwargs: ("2 + 2", 4)
        sys.modules["mathgenerator"] = mathgenerator

// Stub out serial and MQTT dependencies to avoid requiring hardware or network access for tests.
    if "serial" not in sys.modules:
        serial = types.ModuleType("serial")

        class _SerialException(Exception):
            pass

        class _Serial:
            def __init__(self, *args, **kwargs):
                self.buffer = []

            def write(self, data):
                self.buffer.append(data)

            def read(self, *args, **kwargs):
                return b""

        serial.SerialException = _SerialException
        serial.Serial = _Serial
        sys.modules["serial"] = serial

    if "paho" not in sys.modules:
        sys.modules["paho"] = types.ModuleType("paho")

    if "paho.mqtt" not in sys.modules:
        sys.modules["paho.mqtt"] = types.ModuleType("paho.mqtt")

    if "paho.mqtt.client" not in sys.modules:
        mqtt_client = types.ModuleType("paho.mqtt.client")

        class _MqttClient:
            def username_pw_set(self, *args, **kwargs):
                return None

            def subscribe(self, *args, **kwargs):
                return None

            def connect(self, *args, **kwargs):
                return 0

            def loop_start(self):
                return None

            def loop_stop(self):
                return None

            def disconnect(self):
                return None

            def publish(self, *args, **kwargs):
                return None

        mqtt_client.Client = _MqttClient
        sys.modules["paho.mqtt.client"] = mqtt_client
