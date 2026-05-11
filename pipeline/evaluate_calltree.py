import argparse
import logging
import os
import requests
import json
import datetime

import tiktoken
from build_hierarchy import get_hierarchy_xml_string

logger = logging.getLogger(__name__)

# Token thresholds and model selection as used in the paper (Section 4)
_MODEL_TIERS = [
    (400_000,   "openai/gpt-5"),
    (1_000_000, "google/gemini-3-flash-preview"),
    (2_000_000, "x-ai/grok-4.1-fast"),
]


def calculate_token(string: str, model: str = "gpt-4o") -> int:
    """Return an estimated token count for a given text.

    Behavior:
    - Try a model-specific encoding (stripping provider prefixes like "openai/").
    - Fall back to the provided model name if normalization fails.
    - As a last resort use the common "cl100k_base" encoding.

    This is resilient to models named like "openai/gpt-5" or unknown model names.
    """
    if not string:
        return 0

    # Normalize model name: allow forms like "openai/gpt-5" by taking last segment
    norm_model = model.split("/")[-1] if model else model

    encoding = None
    try:
        try:
            encoding = tiktoken.encoding_for_model(norm_model)
        except Exception:
            # Try the raw model name next
            encoding = tiktoken.encoding_for_model(model)
    except Exception:
        # Final fallback to a reasonable default encoding
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # As an absolute last resort, approximate by character count / 4
            return max(0, len(string) // 4)

    try:
        return len(encoding.encode(string))
    except Exception:
        return max(0, len(string) // 4)


def select_model(token_count: int) -> str:
    """Select the appropriate OpenRouter model based on prompt token count.

    GPT-5 for <=400k tokens, Gemini for <=1M, Grok for <=2M.
    Raises ValueError when the prompt exceeds all supported context windows.
    """
    for threshold, model in _MODEL_TIERS:
        if token_count <= threshold:
            return model
    raise ValueError(
        f"Prompt exceeds maximum supported context window ({token_count} tokens)."
    )


def evaluate_calltree(graph_uri: str, endpoint:str, api_key: str, model: str = None) -> str:
    # Load prompt template
    with open("prompts/evaluation_prompt.txt", "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Load calltree as XML
    calltree_xml = get_hierarchy_xml_string(graph_uri=graph_uri)

    # Build prompt
    prompt = prompt_template.replace("{calltree_xml}", calltree_xml)

    data = send_evaluation_request(prompt, endpoint=endpoint, api_key=api_key, model=model)
    logger.debug("Raw OpenRouter response: %s", data)

    if "choices" not in data or not data["choices"]:
        logger.error("Unexpected OpenRouter response format: %s", data)
        raise RuntimeError(f"Unexpected OpenRouter response: {data}")

    message = data["choices"][0]["message"]
    content = message.get("content", "")
    logger.info("Response: %s", content)

    return content

def send_evaluation_request(prompt: str, endpoint: str, api_key: str, model: str) -> str:
    # Build an initial payload and estimate token count on the serialized
    # JSON payload (this better matches how the server counts "text input").
    tentative_model = model or _MODEL_TIERS[-1][1]
    payload = {
        "model": tentative_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "reasoning": {"enabled": False},
    }

    try:
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = len(enc.encode(json.dumps(payload)))
    except Exception:
        tokens = max(0, len(json.dumps(payload)) // 4)

    print(f"Estimated payload token count: {tokens}")
    # Select model depending on token count if not explicitly provided
    if model is None:
        model = select_model(tokens)
        payload["model"] = model

    res = requests.post(
        url=f"{endpoint}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=60,
    )

    try:
        res.raise_for_status()
    except requests.HTTPError as e:
        logger.error("HTTP error from OpenRouter: %s - body: %s", e, res.text)
        raise
    return res.json()

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate a calltree graph by URI."
    )
    parser.add_argument("graph_uri", help="Named graph URI of the calltree in the Virtuoso SPARQL store.",)
    parser.add_argument("--model", default=None, help="Optional OpenRouter model override.")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions", help="OpenRouter API endpoint URL.")
    parser.add_argument("--api-key", dest="api_key", default=os.getenv("OPENROUTER_API_KEY"), help="OpenRouter API key (defaults to OPENROUTER_API_KEY env var).")
    args = parser.parse_args()

    if not args.api_key:
        raise ValueError("OpenRouter API key missing. Provide --api-key or set OPENROUTER_API_KEY.")

    evaluate_calltree(args.graph_uri, endpoint=args.endpoint, api_key=args.api_key, model=args.model)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()