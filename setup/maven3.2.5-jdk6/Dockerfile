FROM oraclelinux:7-slim

# Maximum maven version for JDK 6 is 3.2.5
ENV MAVEN_VERSION=3.2.5

# Set correct JAVA_HOME path for this image
ENV JAVA_HOME=/usr/java/jdk1.6.0_45
ENV PATH=$JAVA_HOME/bin:$PATH
ENV REQUIREMENTS_DIR=jdk6_requirements/

# Install basic tools and CA certs
RUN yum -y install wget unzip tar gzip which shadow-utils \
    libnsl \
    libXext \
    libXrender \
    libXtst \
    libXi \
    fontconfig \
    findutils \
    tar \
    gzip \
    ca-certificates \
    && yum clean all


COPY jdk6_requirements/jdk-6u45-linux-amd64.rpm /tmp/
# Install JDK 6
RUN rpm -ivh /tmp/jdk-6u45-linux-amd64.rpm

# Install Maven 3.2.5
RUN wget https://archive.apache.org/dist/maven/maven-3/3.2.5/binaries/apache-maven-3.2.5-bin.tar.gz -O /tmp/maven.tar.gz \
    && tar -xzf /tmp/maven.tar.gz -C /opt/ \
    && mv /opt/apache-maven-3.2.5 /opt/maven \
    && rm /tmp/maven.tar.gz

ENV M2_HOME=/opt/maven
ENV PATH=$M2_HOME/bin:$PATH

# Add TLS1.2 support for Java 6

COPY jdk6_requirements/jce_policy-6/jce/local_policy.jar $JAVA_HOME/jre/lib/security/
COPY jdk6_requirements/jce_policy-6/jce/US_export_policy.jar $JAVA_HOME/jre/lib/security/

COPY jdk6_requirements/bcprov-jdk15to18-1.71.jar $JAVA_HOME/jre/lib/ext/
COPY jdk6_requirements/bctls-jdk15to18-1.71.jar $JAVA_HOME/jre/lib/ext/
COPY jdk6_requirements/bcutil-jdk15to18-1.71.jar $JAVA_HOME/jre/lib/ext/

COPY jdk6_requirements/java.security $JAVA_HOME/jre/lib/security/java.security

# Helpful defaults for allocator behavior
ENV MALLOC_ARENA_MAX=2

CMD ["sh", "-c", "mvn --version && java -version"]