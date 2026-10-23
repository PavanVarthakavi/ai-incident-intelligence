"""Fixed thresholds used to flag notable behaviour in summaries.

These are simple SLO-style markers so summaries can say *when* something became
abnormal. They are not anomaly detection and do not decide what is evidence:
all collected data is returned regardless.
"""

ERROR_RATIO = 0.05  # 5% of requests returning 5xx
P95_LATENCY_S = 1.0  # p95 request latency
SLOW_TRACE_MS = int(P95_LATENCY_S * 1000)
