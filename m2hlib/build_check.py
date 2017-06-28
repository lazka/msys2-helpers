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

from .utils import package_name_is_vcs, version_is_newer_than
from .srcinfo import iter_packages
from .pacman import PacmanPackage


def add_parser(subparsers):
    parser = subparsers.add_parser("buildcheck",
        help="Compares the package versions of PKGBUILD files with the "
             "versions in the database and reports packages which need to "
             "be build/updated")
    parser.add_argument(
        "path", help="path to the directory containg PKGBUILD files or a "
                     "PKGBUILD file itself")
    parser.add_argument('--show-missing', action='store_true',
                        help="show packages not in the repo")
    parser.add_argument('--show-vcs', action='store_true',
                        help="show VCS packages")
    parser.set_defaults(func=main)


def main(args):
    repo_path = os.path.abspath(args.path)

    repo_packages = PacmanPackage.get_all_packages()
    repo_packages = dict((p.pkgname, p) for p in repo_packages)

    packages_todo = set()
    for package in iter_packages(repo_path):
        if not args.show_vcs and package_name_is_vcs(package.pkgname):
            continue
        if package.pkgname not in repo_packages:
            if args.show_missing:
                packages_todo.add(package)
        else:
            repo_pkg = repo_packages[package.pkgname]
            if version_is_newer_than(package.build_version,
                                     repo_pkg.build_version):
                packages_todo.add(package)

    for package in sorted(packages_todo, key=lambda p: p.pkgname):
        if package.pkgname not in repo_packages:
            print("%-50s local=%-25s db=%-25s %s" % (
                package.pkgname, package.build_version, "missing",
                package.pkgbuild_path))
        else:
            repo_pkg = repo_packages[package.pkgname]
            print("%-50s local=%-25s db=%-25s %s" % (
                package.pkgname, package.build_version, repo_pkg.build_version,
                package.pkgbuild_path))
