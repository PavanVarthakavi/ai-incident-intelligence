import os

# Never export telemetry from tests.
os.environ["OTEL_SDK_DISABLED"] = "true"
