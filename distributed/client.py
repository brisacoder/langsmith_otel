import os
import time
import requests
import logging

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.propagate import inject

# SDK-specific imports
from opentelemetry.sdk.trace import TracerProvider, sampling
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# OTLP exporter (same or different endpoint, depending on your setup)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from dotenv import load_dotenv

load_dotenv(override=True)

# Set all opentelemetry logs to DEBUG
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
logging.getLogger("opentelemetry.sdk").setLevel(logging.DEBUG)
logging.getLogger("opentelemetry.exporter").setLevel(logging.DEBUG)

print(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
print(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))

otlp_exporter = OTLPSpanExporter(
    timeout=10,
)

# Create the SDK TracerProvider
provider = TracerProvider(sampler=sampling.ALWAYS_ON)

# Add a SpanProcessor for exporting
span_processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(span_processor)

# Now set this as the global TracerProvider
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


def main():
    # Start a root span for the client
    with tracer.start_as_current_span("client_root_span", kind=trace.SpanKind.CLIENT) as root_span:

        # root_span.set_attribute("langsmith.span.kind", "LLM")
        # root_span.set_attribute("langsmith.metadata.user_id", "user_123")
        # root_span.set_attribute("gen_ai.system", "OpenAI")
        # root_span.set_attribute("gen_ai.request.model", os.getenv("OPENAI_MODEL_NAME"))
        root_span.set_attribute("llm.request.type", "chat")
        root_span.set_attribute("http.method", "POST")
        root_span.set_attribute("http.url", "http://localhost:8123/stuff")

        # span_context = root_span.get_span_context()
        # root_span_id = format(span_context.span_id, '016x')
        # root_trace_id = format(span_context.trace_id, '032x')

        # root_span.add_event(
        #     "otel",
        #     attributes={
        #         "root_span_id": root_span_id,
        #         "root_trace_id": root_trace_id,
        #     }
        # )

        # We'll inject this current span's context into the headers
        headers = {}
        inject(headers)

        # Make a POST request to the FastAPI server
        response = requests.post(
            "http://localhost:8123/stuff",
            headers=headers,
            json={"data": "hello from client"},
        )
        print("Server response:", response.json())

    span_processor.shutdown()
    time.sleep(1)


if __name__ == "__main__":
    main()
