# Script to find the failing test method for each existing suitable test class

import logging
import os
import json
from helper import iter_output_branch_dirs, send_to_chat_api, TEST_METHOD_SCHEMA, TEST_METHOD_SCHEMA_V2, validate_json

logger = logging.getLogger(__name__)

TEST_RESULTS_FILENAME = "test-results.txt"


def find_method_for_suitable_testclasses():

    skipped = 0
    enriched = 0
    enriched_list = []

    for repo, branch_dir, branch_path in iter_output_branch_dirs("outputs"):
        analysis_path = os.path.join(branch_path, "analysis.json")

        if not os.path.isfile(analysis_path):
            logger.debug("Skipping missing analysis for %s/%s", repo, branch_dir)
            skipped += 1
            continue

        with open(analysis_path, "r") as f:
            analysis_data = json.load(f)

        if not analysis_data or not analysis_data.get("suitable_tests"):
            logger.debug("Skipping analysis without suitable tests for %s/%s", repo, branch_dir)
            skipped += 1
            continue
        elif analysis_data.get("suitable_test_methods") is not None:
            logger.debug("Skipping already enriched analysis for %s/%s", repo, branch_dir)
            enriched += 1
            continue

        suitable_tests = analysis_data.get("suitable_tests")
        cases = []
        is_skip_for_all = True

        with open(os.path.join("prompts", "test_method_prompt.txt"), "r") as f:
            prompt_template = f.read()

        for test_class in suitable_tests:
            test_results_path = os.path.join(branch_path, TEST_RESULTS_FILENAME)

            if not os.path.isfile(test_results_path):
                logger.warning("Missing test results for %s/%s", repo, branch_dir)
                continue

            with open(test_results_path, "r") as f:
                test_results = f.read()

            prompt = prompt_template.replace("{testClass}", test_class).replace("{testLog}", test_results)

            try:
                response = send_to_chat_api(prompt)
                response_json = json.loads(response)
            except Exception as e:
                logger.warning("Failed to get valid response for %s/%s test class %s: %s", repo, branch_dir, test_class, e)
                continue

            is_valid = validate_json(response_json, TEST_METHOD_SCHEMA)
            if is_valid:
                cases.extend(response_json["failingTests"])
                is_skip_for_all = False
            else:
                logger.debug("Schema V1 invalid, trying schema V2 for %s/%s test class %s", repo, branch_dir, test_class)
                is_valid_v2 = validate_json(response_json, TEST_METHOD_SCHEMA_V2)
                if is_valid_v2:
                    v2_items = response_json.get("failingTests") or []
                    converted = [
                        {"failingTest": {
                            "failingTestClass": item["failingTestClass"],
                            "failingTestMethod": item["failingTestMethod"],
                        }}
                        for item in v2_items
                    ]
                    cases.extend(converted)
                    is_skip_for_all = False

        if is_skip_for_all:
            logger.warning("No test methods found for any suitable test class in %s/%s", repo, branch_dir)
            skipped += 1
            continue

        if cases:
            analysis_data["suitable_test_methods"] = cases
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, indent=2)
            enriched += 1
            enriched_list.append((repo, branch_dir, len(cases)))
            logger.info("Enriched %s/%s with %d suitable test methods", repo, branch_dir, len(cases))

    logger.info("Finished processing. Enriched: %d, Skipped: %d", enriched, skipped)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    find_method_for_suitable_testclasses()
