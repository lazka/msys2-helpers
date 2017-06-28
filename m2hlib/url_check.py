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


from __future__ import print_function

import os
from multiprocessing.pool import ThreadPool

import requests

from .srcinfo import iter_packages
from .utils import progress
from .pacman import PacmanPackage


def add_parser(subparsers):
    parser = subparsers.add_parser("urlcheck",
        help="Checks if the source URLs of all packages are still reachable")
    parser.add_argument(
        "path", help="path to the directory containg PKGBUILD files or a "
                     "PKGBUILD file itself")
    parser.add_argument('--all', action='store_true',
                        help="Also check packages which are not in the "
                             "package database")
    parser.set_defaults(func=main)


def source_get_url(source):
    if "::" in source:
        source = source.split("::", 1)[-1]
    if source.startswith(("https:", "http:")):
        return source


def _check_url(args):
    url, pkgbuilds = args

    try:
        r = requests.get(url, timeout=10, stream=True)
        try:
            r.raise_for_status()
        finally:
            r.close()
    except Exception as e:
        return url, pkgbuilds, str(e)
    return url, pkgbuilds, ""


def main(args):
    sources = {}
    repo_path = os.path.abspath(args.path)

    repo_packages = PacmanPackage.get_all_packages()
    repo_package_names = set(p.pkgname for p in repo_packages)

    for package in iter_packages(repo_path):
        # only check packages which are in the repo, all others are many
        # times broken in other ways.
        if not args.all and package.pkgname not in repo_package_names:
            continue
        for source in package.sources:
            url = source_get_url(source)
            if url:
                sources.setdefault(url, set()).add(package.pkgbuild_path)

    print("Checking URLs...")
    work_items = sources.items()
    pool = ThreadPool(50)
    pool_iter = pool.imap_unordered(_check_url, work_items)
    broken = []
    with progress(len(work_items)) as update:
        for i, (url, pkgbuilds, error) in enumerate(pool_iter):
            update(i + 1)
            if error:
                broken.append((url, pkgbuilds, error))
    pool.close()
    pool.join()

    for url, pkgbuilds, error in broken:
        print("\n%s\n   %s\n   %s" % (
            url, " ".join(error.splitlines()), ", ".join(pkgbuilds)))
