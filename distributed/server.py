import os
import logging
import uvicorn
from fastapi import FastAPI, Request

os.environ["OTEL_LOG_LEVEL"] = "DEBUG"

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.propagate import extract

# SDK-specific imports (not just the API)
from opentelemetry.sdk.trace import TracerProvider, sampling
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Example OTLP exporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from dotenv import load_dotenv

from openai import OpenAI

load_dotenv(override=True)

logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
logging.getLogger("opentelemetry.sdk").setLevel(logging.DEBUG)
logging.getLogger("opentelemetry.exporter").setLevel(logging.DEBUG)

print(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
print(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 1. Create a FastAPI app
app = FastAPI()

provider = TracerProvider(sampler=sampling.ALWAYS_ON)

otlp_exporter = OTLPSpanExporter(
    timeout=10,
)

# 4. Add a BatchSpanProcessor to the provider
span_processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(span_processor)

trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


async def call_openai(otel_ctx):
    with tracer.start_as_current_span("server_call_open_ai", context=otel_ctx) as child_span:
        child_span.set_attribute("langsmith.span.kind", "LLM")
        child_span.set_attribute("langsmith.metadata.user_id", "nolan")
        child_span.set_attribute("gen_ai.system", "OpenAI")
        child_span.set_attribute("gen_ai.request.model", os.getenv("OPENAI_MODEL_NAME"))
        child_span.set_attribute("llm.request.type", "chat")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "Write a haiku about recursion in programming.",
            },
        ]

        for i, message in enumerate(messages):
            child_span.set_attribute(f"gen_ai.prompt.{i}.content", str(message["content"]))
            child_span.set_attribute(f"gen_ai.prompt.{i}.role", str(message["role"]))

        completion = client.chat.completions.create(model=os.getenv("OPENAI_MODEL_NAME"), messages=messages)

        child_span.set_attribute("gen_ai.response.model", completion.model)
        child_span.set_attribute(
            "gen_ai.completion.0.content", str(completion.choices[0].message.content)
        )
        child_span.set_attribute("gen_ai.completion.0.role", "assistant")
        child_span.set_attribute("gen_ai.usage.prompt_tokens", completion.usage.prompt_tokens)
        child_span.set_attribute(
            "gen_ai.usage.completion_tokens", completion.usage.completion_tokens
        )
        child_span.set_attribute("gen_ai.usage.total_tokens", completion.usage.total_tokens)

        span_context = child_span.get_span_context()
        root_span_id = format(span_context.span_id, '016x')
        root_trace_id = format(span_context.trace_id, '032x')

        child_span.add_event(
            "otel",
            attributes={
                "root_span_id": root_span_id,
                "root_trace_id": root_trace_id,
            }
        )

        return completion.choices[0].message


@app.post("/stuff")
async def handle_stuff(request: Request):
    """
    This endpoint receives an incoming request, extracts the OTEL context from the headers,
    and starts a child span under the caller's trace.
    """
    # Extract the OTEL context from incoming request headers
    otel_ctx = extract(request.headers)

    response = await call_openai(otel_ctx)
    return {"message": response}


if __name__ == "__main__":
    # Run the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8123, log_level="debug")
