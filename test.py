# flake8: noqa

import sys
import os
import area4
import string
import click
import importlib
import importlib_metadata
import distutils
import inspect
import bleach
import typing
import keyword
import shelve
import pickle
import profile

helloworld = "\\o/"  # nice little wave

print("hi")

myvar = ""
myvar += "hi world"


def helloworld2():
    global x


list1 = ["hi", "world", "hello"]
list2 = ["sup", "world", "yeehaw"]

for i in list1:
    for x in list2:
        if i == x:
            print("DUPE!!")
