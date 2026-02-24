import base64
import requests
import os
from typing import Dict, List
from helper import send_to_chat_api, ANALYSIS_V1_SCHEMA, validate_json

import json
import logging
from logging import Logger

# Configure module-level logger
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
  level=LOG_LEVEL,
  format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger: Logger = logging.getLogger("fetch_and_analyze")

repos:list = ["jackrabbit-oak", "wicket", "camel", "commons-math", "logging-log4j2", "flink", "accumulo","maven"]
GITHUB_API = "https://api.github.com"
_github_pat = os.getenv("GITHUB_PAT", "")
gh_headers: Dict[str, str] = {
  "Authorization": f"Bearer {_github_pat}",
  "Accept": "application/vnd.github+json",
  "User-Agent": "bugs-dot-jar-script",
}

BUGS_DOT_JAR = "bugs-dot-jar"

def build_prompt(patch:bytes, test:bytes) -> str:
  with open("prompts/analysis_prompt.txt", "r") as f:
    base_prompt = f.read()

  p = base_prompt
  p = p.replace("{patch}", patch.strip())
  p = p.replace("{test_log}", test.strip())
  return p

def process_branch(repo:str, branch:str, output_dir:str):
  logger.info("Process branch: %s of repo: %s", branch, repo)

  branch_dir = os.path.join(output_dir, branch.replace("/", "__"))
  patch_path = os.path.join(branch_dir, "developer-patch.diff")
  test_path = os.path.join(branch_dir, "test-results.txt")

  if not (os.path.isfile(patch_path) and os.path.isfile(test_path)):  # Skip fetching if both files exist
    patch = fetch_repo_files(repo, branch, "developer-patch.diff")
    test = fetch_repo_files(repo, branch, "test-results.txt")

    # Record whether each artifact was found
    patch_exists = patch is not None
    test_exists = test is not None

    # If neither file was found, nothing to do for this branch
    if not (patch_exists or test_exists):
      logger.debug("No patch or test found for %s@%s", repo, branch)
      return False

    # Ensure output directory exists when we will write files
    os.makedirs(branch_dir, exist_ok=True)
    
    patch_text = patch.decode("utf-8", errors="replace") if patch else None
    test_text = test.decode("utf-8", errors="replace") if test else None

    if patch_text:
      with open(os.path.join(branch_dir, "developer-patch.diff"), "w", encoding="utf-8") as f:
        f.write(patch_text)
      logger.debug("Wrote patch to %s", patch_path)
    if test_text:
      with open(os.path.join(branch_dir, "test-results.txt"), "w", encoding="utf-8") as f:
        f.write(test_text)
      logger.debug("Wrote test results to %s", test_path)
  
  else:
    with open(patch_path, "rb") as f:
      patch_text = f.read().decode("utf-8", errors="replace") if os.path.isfile(patch_path) else None
    with open(test_path, "rb") as f:
      test_text = f.read().decode("utf-8", errors="replace") if os.path.isfile(test_path) else None
    logger.debug("Loaded existing files for branch %s: patch=%s test=%s", branch, bool(patch_text), bool(test_text))

  if os.path.isfile(os.path.join(branch_dir, "analysis.json")):
    logger.info("Analysis already exists for %s on branch %s, skipping", repo, branch)
    return True
  
  prompt = build_prompt(patch_text, test_text)
  
  logger.debug("Sending prompt to analysis API for %s@%s (prompt length=%d)", repo, branch, len(prompt))
  try:
    answer = send_to_chat_api(prompt)
    answer = json.loads(answer)
  except Exception as e:
     return False


  isValid = validate_json(answer, ANALYSIS_V1_SCHEMA) # Validate response, only true when it contains valid data
  
  if isValid and isinstance(answer, dict):
    out_path = os.path.join(branch_dir, "analysis.json")
    with open(out_path, "w") as f:
      json.dump(answer, f, indent=2, ensure_ascii=False)
    logger.info("Wrote analysis for %s@%s to %s", repo, branch, out_path)
  else:
     return False

  logger.info("Branch %s processed.", branch)
  return True


