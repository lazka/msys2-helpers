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
from multiprocessing.pool import ThreadPool

from .utils import progress


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
            deps.append(line.split(":", 1)[-1].strip())
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
    elif name.lower() in ["gdiplus.dll"]:
        return True
    elif name.lower().startswith("msvcr"):
        return True
    return False


pkgfile_is_updated = False
pkgfile_cache = {}


def get_packages_for_lib(path_or_name):
    """Uses pkgfile to get the package for a specific file

    Args:
        path_or_name (str): Either a basename or an absolute path
    Returns:
        set(str): A set of packages containing the file
    """

    global pkgfile_is_updated

    if path_or_name in pkgfile_cache:
        return pkgfile_cache[path_or_name]

    if not pkgfile_is_updated:
        subprocess.check_output(["pkgfile", "-u"])
        pkgfile_is_updated = True

    # convert an absolute path to something pkgfile understands
    if os.path.isabs(path_or_name):
        base = os.path.dirname(sys.prefix)
        path_or_name = os.sep + os.path.relpath(path_or_name, base)
    else:
        if os.path.basename(path_or_name) != path_or_name:
            raise ValueError("only a basename or absolute path allowed")

    try:
        text = subprocess.check_output(
            ["pkgfile", path_or_name]).decode("utf-8")
    except subprocess.CalledProcessError:
        packages = set()
    else:
        packages = set()
        for line in text.splitlines():
            if not line.strip():
                continue
            packages.add(line.split("-", 3)[-1])

    pkgfile_cache[path_or_name] = packages
    return packages


def _thread_get_deps(path):
    return path, get_dependencies(path)


def main(args):
    root = sys.prefix
    extensions = [".exe", ".pyd", ".dll"]

    print("Collecting files in %s..." % root)
    paths_to_check = []
    for base, dirs, files in os.walk(root):
        for f in files:
            path = os.path.join(base, f)
            ext_lower = os.path.splitext(f)[-1].lower()
            if ext_lower not in extensions:
                continue
            paths_to_check.append(path)

    print("Collecting dependencies...")
    to_check = []
    pool = ThreadPool()
    pool_iter = pool.imap_unordered(_thread_get_deps, paths_to_check)
    with progress(len(paths_to_check)) as update:
        for i, (path, deps) in enumerate(pool_iter):
            update(i + 1)
            for lib in deps:
                to_check.append((path, lib))
    pool.close()
    pool.join()

    print("Collecting GIR dependencies...")
    for namespace, version, lib in get_required_by_typelibs(root):
        to_check.append(("%s-%s.typelib" % (namespace, version), lib))

    print("Verifying dependencies...")
    missing = []
    with progress(len(to_check)) as update:
        for i, (path, lib) in enumerate(to_check):
            update(i + 1)
            if not find_lib(root, lib):
                missing.append(
                    (path, get_packages_for_lib(path),
                     lib, get_packages_for_lib(lib)))

    def pkg_list(pkgs):
        return ", ".join(pkgs) or "???"

    for path, path_pkgs, lib, lib_pkgs in missing:
        print("MISSING: %s (%s) -> %s (%s)" % (
            path, pkg_list(path_pkgs),lib, pkg_list(lib_pkgs)))


def add_parser(subparsers):
    parser = subparsers.add_parser("dll-check",
        help="Searches for missing dependencies")
    parser.add_argument("--all", help="check all packages",
                        action="store_true")
    parser.set_defaults(func=main)
