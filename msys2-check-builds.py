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
from multiprocessing.pool import ThreadPool
from multiprocessing import cpu_count

from m2hlib import get_srcinfo_for_pkgbuild, package_name_is_vcs


class Package(object):

    def __init__(self, pkgbuild_path, pkgname, pkgver, pkgrel):
        self.pkgbuild_path = pkgbuild_path
        self.pkgname = pkgname
        self.pkgver = pkgver
        self.pkgrel = pkgrel
        self.epoch = None
        self.depends = []
        self.makedepends = []

    @property
    def build_version(self):
        version = "%s-%s" % (self.pkgver, self.pkgrel)
        if self.epoch:
            version = "%s~%s" % (self.epoch, version)
        return version

    @classmethod
    def from_srcinfo(cls, pkgbuild_path, srcinfo):
        packages = set()

        for line in srcinfo.splitlines():
            line = line.strip()
            if line.startswith("pkgbase = "):
                pkgver = pkgrel = epoch = None
                depends = []
                makedepends = []
            elif line.startswith("depends = "):
                depends.append(line.split(" = ", 1)[-1])
            elif line.startswith("makedepends = "):
                makedepends.append(line.split(" = ", 1)[-1])
            elif line.startswith("pkgver = "):
                pkgver = line.split(" = ", 1)[-1]
            elif line.startswith("pkgrel = "):
                pkgrel = line.split(" = ", 1)[-1]
            elif line.startswith("epoch = "):
                epoch = line.split(" = ", 1)[-1]
            elif line.startswith("pkgname = "):
                pkgname = line.split(" = ", 1)[-1]
                package = Package(pkgbuild_path, pkgname, pkgver, pkgrel)
                package.epoch = epoch
                package.depends = depends
                package.makedepends = makedepends
                packages.add(package)

        return packages


def get_packages_for_pkgbuild(pkgbuild_path):
    packages = set()

    srcinfo = get_srcinfo_for_pkgbuild(pkgbuild_path)
    if srcinfo is None:
        return packages

    packages.update(Package.from_srcinfo(pkgbuild_path, srcinfo))
    return packages


def iter_packages(repo_path, show_progress):

    pkgbuild_paths = []
    if os.path.isfile(repo_path) and os.path.basename(repo_path) == "PKGBUILD":
        pkgbuild_paths.append(repo_path)
    else:
        print("Searching for PKGBUILD files in %s" % repo_path,
              file=sys.stderr)
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
    pool_iter = pool.imap_unordered(get_packages_for_pkgbuild, pkgbuild_paths)
    for i, packages in enumerate(pool_iter):
        if show_progress:
            print("%d/%d" % (i + 1, len(pkgbuild_paths)), file=sys.stderr)
        for package in packages:
            yield package
    pool.close()
    pool.join()


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path", help="path to the directory containg PKGBUILD files or a "
                     "PKGBUILD file itself")
    parser.add_argument('--show-missing', action='store_true',
                        help="show packages not in the repo")
    parser.add_argument('--show-progress', action='store_true',
                        help="show progress of parsing PKGBUILD files")
    parser.add_argument('--show-vcs', action='store_true',
                        help="show VCS packages")
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
    show_progress = args.show_progress

    packages = []
    for package in iter_packages(repo_path, show_progress):
        packages.append(package)

    for package in sorted(packages, key=lambda p: p.pkgname):
        if not args.show_vcs and package_name_is_vcs(package.pkgname):
            continue
        if package.pkgname not in pkgbuilds_in_repo:
            if args.show_missing:
                print("%-50s local=%-25s repo=%-25s %s" % (
                    package.pkgname, package.build_version, "missing",
                    package.pkgbuild_path))
        else:
            repo_version = pkgbuilds_in_repo[package.pkgname]
            if package.build_version != repo_version:
                print("%-50s local=%-25s repo=%-25s %s" % (
                    package.pkgname, package.build_version, repo_version,
                    package.pkgbuild_path))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
