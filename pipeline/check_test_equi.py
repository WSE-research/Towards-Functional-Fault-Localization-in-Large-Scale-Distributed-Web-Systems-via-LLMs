
import json
import os
from typing import Dict, List

repos:list = ["jackrabbit-oak", "wicket", "camel", "commons-math", "logging-log4j2", "flink", "accumulo","maven"]
OUTPUTS_DIR = "outputs"

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

def check_test_patch_equi():

  total = 0
  written = 0
  skipped = 0

  for repo, branch_dir, branch_path in iter_output_branch_dirs(OUTPUTS_DIR):
      if repos and repo not in repos:
          continue
      analysis_path =  os.path.join(branch_path, "analysis.json")
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
      total += 1

      patched_list = analysis_data.get("patched", [])
      test_list = analysis_data.get("test", [])

      if not isinstance(patched_list, list) or not isinstance(test_list, list):
          print("Skipping invalid analysis for %s/%s" % (repo, branch_dir))
          skipped += 1
          continue
      
      patched_class_list = transform_patched_list_to_classes(patched_list)

      equi_patch_exist = False
      
      for test in test_list:
          test_lower = str(test).lower()
          for patched_class in patched_class_list:
              patched_lower = patched_class.lower()
              if patched_class and patched_lower in test_lower:
                  equi_patch_exist = True
                  break
          if equi_patch_exist:
              break
      if not equi_patch_exist:
          with open(os.path.join(OUTPUTS_DIR, "no_equi_patch.txt"), "a", encoding="utf-8") as out_f:
              out_f.write(branch_dir + "\n")
          written += 1

if __name__ == "__main__":
    check_test_patch_equi()