def fetch_repo_files(repo:str, branch, target:str):
  url = f"{GITHUB_API}/repos/{BUGS_DOT_JAR}/{repo}/contents/.{BUGS_DOT_JAR}/{target}" #.bugs-dot-jar/developer-patch.diff
  logger.debug("Fetching repo file %s for %s@%s", target, repo, branch)
  resp = requests.get(url, headers=gh_headers, params={"ref": branch}, timeout=30)
  if resp.status_code != 200:
      if resp.status_code == 401:
          raise PermissionError("Unauthorized access to GitHub API")
      else:
        logger.error("GitHub API error fetching %s: %s %s", url, resp.status_code, resp.text)
        raise RuntimeError(
          f"GitHub API error fetching file: {resp.status_code} {resp.text}"
      )
  data = resp.json()
  if isinstance(data, list):
    return None
  content_b64 = data.get("content")
  if not isinstance(content_b64, str):
    return None
  content_b64 = content_b64.replace("\n", "")
  try:
    return base64.b64decode(content_b64)
  except Exception:
    return None


def list_all_branches(owner:str, repo:str) -> List[str]:
    """Return a list of all branch names for the given repo, with pagination.

    Raises RuntimeError on non-200 responses.
    """
    logger.info("Listing all branches for repo %s/%s", owner, repo)
    branches: List[str] = []
    page = 1
    per_page = 100
    while True:
        url = f"{GITHUB_API}/repos/{BUGS_DOT_JAR}/{repo}/branches"
        resp = requests.get(url, headers=gh_headers, params={"per_page": per_page, "page": page}, timeout=30)
        if resp.status_code != 200:
            if resp.status_code == 401:
               raise PermissionError("Unauthorized access to GitHub API")
            else:
              logger.error("GitHub API error listing branches for %s: %s %s", repo, resp.status_code, resp.text)
              raise RuntimeError(f"GitHub API error listing branches: {resp.status_code} {resp.text}")
        data = resp.json()
        if not data:
            break
        for b in data:
            name = b.get("name")
            if isinstance(name, str):
                branches.append(name)
        if len(data) < per_page:
            break
        page += 1
    logger.info("Total branches found for %s: %d", repo, len(branches))
    return branches

def fetch_and_analyze():

    with open("prompts/analysis_prompt.txt", "r") as f:
        prompt = f.read()

    processed = 0
    skipped = 0
    skippedList = []
    count = 0

    for repo in repos:
        logger.info("Processing project: %s", repo)

        try:
            branches = list_all_branches("bugs-dot-jar", repo)
        except Exception:
            logger.exception("Error fetching branches for %s", repo)
            continue

        if not branches:
            logger.warning("No branches found for %s", repo)
            continue

        repo_output_dir = os.path.join("outputs", repo)
        os.makedirs(repo_output_dir, exist_ok=True)

        # Count per-repo (branches) for clearer per-repo logging, and accumulate totals
        repo_processed = 0
        repo_skipped = 0

        # Branches should only contain items that start with "bugs-dot-jar"
        branches = [b for b in branches if b.startswith("bugs-dot-jar")]

        for branch in branches:
            count += 1
            try:
                did = process_branch(repo, branch, repo_output_dir)
                if did:
                    repo_processed += 1
                else:
                    repo_skipped += 1
                    skippedList.append(f"{repo}@{branch}")
            except PermissionError as e:
                logger.error("Auth error for GitHub API, %s", e) # Occurs when API request fails
                skippedList.append(f"{repo}@{branch}")
                skipped += 1
                continue
            except Exception as e:
                skippedList.append(f"{repo}@{branch}")
                skipped += 1
                continue

        processed += repo_processed
        skipped += repo_skipped

        logger.info("Repo %s done. processed=%d skipped=%d", repo, repo_processed, repo_skipped)

    overall_total = processed + skipped
    logger.info("All repos done. processed=%d skipped=%d total=%d", processed, skipped, overall_total)
    logger.info("Skipped branches so far: %s", skippedList)
    logger.info(f"Total branches processed: {count}")

if __name__ == "__main__":
    fetch_and_analyze()