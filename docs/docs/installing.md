---
id: install
title: Installing
---

## From PyPI

Since PyPerf is still in development, this option is not yet usable.

## From Source

To install from source, please first clone the repository from GitHub, enter the cloned directory, and run:

```
pip3 install .
```

which will install the tool with the source code from the `pyperf` directory.
You can edit that source, and then re-run that command to reinstall, and finally,
you can run this command to run the tool against the test file:

```
pyperf -f test.py
```
