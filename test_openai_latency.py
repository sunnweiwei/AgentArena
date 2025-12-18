#!/usr/bin/env python3
"""Measure Responses API latency for a streaming request."""
from __future__ import annotations

import argparse
import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DEFAULT_PROMPT = "intro elon musk in a table"
DEFAULT_MODEL = "gpt-5-nano"


@dataclass
class LatencySample:
    prompt: str
    model: str
    time_to_first_ms: float
    total_ms: float
    chunk_count: int


def load_api_key() -> str:
    # Try .env first
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        return api_key
    
    # Fallback to openaikey file for backward compatibility
    key_path = Path(__file__).parent / "openaikey"
    if key_path.exists():
        return key_path.read_text().strip()
    
    raise FileNotFoundError(
        f"Missing OpenAI API key. Set OPENAI_API_KEY in .env file or create 'openaikey' file at {key_path}"
    )


def measure_latency(client: OpenAI, prompt: str, model: str) -> LatencySample:
    start = time.perf_counter()
    first_chunk_time: Optional[float] = None
    chunk_count = 0
    
    stream = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        stream=True,
    )
    
    for event in stream:
        event_type = getattr(event, "type", "")
        if event_type == "response.output_text.delta":
            if first_chunk_time is None:
                first_chunk_time = time.perf_counter()
            chunk_count += 1

    end = time.perf_counter()
                if first_chunk_time is None:
        raise RuntimeError("Did not receive any output_text.delta events")

    return LatencySample(
        prompt=prompt,
        model=model,
        time_to_first_ms=(first_chunk_time - start) * 1000,
        total_ms=(end - start) * 1000,
        chunk_count=chunk_count,
    )


def run_trials(
    prompt: str,
    model: str,
    trials: int,
    delay: float,
) -> List[LatencySample]:
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)
    results: List[LatencySample] = []

    for i in range(trials):
        print(f"Trial {i+1}/{trials}…", flush=True)
        sample = measure_latency(client, prompt, model)
        print(
            f"  Time to first token: {sample.time_to_first_ms:.2f} ms | "
            f"Total time: {sample.total_ms:.2f} ms | "
            f"Chunks: {sample.chunk_count}"
        )
        results.append(sample)
        if i < trials - 1 and delay > 0:
            time.sleep(delay)

    return results


def summarize(samples: List[LatencySample]) -> None:
    if not samples:
        print("No samples collected.")
        return

    first_latencies = [s.time_to_first_ms for s in samples]
    totals = [s.total_ms for s in samples]

    def fmt_stats(values: List[float]) -> str:
        if len(values) == 1:
            return f"{values[0]:.2f} ms"
        return (
            f"avg {statistics.mean(values):.2f} ms | "
            f"min {min(values):.2f} ms | "
            f"max {max(values):.2f} ms"
        )

    print("\n=== Latency Summary ===")
    print(f"Prompt: {samples[0].prompt!r}")
    print(f"Model:  {samples[0].model}")
    print(f"Trials: {len(samples)}")
    print(f"Time to first token: {fmt_stats(first_latencies)}")
    print(f"Total response time: {fmt_stats(totals)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure OpenAI Responses streaming latency."
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help=f"Prompt to send to the model (default: {DEFAULT_PROMPT!r})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name to test (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=3,
        help="Number of trials to run (default: 3)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between trials (default: 1s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    samples = run_trials(
        prompt=args.prompt,
        model=args.model,
        trials=max(1, args.trials),
        delay=max(0.0, args.delay),
    )
    summarize(samples)


if __name__ == "__main__":
    main()

