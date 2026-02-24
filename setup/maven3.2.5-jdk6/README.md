# JDK6 - Maven3.2.5 Setup
For the experiments with the bugs-dot-jar repository, it was mandatory to use JDK6, as it provided the most working examples when testing the successful compilation for different JDKs (i.e. JDK6/7/8). This preliminary study was needed, as the dataset was comparibly old, with projects older than 10 years. However, JDK6 brings some difficulties, e.g. TLS1.1 and more. Thus, we provide a setup for it with all necessary files.

### Step 1: Install JDK6 and maven
#### JDK6
1. Download the file `jdk-6u45-linux-x64.bin`.
2. Make it executable: `sudo  chmod +x jdk-6u45-linux-x64.bin`
3. Run the installer: `./jdk-6u45-linux-x64.bin`
4. Copy the files to your desired Java installation path, e.g.: `cp -r jdk1.6.0_45/ /opt/java/`

#### Maven3.2.5
We use Maven 3.2.5 because it is one of the newest versions still compatible with JDK6.
1. Download the tarball: `wget https://archive.apache.org/dist/maven/maven-3/3.2.5/binaries/apache-maven-3.2.5-bin.tar.gz`
2. Extract it `tar -xzf apache-maven-3.2.5-bin.tar.gz`
3. Copy the files to your desired installation path: `cp -r apache-maven-3.2.5/ /opt/maven`

### Step 2: Add TLS1.2 support
Reference: <<URL>>

1. Set JDK6 as your `JAVA_HOME` to ensure the following steps work: `export JAVA_HOME=/opt/java/jdk1.6.0_45`
2. Copy the required files: cp jdk6_requirements/jce_policy-6/jce/local_policy.jar $JAVA_HOME/jre/lib/security/ &&
cp jdk6_requirements/jce_policy-6/jce/US_export_policy.jar $JAVA_HOME/jre/lib/security/ &&
cp jdk6_requirements/bcprov-jdk15to18-1.71.jar $JAVA_HOME/jre/lib/ext/ &&
cp jdk6_requirements/bctls-jdk15to18-1.71.jar $JAVA_HOME/jre/lib/ext/ &&
cp jdk6_requirements/bcutil-jdk15to18-1.71.jar $JAVA_HOME/jre/lib/ext/ &&
cp jdk6_requirements/java.security $JAVA_HOME/jre/lib/security/java.security
3. Optionally, you may also need to add certificates for Maven Central (see Step 2b).

### Step 2b: Add certs for maven central
**TODO:** Provide instructions for installing the required certificates.

### Step 3: Use JDK6 and maven3.2.5
To run the experiments with the previously configured setup, set the environment variables for this session:
```
export M2_HOME=/opt/maven
export PATH=$M2_HOME/bin:$PATH
export JAVA_HOME=/opt/java/jdk1.6.0_45
export PATH=$JAVA_HOME/bin:$PATH
```
This ensures that:
1. Maven 3.2.5 is used (M2_HOME and PATH updated)
2. JDK6 is active (JAVA_HOME and PATH updated)

You can now run Maven commands and compile the projects with the JDK6 environment.

---
If you still encounter issues, current LLMs can provide helpful troubleshooting guidance.


