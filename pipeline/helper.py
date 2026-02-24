import logging
import os
from typing import List
import requests
from logging import Logger
from jsonschema import validate, ValidationError, Draft202012Validator
import json

# Configure module-level logger
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
  level=LOG_LEVEL,
  format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger: Logger = logging.getLogger("helper")

API_BASE = os.getenv("ANALYSIS_API_BASE", "http://localhost:8080/v1")
API_KEY = os.getenv("ANALYSIS_API_KEY", "")
MODEL = os.getenv("ANALYSIS_MODEL", "gpt-4.1")


def iter_output_branch_dirs(outputs_root: str):
    """Yield (repo, branch_dir, branch_path) for each branch directory under outputs_root/<repo>/*.

    Skips non-directories.
    """
    if not os.path.isdir(outputs_root):
        return
    for repo in os.listdir(outputs_root):
        repo_path = os.path.join(outputs_root, repo)
        if not os.path.isdir(repo_path):
            continue
        for branch_dir in os.listdir(repo_path):
            branch_path = os.path.join(repo_path, branch_dir)
            if os.path.isdir(branch_path):
                yield repo, branch_dir, branch_path

def transform_patched_list_to_classes(patched_list: List[str]) -> List[str]:
    """Transform fully-qualified class names to simple class names.

    Example: 'org.apache.jackrabbit.oak.core.RootImpl' -> 'RootImpl'
    """
    class_list: List[str] = []
    if not patched_list:
        return class_list
    for item in patched_list:
        try:
            class_name = item.split(".")[-1]
            class_list.append(class_name)
        except AttributeError:
            continue
    return class_list

def send_to_chat_api(prompt:str) -> str:
  if not API_KEY or not MODEL or not API_BASE:
    raise RuntimeError("API_KEY, MODEL, and API_BASE must be set")
   
  url = f"{API_BASE}/chat/completions"
  payload = {
    "model": MODEL,
    "messages": [
      {"role": "system", "content": "You are a precise software analysis assistant. Reply with ONLY valid JSON as requested."},
      {"role": "user", "content": prompt}
    ]
  }

  logger.debug("Payload for chat API request: %s", payload)

  headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
  }
  try:
    response = requests.post(url, json=payload, headers=headers)
  except Exception as e:
    logger.exception("Failed to send chat API request to %s", url)
    raise

  if response.status_code != 200:
    logger.error("Chat API returned non-200: %s %s", response.status_code, response.text)
    raise RuntimeError(f"Chat API error: {response.status_code} {response.text}")
  
  data = response.json()
  content = None
  if isinstance(data, dict):
    try:
       content = data["choices"][0]["message"]["content"]
    except Exception:
      if isinstance(data.get("message"), str):
        content = data["message"]
      elif isinstance(data.get("content"), str):
        content = data["content"]
  elif isinstance(data, str):
    content = data
  
  if content is None:
     content = response.text
  
  if isinstance(content, dict):
     return content
  elif isinstance(content, str):
     return strip_code_fences(content)

def validate_json(data: dict, schema: dict) -> bool:
    try:
        validate(instance=data, schema=schema, cls=Draft202012Validator)
        return True
    except ValidationError as e:
        logger.warning("Validation error: %s | data: %s", e.message, data)
        return False

def strip_code_fences(s: str) -> str:
    """Remove outer ```...``` fences and optional language tag from a string."""
    s = s.strip()
    if s.startswith("```") and s.endswith("```"):
        s = s[3:-3].strip()
        first_newline = s.find("\n")
        if first_newline != -1:
            maybe_lang = s[:first_newline].strip().lower()
            if maybe_lang in {"json", "jsonc", "javascript", "js"}:
                s = s[first_newline + 1 :].lstrip()
    return s

ANALYSIS_V1_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "patched": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "test": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    }
  },
  "required": ["patched", "test"],
  "additionalProperties": False
}


TEST_METHOD_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "failingTests": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "failingTest": {
            "type": "object",
            "properties": {
              "failingTestClass": {"type": "string"},
              "failingTestMethod": {"type": "string"}
            },
            "required": ["failingTestClass", "failingTestMethod"],
            "additionalProperties": False
          }
        },
        "required": ["failingTest"],
        "additionalProperties": False
      },
      "minItems": 1
    }
  },
  "required": ["failingTests"],
  "additionalProperties": False
}

TEST_METHOD_SCHEMA_V2 = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "failingTests": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "failingTestClass": {"type": "string"},
          "failingTestMethod": {"type": "string"},
        },
        "required": ["failingTestClass", "failingTestMethod"],
        "additionalProperties": False,
      },
      "minItems": 1,
    }
  },
  "required": ["failingTests"],
  "additionalProperties": False,
}