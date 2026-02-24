from helper import iter_output_branch_dirs
import os
import json
import re
from typing import Any, Dict

def step_enrich_packages(outputs_dir: str = "outputs") -> None:
    """Step 4: infer and attach 'sourcePackage' to each analysis.json where possible.

    It looks for lines like '[ERROR] Please refer to .../<module>/target/' in test-results.txt,
    extracts '<module>' as the source package, and updates analysis.json if missing.
    """
    updated = 0
    skipped = 0
    skipped_list = []
    for repo, branch_dir, branch_path in iter_output_branch_dirs(outputs_dir):
        test_result_file = os.path.join(branch_path, "test-results.txt")
        if not os.path.isfile(test_result_file):
            skipped += 1
            skipped_list.append(branch_path)
            continue
        branch_clean = branch_dir
        if branch_clean.startswith("bugs-dot-jar_"):
            branch_clean = branch_clean[len("bugs-dot-jar_"):]
        found_pkg = None
        try:
            with open(test_result_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("[ERROR] Please refer to"):
                        pattern = rf"{re.escape(branch_clean)}[^/]*/(?:(.+)/)?target/"
                        match = re.search(pattern, line)
                        if match:
                            found_pkg = match.group(1) or ""
                        break
        except Exception:
            continue
        if found_pkg is None:
            continue
        analysis_file = os.path.join(branch_path, "analysis.json")
        if not os.path.isfile(analysis_file):
            skipped += 1
            skipped_list.append(branch_path)
            continue
        with open(analysis_file, "r", encoding="utf-8") as f:
            analysis_data: Dict[str, Any] = json.load(f)
        if "sourcePackage" not in analysis_data:
            analysis_data["sourcePackage"] = found_pkg
            with open(analysis_file, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, indent=2)
            updated += 1
        elif "sourcePackage" in analysis_data:
            updated += 1
    print(f"Enriched {updated} analysis.json files with sourcePackage")
    print(f"Skipped {skipped} branches without sourcePackage info")
    print("Skipped branches:", skipped_list)

def main():
    step_enrich_packages()

if __name__ == "__main__":
    main()
