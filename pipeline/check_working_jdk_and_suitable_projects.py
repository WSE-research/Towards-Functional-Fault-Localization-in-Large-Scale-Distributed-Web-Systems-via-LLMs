# Check for each entry in data/working-examples-jdk6.txt if the project (line) can be found in outputs/ and if it has at least one branch with analysis.json containing suitable_tests with at least one entry.
import os
import json
from typing import List
from helper import iter_output_branch_dirs, send_to_chat_api, TEST_METHOD_SCHEMA, TEST_METHOD_SCHEMA_V2, validate_json
WORKING_EXAMPLES_FILE = "data/working-examples-jdk6.txt"

def check_working_jdk_and_suitable_projects():
  working_projects_with_suitable_tests: List[str] = []
  working_projects_without_suitable_tests: List[str] = []
  missing_projects: List[str] = []

  with open(WORKING_EXAMPLES_FILE, "r") as f:
    working_projects = [line.strip() for line in f if line.strip()]

  output_root = "outputs"

  for project in working_projects:
    project_found = False
    has_suitable_tests = False

    project_name = findProjectName(project)

    project_path = os.path.join(output_root, f"{project_name}/{project}")
    if os.path.isdir(project_path):
      project_found = True
      for _, _, branch_path in iter_output_branch_dirs(output_root):
        if os.path.commonpath([branch_path, project_path]) != project_path:
          continue
        analysis_path = os.path.join(branch_path, "analysis.json")
        if os.path.isfile(analysis_path):
          with open(analysis_path, "r") as f:
            analysis_data = json.load(f)
          if analysis_data.get("suitable_tests"):
            has_suitable_tests = True
            break

    if not project_found:
      missing_projects.append(project)
    elif has_suitable_tests:
      working_projects_with_suitable_tests.append(project)
    else:
      working_projects_without_suitable_tests.append(project)

  print("Projects with suitable tests:")
  for proj in working_projects_with_suitable_tests:
    print(f"  {proj}")
  print("\nProjects without suitable tests:")
  for proj in working_projects_without_suitable_tests:
    print(f"  {proj}")
  print("\nMissing projects:")
  for proj in missing_projects:
    print(f"  {proj}")

  # Write projects with suitable tests to file
  with open("data/working-examples-jdk6-with-suitable-tests.txt", "w") as f:
    for proj in working_projects_with_suitable_tests:
      f.write(f"{proj}\n")

  
  print("\nSummary:")
  print(f"  Total working projects with JDK6: {len(working_projects)}")
  print(f"  Total with suitable tests: {len(working_projects_with_suitable_tests)}")
  print(f"  Total without suitable tests: {len(working_projects_without_suitable_tests)}")
  print(f"  Total missing projects: {len(missing_projects)}")

def findProjectName(project: str) -> str:
    project = project.upper()
    if "WICKET" in project:
        return "wicket"
    elif "MATH" in project:
        return "commons-math"
    elif "LOG4J2" in project:
        return "logging-log4j2"
    elif "FLINK" in project:
        return "flink"
    elif "ACCUMULO" in project:
        return "accumulo"
    elif "OAK" in project:
        return "jackrabbit-oak"
    elif "CAMEL" in project:
        return "camel"
    elif "MNG" in project:
        return "maven"

def main():
  check_working_jdk_and_suitable_projects()

if __name__ == "__main__":
  main()