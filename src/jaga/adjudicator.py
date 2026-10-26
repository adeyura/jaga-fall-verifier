"""Muse Spark adjudicator: a second, independent look at a candidate.

The adjudicator receives the numeric evidence the pipeline measured
(feature traces, the rules stage's phase record) plus, optionally,
images, and returns a structured verdict. It is an experiment with a
pre-registered keep/pivot gate, not a load-bearing assumption: the
rules stage must stand on its own if the gate removes this stage.

Failure discipline (this is what the gate's operability metric counts):
- A transport failure, a timeout, an unparseable reply, or a reply that
  fails schema validation is an UNUSABLE verdict: recorded as such,
  never raised, never silently converted into a benign or a fall.
- The verdict enum includes "uncertain": when the evidence does not
  discriminate, the model must say so. Uncertainty escalates; it is
  never rounded to the nearer answer.

The reasoning schema asks for the strongest case for a fall, the
strongest case for a benign explanation, any data-quality problems,
and the observation that discriminates between the two, before the
verdict. Correlated, anchored reasoning is the known failure mode of a
second stage that reads the first stage's traces; the counterargument
fields exist to make that failure visible in the log.

This module is provider-neutral: the transport is an injected callable
taking an OpenAI-compatible chat request body (dict) and returning the
parsed response (dict). Images are attached by the caller as data
URLs, so what the model saw is exactly what the log records.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

DEFAULT_MODEL = "muse-spark-1.3"

SYSTEM = """You are the verification stage of a fall-event detection system for an elderly person living alone. A first stage (motion analysis, person segmentation, and a rules engine) has flagged a candidate event and measured the evidence below. Your job is to verify or reject the candidate, or to say the evidence cannot decide.

Rules you must follow:
- You are verifying an event, never assessing a person's health. Say nothing about injury, medical condition, or treatment.
- Argue both sides before deciding: state the strongest evidence that this was a fall, the strongest evidence for a benign explanation (sitting down fast, lying down on purpose, crouching, bending), any problems with the data quality, and the single observation that best discriminates between the two explanations.
- If the discriminating observation is missing or ambiguous, your verdict is "uncertain". Do not round uncertainty to the closer answer.
- Answer with exactly one JSON object and no other text, with these fields:
  "for_fall": string, "for_benign": string, "data_quality": string,
  "discriminator": string,
  "verdict": one of "fall", "benign", "uncertain",
  "confidence": a number from 0 to 1.
"""


@dataclass
class Verdict:
    usable: bool
    verdict: str | None = None        # fall | benign | uncertain
    confidence: float | None = None
    for_fall: str = ""
    for_benign: str = ""
    data_quality: str = ""
    discriminator: str = ""
    error: str | None = None
    raw_content: str | None = None
    usage: dict = field(default_factory=dict)


def build_body(traces_text: str, image_data_urls: list[str],
               model: str = DEFAULT_MODEL, max_tokens: int = 6000) -> dict:
    content: list[dict] = [{"type": "text", "text": traces_text}]
    for url in image_data_urls:
        content.append({"type": "image_url",
                        "image_url": {"url": url}})
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": content},
        ],
    }


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_verdict(content: str | None, usage: dict | None = None) -> Verdict:
    if not content:
        return Verdict(False, error="empty or null model content",
                       usage=usage or {})
    m = _JSON_BLOCK.search(content)
    if not m:
        return Verdict(False, error="no JSON object in model output",
                       raw_content=content, usage=usage or {})
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return Verdict(False, error=f"JSON parse failed: {e}",
                       raw_content=content, usage=usage or {})
    verdict = obj.get("verdict")
    if verdict not in ("fall", "benign", "uncertain"):
        return Verdict(False, error=f"invalid verdict value: {verdict!r}",
                       raw_content=content, usage=usage or {})
    conf = obj.get("confidence")
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        return Verdict(False,
                       error=f"invalid confidence value: {conf!r}",
                       raw_content=content, usage=usage or {})
    return Verdict(
        usable=True, verdict=verdict, confidence=float(conf),
        for_fall=str(obj.get("for_fall", "")),
        for_benign=str(obj.get("for_benign", "")),
        data_quality=str(obj.get("data_quality", "")),
        discriminator=str(obj.get("discriminator", "")),
        raw_content=content, usage=usage or {})


def adjudicate(transport, traces_text: str, image_data_urls: list[str],
               model: str = DEFAULT_MODEL,
               max_tokens: int = 6000) -> Verdict:
    """Run one adjudication. Transport errors become unusable verdicts."""
    body = build_body(traces_text, image_data_urls, model, max_tokens)
    try:
        response = transport(body)
    except Exception as e:  # timeouts, HTTP errors, helper failures
        return Verdict(False, error=f"transport failed: {e}")
    choices = response.get("choices") or []
    if not choices:
        return Verdict(False, error="response carried no choices",
                       usage=response.get("usage") or {})
    content = (choices[0].get("message") or {}).get("content")
    return parse_verdict(content, response.get("usage") or {})
