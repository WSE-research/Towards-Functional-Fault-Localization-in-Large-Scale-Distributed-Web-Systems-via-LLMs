# Scripts (Bug Branch Source Trees)

This directory contains a subset of checked-out bug branch source trees from the [bugs-dot-jar](https://github.com/bugs-dot-jar/bugs-dot-jar) dataset. These are the actual project directories compiled and tested during Steps 3 and 4 of the pipeline.

Not all branches present here resulted in a final experiment — some were excluded due to the described problems, missing suitable tests, or aborted processes as the call graph would be extremely large.

## Relation to Other Directories

- Per-branch analysis artifacts (`analysis.json`, `developer-patch.diff`, `test-results.txt`) are stored in [`outputs/`](../outputs/)
- The list of branches with suitable tests is maintained in [`data/working-examples-jdk6-with-suitable-tests.txt`](../data/working-examples-jdk6-with-suitable-tests.txt)
- Setup instructions for the JDK 6 + Maven environment used to compile these branches are in [`setup/`](../setup/)
