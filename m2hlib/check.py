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

from .srcinfo import iter_packages


def add_parser(subparsers):
    parser = subparsers.add_parser("check")
    parser.add_argument("repo_path")
    parser.set_defaults(func=main)



def main(args):
    repo_path = os.path.abspath(args.repo_path)
    packages = list(iter_packages(repo_path))
    nomatch = set()
    for p in packages:
        dirname = os.path.basename(os.path.dirname(p.pkgbuild_path))
        pkgbase = p.pkgbase
        if dirname != pkgbase:
            nomatch.add((p.pkgbuild_path, pkgbase))

    for pkgbuild_path, pkgbase in sorted(nomatch):
        print(pkgbuild_path, "-->", pkgbase)
