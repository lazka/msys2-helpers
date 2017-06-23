#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2017 Christoph Reiter
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE

"""
Tool which searches for missing shared library dependencies
"""

from __future__ import print_function

import subprocess
import os
import sys
import argparse


def get_required_by_typelibs(root):
    deps = set()

    try:
        subprocess.check_output(["g-ir-inspect", "-h"])
    except OSError:
        # not installed
        return deps

    typelib_dir = os.path.join(root, "lib", "girepository-1.0")
    for entry in os.listdir(typelib_dir):
        namespace, version = os.path.splitext(entry)[0].split("-", 1)
        output = subprocess.check_output(
            ["g-ir-inspect", namespace, "--version", version,
             "--print-shlibs"]).decode("utf-8")
        for line in output.splitlines():
            if line.startswith("shlib:"):
                lib = line.split(":", 1)[-1].strip()
                deps.add((namespace, version, lib))
    return deps


def get_dependencies(filename):
    deps = []
    try:
        data = subprocess.check_output(["objdump", "-p", filename],
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        # can happen with wrong arch binaries
        return []
    data = data.decode("utf-8")
    for line in data.splitlines():
        line = line.strip()
        if line.startswith("DLL Name:"):
            deps.append(line.split(":", 1)[-1].strip().lower())
    return deps



def get_lib_path(root, name):
    search_path = os.path.join(root, "bin")
    if os.path.exists(os.path.join(search_path, name)):
        return os.path.join(search_path, name)


def find_lib(root, name):
    system_search_path = os.path.join("C:", os.sep, "Windows", "System32")
    if get_lib_path(root, name):
        return True
    elif os.path.exists(os.path.join(system_search_path, name)):
        return True
    elif name in ["gdiplus.dll"]:
        return True
    elif name.startswith("msvcr"):
        return True
    return False


def check_deps(root):
    extensions = [".exe", ".pyd", ".dll"]

    for base, dirs, files in os.walk(root):
        for f in files:
            path = os.path.join(base, f)
            ext_lower = os.path.splitext(f)[-1].lower()
            if ext_lower in extensions:
                for lib in get_dependencies(path):
                    if not find_lib(root, lib):
                        print("MISSING:", path, "->", lib)

    for namespace, version, lib in get_required_by_typelibs(root):
        if not find_lib(root, lib):
            print("MISSING:", "GIR", namespace, version, lib)


def main(argv):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv[1:])

    check_deps(sys.prefix)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
