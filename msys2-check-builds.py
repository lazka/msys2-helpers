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

"""Reports packages which need to be rebuild"""

from __future__ import print_function

import os
import sys
import argparse
import subprocess
import hashlib
from multiprocessing.pool import ThreadPool
from multiprocessing import cpu_count


DIR = os.path.dirname(os.path.realpath(__file__))


def _get_cached(pkgbuild_path):
    try:
        os.mkdir(os.path.join(DIR, "_srcinfocache"))
    except OSError:
        pass

    with open(pkgbuild_path, "rb") as f:
        h = hashlib.new("SHA1")
        h.update(f.read())
        digest = h.hexdigest()

    cache_path = os.path.join(DIR, "_srcinfocache", digest)
    if not os.path.exists(cache_path):
        try:
            data = subprocess.check_output(
                ["bash", "/usr/bin/makepkg-mingw", "--printsrcinfo", "-p",
                 os.path.basename(pkgbuild_path)],
                cwd=os.path.dirname(pkgbuild_path),
                stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print(
                "ERROR: %s %s" % (pkgbuild_path, e.output.splitlines()),
                file=sys.stderr)
            return

        with open(cache_path, "wb") as f:
            f.write(data)

    with open(cache_path, "rb") as f:
        return f.read()


def get_pkgbuild_versions(pkgbuild_path):
    packages = {}

    data = _get_cached(pkgbuild_path)
    if data is None:
        return pkgbuild_path, packages
    text = data.decode("utf-8")

    pkgver = None
    pkgrel = None
    epoch = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("pkgver = "):
            pkgver = line.split(" = ", 1)[-1]
        elif line.startswith("pkgrel = "):
            pkgrel = line.split(" = ", 1)[-1]
        elif line.startswith("epoch = "):
            epoch = line.split(" = ", 1)[-1]
        elif line.startswith("pkgname = "):
            pkgname = line.split(" = ", 1)[-1]
            version = "%s-%s" % (pkgver, pkgrel)
            if epoch:
                version = "%s~%s" % (epoch, version)
            packages[pkgname] = version
    return pkgbuild_path, packages


def iter_all_pkgbuilds(repo_path):

    pkgbuild_paths = []
    if os.path.isfile(repo_path) and os.path.basename(repo_path) == "PKGBUILD":
        pkgbuild_paths.append(repo_path)
    else:
        for base, dirs, files in os.walk(repo_path):
            for f in files:
                if f == "PKGBUILD":
                    # in case we find a PKGBUILD, don't go deeper
                    del dirs[:]
                    path = os.path.join(base, f)
                    pkgbuild_paths.append(path)
        pkgbuild_paths.sort()

    if not pkgbuild_paths:
        print("No PKGBUILD files found here", file=sys.stderr)
        return
    else:
        print("Found %d PKGBUILD files" % len(pkgbuild_paths), file=sys.stderr)

    pool = ThreadPool(cpu_count() * 2)
    pool_iter = pool.imap_unordered(get_pkgbuild_versions, pkgbuild_paths)
    for i, (p, v) in enumerate(pool_iter):
        print("%d/%d" % (i + 1, len(pkgbuild_paths)), file=sys.stderr)
        for name, version in v.items():
            yield (p, name, version)
    pool.close()
    pool.join()


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path", help="path to the directory containg PKGBUILD files or a "
                     "PKGBUILD file itself")
    args = parser.parse_args(argv[1:])

    pkgbuilds_in_repo = {}
    text = subprocess.check_output(["pacman", "-Sl"]).decode("utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        package_name, version = line.split()[1:3]
        pkgbuilds_in_repo[package_name] = version

    repo_path = os.path.abspath(args.path)
    for path, name, version in iter_all_pkgbuilds(repo_path):
        if name not in pkgbuilds_in_repo:
            print("NOT IN REPO: %s (%s)" % (name, path))
        else:
            repo_version = pkgbuilds_in_repo[name]
            if version != repo_version:
                print("DIFFERENTE VERSION: %s local=%s repo=%s (%s)" % (
                    name, version, repo_version, path))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
