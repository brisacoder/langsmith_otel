import os

from openai import OpenAI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, sampling
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from dotenv import load_dotenv


load_dotenv(override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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


def call_openai():
    model = "gpt-4o-mini"
    with tracer.start_as_current_span("call_open_ai") as span:
        span.set_attribute("langsmith.span.kind", "LLM")
        span.set_attribute("langsmith.metadata.user_id", "user_123")
        span.set_attribute("gen_ai.system", "OpenAI")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("llm.request.type", "chat")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "Write a haiku about recursion in programming.",
            },
        ]

        for i, message in enumerate(messages):
            span.set_attribute(f"gen_ai.prompt.{i}.content", str(message["content"]))
            span.set_attribute(f"gen_ai.prompt.{i}.role", str(message["role"]))

        completion = client.chat.completions.create(model=model, messages=messages)

        span.set_attribute("gen_ai.response.model", completion.model)
        span.set_attribute(
            "gen_ai.completion.0.content", str(completion.choices[0].message.content)
        )
        span.set_attribute("gen_ai.completion.0.role", "assistant")
        span.set_attribute("gen_ai.usage.prompt_tokens", completion.usage.prompt_tokens)
        span.set_attribute(
            "gen_ai.usage.completion_tokens", completion.usage.completion_tokens
        )
        span.set_attribute("gen_ai.usage.total_tokens", completion.usage.total_tokens)
        return completion.choices[0].message


if __name__ == "__main__":
    call_openai()
