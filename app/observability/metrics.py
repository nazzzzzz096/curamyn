import os
from prometheus_client import Counter, Histogram

# ---------------------------------------
# Disable metrics completely in tests
# ---------------------------------------
if os.getenv("CURAMYN_ENV") == "test":

    class DummyMetric:
        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

    # ---- STT ----
    STT_REQUEST_LATENCY = DummyMetric()
    STT_REQUESTS_TOTAL = DummyMetric()
    STT_ERRORS_TOTAL = DummyMetric()
    STT_FALLBACKS_TOTAL = DummyMetric()

    # ---- TTS ----
    TTS_REQUEST_LATENCY = DummyMetric()
    TTS_REQUESTS_TOTAL = DummyMetric()
    TTS_ERRORS_TOTAL = DummyMetric()

else:
    # ---------------- STT ----------------
    STT_REQUEST_LATENCY = Histogram(
        "stt_request_latency_seconds",
        "Speech-to-text request latency",
        ["engine"],
    )

    STT_REQUESTS_TOTAL = Counter(
        "stt_requests_total",
        "Total STT requests",
        ["engine", "status"],
    )

    STT_ERRORS_TOTAL = Counter(
        "stt_errors_total",
        "Total STT errors",
        ["engine", "error_type"],
    )

    STT_FALLBACKS_TOTAL = Counter(
        "stt_fallbacks_total",
        "Total STT fallbacks",
        ["from_engine", "to_engine"],
    )

    # ---------------- TTS ----------------
    TTS_REQUEST_LATENCY = Histogram(
        "tts_request_latency_seconds",
        "Text-to-speech request latency",
        ["engine", "source"],
    )

    TTS_REQUESTS_TOTAL = Counter(
        "tts_requests_total",
        "Total TTS requests",
        ["engine", "status", "source"],
    )

    TTS_ERRORS_TOTAL = Counter(
        "tts_errors_total",
        "Total TTS errors",
        ["engine", "error_type"],
    )
