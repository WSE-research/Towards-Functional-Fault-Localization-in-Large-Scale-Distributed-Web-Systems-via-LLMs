import argparse
import logging
import os
import requests
import json

import tiktoken
from build_hierarchy import get_hierarchy_xml_string

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Token thresholds and model selection as used in the paper (Section 4)
_MODEL_TIERS = [
    (400_000,   "openai/gpt-5"),
    (1_000_000, "google/gemini-3-flash-preview"),
    (2_000_000, "x-ai/grok-4.1-fast"),
]


def num_tokens_from_string(string: str, model: str = "gpt-4o") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(model)
    num_tokens = len(encoding.encode(string))
    return num_tokens


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


def evaluate_calltree(graph_uri: str) -> str:
    # Load prompt template
    with open("prompts/evaluation_prompt.txt", "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Load calltree as XML
    calltree_xml = get_hierarchy_xml_string(graph_uri=graph_uri)

    # Build prompt
    prompt = prompt_template.replace("{calltree_xml}", calltree_xml)

    # Select model based on token count
    prompt_tokens = num_tokens_from_string(prompt)
    logger.info("Prompt token count: %d", prompt_tokens)
    model = select_model(prompt_tokens)
    logger.info("Selected model: %s", model)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "reasoning": {"enabled": True},
    }

    res = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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

    data = res.json()
    logger.debug("Raw OpenRouter response: %s", data)

    if "choices" not in data or not data["choices"]:
        logger.error("Unexpected OpenRouter response format: %s", data)
        raise RuntimeError(f"Unexpected OpenRouter response: {data}")

    message = data["choices"][0]["message"]
    content = message.get("content", "")
    logger.info("Response: %s", content)

    return content


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate a calltree graph by URI."
    )
    parser.add_argument(
        "graph_uri",
        help="Named graph URI of the calltree in the Virtuoso SPARQL store.",
    )
    args = parser.parse_args()

    evaluate_calltree(args.graph_uri)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()