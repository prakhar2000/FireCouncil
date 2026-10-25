"""One model call per persona. The replay sends them only when BEDROCK_CALLS=1."""

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaCall:
    """The request a persona would send. ``invoke`` is not used by the replay."""

    persona: str
    model_id_env: str
    system: str
    user: str


def invoke(call: PersonaCall) -> str:
    """Send one persona call. Refuses unless BEDROCK_CALLS=1, which the replay never sets."""
    if os.environ.get("BEDROCK_CALLS") != "1":
        raise RuntimeError("Bedrock calls are off")
    model_id = os.environ.get(call.model_id_env, "").strip()
    if not model_id:
        raise RuntimeError(f"{call.model_id_env} is empty")
    import boto3

    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-2"))
    response = client.converse(
        modelId=model_id,
        system=[{"text": call.system}],
        messages=[{"role": "user", "content": [{"text": call.user}]}],
        inferenceConfig={"maxTokens": 1500},
    )
    return response["output"]["message"]["content"][0]["text"]


def apply_model(draft, call: PersonaCall, model):
    """Use the model reply when calls are on and the JSON matches. Otherwise keep the draft."""
    if os.environ.get("BEDROCK_CALLS") != "1":
        return draft
    try:
        payload = _json_object(invoke(call))
        return model.model_validate(payload)
    except Exception:  # noqa: BLE001  a bad model reply must keep the local draft
        return draft


def _json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model reply has no JSON object")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise TypeError("model reply is not an object")
    return payload
