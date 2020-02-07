#!/usr/bin/env bash

python3 -m pip install --upgrade .
perf -f test/test.py
