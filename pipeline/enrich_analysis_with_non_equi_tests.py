from helper import iter_output_branch_dirs, transform_patched_list_to_classes
import os
import json

OUTPUTS_DIR = "outputs"

def enrich_analysis_with_non_equi_tests():
    """Enrich analysis.json files with non-equivalent test and patch information."""

    skipped = 0
    enriched = 0
    count = 0

    for repo, branch_dir, branch_path in iter_output_branch_dirs(OUTPUTS_DIR):
        count += 1
        analysis_path = os.path.join(branch_path, "analysis.json")
        if not os.path.isfile(analysis_path):
            print("Skipping missing analysis for %s/%s" % (repo, branch_dir))
            skipped += 1
            continue
        with open(analysis_path, "r") as f:
            analysis_data = json.load(f)
        if not analysis_data:
            print("Skipping empty analysis for %s/%s" % (repo, branch_dir))
            skipped += 1
            continue
        if analysis_data.get("suitable_tests") is not None:
            print("Skipping already enriched analysis for %s/%s" % (repo, branch_dir))
            enriched += 1
            continue

        patched_list = analysis_data.get("patched", [])
        test_list = analysis_data.get("test", [])

        patched_class_list = transform_patched_list_to_classes(patched_list)
        test_class_list = transform_patched_list_to_classes(test_list)

        suitable_tests = []

        for test_class in test_class_list:
            test_class_lower = str(test_class).lower()
            equi_found = False
            for patched_class in patched_class_list:
                patched_class_lower = str(patched_class).lower()
                if patched_class_lower in test_class_lower:
                    equi_found = True
                    break
            if not equi_found:
                suitable_tests.append(test_class)

        if len(suitable_tests) > 0:
            analysis_data["suitable_tests"] = suitable_tests
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, indent=2)
            print("Enriched analysis for %s/%s with %d non-equivalent tests" % (repo, branch_dir, len(suitable_tests)))
            enriched += 1
        else:
            skipped += 1

    print("Summary: Enriched %d analyses, skipped %d analyses" % (enriched, skipped))
    print(f"Total analyses processed: {count}")

def remove_all_suitable_tests_from_analyses():
    """Remove suitable_tests field from all analysis.json files."""
    for repo, branch_dir, branch_path in iter_output_branch_dirs(OUTPUTS_DIR):
        analysis_path = os.path.join(branch_path, "analysis.json")
        if not os.path.isfile(analysis_path):
            print("Skipping missing analysis for %s/%s" % (repo, branch_dir))
            continue
        with open(analysis_path, "r") as f:
            analysis_data = json.load(f)
        if not analysis_data:
            print("Skipping empty analysis for %s/%s" % (repo, branch_dir))
            continue
        if analysis_data.get("suitable_tests") is None:
            print("No suitable_tests to remove for %s/%s" % (repo, branch_dir))
            continue

        analysis_data.pop("suitable_tests", None)
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis_data, f, indent=2)
        print("Removed suitable_tests from analysis for %s/%s" % (repo, branch_dir))

if __name__ == "__main__":
    #remove_all_suitable_tests_from_analyses()
    enrich_analysis_with_non_equi_tests()