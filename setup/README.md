# Environment Setup (Step 3)

This directory contains setup instructions, Maven configuration templates, and the AspectJ tracing agent required to compile the bugs-dot-jar branches and run tests with call-tree recording.

## Background

The bugs-dot-jar dataset was introduced in 2018. Finding a compatible build toolchain required step-wise downgrading from recent JDK versions. The final working setup is:

- **JDK 6** (TLS 1.2 compatible build, e.g., Azul Zulu 6)
- **Maven 3.2.5**
- **AspectJ 1.6.10** weaving agent compiled for JDK 6

## Setup Steps

### 1. JDK 6 and Maven 3.2.5

To execute experiments on your own, you need to use JDK 6. However, during our research we found it difficult to set it up properly. That's why we provide a step-by-step solution that worked out for us. The submodule `maven3.2.5-jdk6` explains it in detail. We recommend setting it up locally following the instructions in [`setup/maven3.2.5-jdk6/README.md`](maven3.2.5-jdk6/README.md).

### 2. Install the `methodaspect` Tracing Agent

The call-tree tracer is published as a custom Maven artifact (`org.wse-research:methodaspect:0.1.0`) in the **local file-system repository** at `setup/aspect/`. It was compiled targeting JDK 6 bytecode using AspectJ 1.6.10 (the last version compatible with Java 6). The source code of the aspect is accessible at https://github.com/WSE-research/methodaspect.

The aspect instruments every method entry and exit event to record:
- Caller and callee fully-qualified class/method names
- Method parameter types and values
- Return values and thrown exceptions

All recorded events are written to Virtuoso via SPARQL Update, building the call-graph named graph used in Steps 4–6. The aspect introduces no changes to functional behavior.

#### Install into your local Maven repository

Before the artifact can be resolved by Maven, install it from the bundled files:

```bash
mvn install:install-file \
  -Dfile=setup/aspect/0.1.0/methodaspect-0.1.0.jar \
  -DsourcesFile=setup/aspect/0.1.0/methodaspect-0.1.0-sources.jar \
  -DjavadocFile=setup/aspect/0.1.0/methodaspect-0.1.0-javadoc.jar \
  -DpomFile=setup/aspect/0.1.0/methodaspect-0.1.0.pom \
  -DgroupId=org.wse-research \
  -DartifactId=methodaspect \
  -Dversion=0.1.0 \
  -Dpackaging=jar
```

### 3. Instrumenting a bugs-dot-jar Branch

Three changes must be made to the target project before running tests. Example setups can be found in the `scripts/` directory.

#### 3a. Add dependencies (`templates/maven/required_dependencies.xml`)

Paste the contents into the `<dependencies>` block of the target `pom.xml`:

```xml
<dependency>
    <groupId>org.aspectj</groupId>
    <artifactId>aspectjrt</artifactId>
    <version>1.6.10</version>
</dependency>
<dependency>
    <groupId>org.wse-research</groupId>
    <artifactId>methodaspect</artifactId>
    <version>0.1.0</version>
</dependency>
```

#### 3b. Add the Surefire plugin (`templates/maven/required_plugin.xml`)

Paste the contents into the `<build><plugins>` block of the target `pom.xml`:

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-surefire-plugin</artifactId>
  <version>2.19.1</version>
  <configuration>
    <argLine>
      -javaagent:${settings.localRepository}/org/aspectj/aspectjweaver/1.6.10/aspectjweaver-1.6.10.jar
      -Daj.weaving.load=true
      -Dorg.aspectj.weaver.showWeaveInfo=true
    </argLine>
  </configuration>
</plugin>
```

#### 3c. Create `src/main/resources/META-INF/aop.xml`

This file configures the AspectJ load-time weaver. It defines two pointcuts via the abstract `MethodAspect` base class:
- `testMethodExecution` — the entry-point test method that starts the trace
- `anyMethodExceptAspect` — all methods in the project's package to be recorded

Use `setup/templates/aop.xml-TEMPLATE` as a starting point:

```xml
<aspectj>
  <aspects>
    <concrete-aspect name="org.wseresearch.methodaspect.ConcreteMethodAspect"
                     extends="org.wseresearch.methodaspect.MethodAspect">
      <pointcut name="testMethodExecution"
                expression="execution(* PACKAGE_AND_CLASS.METHOD(..))"/>
      <pointcut name="anyMethodExceptAspect"
                expression="execution(* PACKAGE) &amp;&amp; !execution(* org.wseresearch.methodaspect..*(..))"/>
    </concrete-aspect>
  </aspects>
  <weaver options="-verbose">
    <include within="*"/>
  </weaver>
</aspectj>
```

Replace `PACKAGE_AND_CLASS.METHOD` with the fully-qualified failing test method (e.g., `org.apache.logging..SMTPAppenderTest.testDelivery`) and `PACKAGE` with the project's root package wildcard (e.g., `org.apache.logging..*(..)`).

#### 3d. Run the instrumented test

```bash
mvn test -Dtest=<FailingTestClass>#<failingTestMethod>
```

Maven loads the AspectJ weaving agent at JVM startup; the `methodaspect` aspect intercepts every method call during the test run and writes the caller–callee pairs to Virtuoso under a named graph URI derived from the branch name.

## Common Issues

- **Plugin-side failures**: Caused by JDK version incompatibility. Ensure JDK 6 is active (see [`maven3.2.5-jdk6/README.md`](maven3.2.5-jdk6/README.md)).
- **Invalid class file definitions**: Usually due to newer bytecode versions. Verified resolved with JDK 6.
- **TLS errors during dependency download**: Requires a TLS 1.2 compatible JDK 6 build (standard JDK 6 only supports TLS 1.0).
- **AspectJ weaving failures**: Some projects could not be traced due to runtime incompatibilities between the AspectJ weaving agent and specific test execution environments, or mismatches between abstract and concrete aspect class definitions. Further investigation may resolve this, but is time-consuming.
