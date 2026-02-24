# Alrighty, for each item in the list, create the Dockerfile, build it, and run it.
# Track if the mvn clean install was successful or not. If not, capture the console output.
# Store the results in a pandas dataframe and export to CSV.

import os
import subprocess
import shutil
import time
import docker
from pymongo import MongoClient
import os


jdks = {
    "jdk6": "maven3.2.5-jdk6",
#    "jdk7": "maven:3.6.1-jdk-7",
#    "jdk8": "maven:3.6.1-jdk-8",
}

def JDK_6_DOCKERFILE(base_image:str, repository:str):
    return f"""
FROM {base_image}

WORKDIR /app

# Ensure modern CA certificates for HTTPS endpoints
USER root
RUN yum -y install ca-certificates \
	&& update-ca-trust \
	&& yum clean all

# Copy project sources
COPY  {repository} .

# Add an entrypoint that sets safe ulimits for old JDKs
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Reduce glibc arena bloat and set conservative JVM options for JDK 6
ENV MALLOC_ARENA_MAX=2 MAVEN_OPTS="-Xmx512m -XX:MaxPermSize=256m -Djava.net.preferIPv4Stack=true -Dhttps.protocols=TLSv1.2 -Djavax.net.ssl.trustStore=/etc/pki/ca-trust/extracted/java/cacerts -Djavax.net.ssl.trustStorePassword=changeit"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["mvn", "clean", "install", "-DskipTests"]
"""

mappings= {
  "FLINK": "flink",
  "CAMEL": "camel",
  "OAK": "jackrabbit-oak",
  "WICKET": "wicket",
  "LOG4J2": "logging-log4j2",
  "MATH": "commons-math",
  "ACCUMULO": "accumulo",
  "MNG": "maven",
}

repo_list = None
with open("no_equi_patch.txt", "r") as f:
    repo_list = [line.strip() for line in f.readlines() if line.strip()]

# DataFrame to store results

mongo_client = MongoClient("mongodb://admin:secret@localhost:27017/")
mongo_db = mongo_client["build_results"]
mongo_coll = mongo_db["results"]

client = docker.from_env()

for repo in repo_list:

    # If Repo exist in current dir as dir, skip repo
    if os.path.isdir(repo):
        print(f"Skipping {repo} as it already exists.")
        continue

    # Clone the repo
    project_key = next((key for key in mappings if key in repo), None)
    project_name = mappings[project_key] if project_key else None
    
    repo_url = f"git@github.com:bugs-dot-jar/{project_name}.git"

    # Clone the repo once per repository (we'll delete it after all jdk runs)
    try:
        subprocess.run(f"git clone {repo_url} --branch {repo} --single-branch {repo}", shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to clone {repo_url} branch {repo}: {e}")
        # record failure and skip this repository entirely
        for jdk in jdks:
            doc = {
                "repository": repo,
                "jdk": jdk,
                "result": "clone_failed",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "output": str(e)
            }
            try:
                mongo_coll.insert_one(doc)
            except Exception as me:
                print(f"Failed to insert clone_failed doc into MongoDB: {me}")
        continue

    # Try for each jdk in jdks
    for jdk in jdks:
        if jdks[jdk] is None:
            print(f"Skipping {repo} for {jdk} as no suitable image is available.")
            continue

        # Build the Dockerfile
        if(jdk == "jdk6"):
            docker_file_content = JDK_6_DOCKERFILE(jdks[jdk], repo)
        else:
            docker_file_content = f"""
        FROM {jdks[jdk]}
        WORKDIR /app
        COPY {repo} .

        CMD ["mvn", "clean", "install", "-DskipTests"]
        """

        print(f"Dockerfile: \n {docker_file_content}")

        dockerfile_tag = f"{repo}-{jdk}".lower()
        with open("Dockerfile", "w") as f:
            f.write(docker_file_content)
        
        # Build the docker image with docker
        container = None
        image = None
        try:
            print(f"Building Docker image for {repo} with {jdk}...")
            image, build_logs = client.images.build(path=".", tag=dockerfile_tag)
            for chunk in build_logs:
                if 'stream' in chunk:
                    print(chunk['stream'].strip())
        except docker.errors.BuildError as e:
            print(f"Failed to build Docker image for {repo} with {jdk}: {e}")
            doc = {
                "repository": repo,
                "jdk": jdk,
                "result": "build_failed",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "output": str(e)
            }
            try:
                mongo_coll.insert_one(doc)
            except Exception as me:
                print(f"Failed to insert build_failed doc into MongoDB: {me}")
            # cleanup temporary Dockerfile if present
            try:
                if os.path.exists("Dockerfile"):
                    os.remove("Dockerfile")
            except Exception:
                pass
            continue
        
        # Run the docker container
        try:
            print(f"Running Docker container for {repo} with {jdk}...")
            container = client.containers.run(dockerfile_tag, detach=True)
            exit_status = container.wait()
            logs = container.logs().decode('utf-8')
            container.remove()
            
            result = "success" if exit_status['StatusCode'] == 0 else "failure"
            doc = {
                "repository": repo,
                "jdk": jdk,
                "result": result,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "output": logs
            }
            try:
                mongo_coll.insert_one(doc)
            except Exception as me:
                print(f"Failed to insert run result doc into MongoDB: {me}")
            print(f"Completed {repo} with {jdk}: {result}")
        except docker.errors.ContainerError as e:
            print(f"Failed to run Docker container for {repo} with {jdk}: {e}")
            doc = {
                "repository": repo,
                "jdk": jdk,
                "result": "run_failed",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "output": str(e)
            }
            try:
                mongo_coll.insert_one(doc)
            except Exception as me:
                print(f"Failed to insert run_failed doc into MongoDB: {me}")
            # cleanup temporary Dockerfile if present
            try:
                if os.path.exists("Dockerfile"):
                    os.remove("Dockerfile")
            except Exception:
                pass
            continue
        finally:
            # Always attempt to clean up container, image and Dockerfile for this jdk and log results
            # Container removal
            try:
                if container is not None:
                    try:
                        container.remove(force=True)
                        print(f"Container for {dockerfile_tag} removed successfully")
                    except Exception as e:
                        print(f"Failed to remove container for {dockerfile_tag}: {e}")
                else:
                    print(f"No container to remove for {dockerfile_tag}")
            except NameError:
                print(f"Container variable not defined for {dockerfile_tag}")

            # Image removal
            try:
                client.images.remove(image=dockerfile_tag, force=True)
                print(f"Image {dockerfile_tag} removed successfully")
            except Exception as e:
                print(f"Failed to remove image {dockerfile_tag}: {e}")

            # remove Dockerfile
            try:
                if os.path.exists("Dockerfile"):
                    os.remove("Dockerfile")
                    print("Removed temporary Dockerfile")
            except Exception as e:
                print(f"Failed to remove Dockerfile: {e}")
        
        # Results are inserted into MongoDB after each run

    # After all jdk runs for this repository, remove the cloned repo directory
    try:
        if os.path.exists(repo):
            shutil.rmtree(repo)
            print(f"Removed cloned repository directory {repo}")
    except Exception as e:
        print(f"Failed to remove cloned repository directory {repo}: {e}")