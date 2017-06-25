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
import subprocess
from multiprocessing.pool import ThreadPool
from multiprocessing import cpu_count

from .utils import get_srcinfo_for_pkgbuild, package_name_is_vcs, progress


class cached_property(object):
    """A read-only @property that is only evaluated once."""

    def __init__(self, fget, doc=None):
        self.fget = fget
        self.__doc__ = doc or fget.__doc__
        self.__name__ = name = fget.__name__
        # these get name mangled, so caching wont work unless
        # we mangle too
        assert not (name.startswith("__") and not name.endswith("__")), \
            "can't cache a dunder method"

    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = result = self.fget(obj)
        return result


class Package(object):

    __packages = {}

    def __init__(self, pkgbuild_path, pkgname, pkgver, pkgrel):
        self.pkgbuild_path = pkgbuild_path
        self.pkgname = pkgname
        self.pkgver = pkgver
        self.pkgrel = pkgrel
        self.epoch = None
        self.depends = []
        self.makedepends = []

        # There can be more than one package with the same name, we can't be
        # sure which one is in the repo..
        self.__packages.setdefault(pkgname, set()).add(self)

    def __repr__(self):
        return "<%s %s %s>" % (
            type(self).__name__, self.pkgname, self.build_version)

    @classmethod
    def by_name(cls, pkgname):
        return cls.__packages.get(pkgname, set())

    @cached_property
    def transitive_dependencies(self):
        """Returns a set of transitive dependencies for this package"""

        packages_todo = set([self])
        packages_done = set()
        deps = set()

        while packages_todo:
            p = packages_todo.pop()
            packages_done.add(p)
            new_deps = set(p.depends + p.makedepends)
            deps.update(new_deps)
            for d in new_deps:
                for new_p in self.by_name(d):
                    if new_p not in packages_done:
                        packages_todo.add(new_p)
        return deps

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


def iter_packages(repo_path):

    pkgbuild_paths = []
    if os.path.isfile(repo_path) and os.path.basename(repo_path) == "PKGBUILD":
        pkgbuild_paths.append(repo_path)
    else:
        print("Searching for PKGBUILD files in %s" % repo_path)
        for base, dirs, files in os.walk(repo_path):
            for f in files:
                if f == "PKGBUILD":
                    # in case we find a PKGBUILD, don't go deeper
                    del dirs[:]
                    path = os.path.join(base, f)
                    pkgbuild_paths.append(path)
        pkgbuild_paths.sort()

    if not pkgbuild_paths:
        print("No PKGBUILD files found here")
        return
    else:
        print("Found %d PKGBUILD files" % len(pkgbuild_paths))

    pool = ThreadPool(cpu_count() * 2)
    pool_iter = pool.imap_unordered(get_packages_for_pkgbuild, pkgbuild_paths)
    print("Parsing PKGBUILD files...")
    with progress(len(pkgbuild_paths)) as update:
        for i, packages in enumerate(pool_iter):
            update(i + 1)
            for package in packages:
                yield package
    pool.close()
    pool.join()


def get_packages_in_repo():
    pkgbuilds_in_repo = {}
    text = subprocess.check_output(["pacman", "-Sl"]).decode("utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        package_name, version = line.split()[1:3]
        pkgbuilds_in_repo[package_name] = version
    return pkgbuilds_in_repo


def print_build_order(packages_todo, pkgbuilds_in_repo):

    pkgbuilds = {}
    for package in packages_todo:
        pkgbuilds.setdefault(package.pkgbuild_path, set()).add(package)

    # now sort the pkgbuilds by the dependencies of the contained packages

    try:
        cmp
    except NameError:
        cmp = lambda a, b: (a > b) - (a < b)

    def cmp_func(aa, bb):
        """Takes two sets of packages ands sorts according to their
        dependencies.
        """

        at = set()
        for a in aa:
            a_name = a.pkgname
            at.update(a.transitive_dependencies)

        bt = set()
        for b in bb:
            b_name = b.pkgname
            bt.update(b.transitive_dependencies)

        # make the result deterministic, packages with fewer dependencies first
        a_key = (len(at), a_name)
        b_key = (len(bt), b_name)

        if a_name in bt and b_name in at:
            # cyclic!
            return cmp(a_key, b_key)
        elif a_name in bt:
            return -1
        elif b_name in at:
            return 1
        else:
            return cmp(a_key, b_key)

    real_cmp = lambda a, b: cmp_func(a[1], b[1])

    if sys.version_info[0] == 3:
        from functools import cmp_to_key

        key = cmp_to_key(real_cmp)

        def do_sort(x):
            return sorted(x, key=key)
    else:
        def do_sort(x):
            return sorted(x, cmp=real_cmp)

    order = [i[0] for i in do_sort(pkgbuilds.items())]

    for path in order:
        print(path)


def print_table(packages_todo, pkgbuilds_in_repo):
    for package in sorted(packages_todo, key=lambda p: p.pkgname):
        if package.pkgname not in pkgbuilds_in_repo:
            print("%-50s local=%-25s repo=%-25s %s" % (
                package.pkgname, package.build_version, "missing",
                package.pkgbuild_path))
        else:
            repo_version = pkgbuilds_in_repo[package.pkgname]
            print("%-50s local=%-25s repo=%-25s %s" % (
                package.pkgname, package.build_version, repo_version,
                package.pkgbuild_path))


def add_parser(subparsers):
    parser = subparsers.add_parser("check-builds",
        help="Compares the packages versions of PKGBUILD files with the "
             "versions in the database and reports packages which need to "
             "be build/updated")
    parser.add_argument(
        "path", help="path to the directory containg PKGBUILD files or a "
                     "PKGBUILD file itself")
    parser.add_argument('--show-missing', action='store_true',
                        help="show packages not in the repo")
    parser.add_argument('--show-vcs', action='store_true',
                        help="show VCS packages")
    parser.add_argument('--buildorder', action='store_true',
                        help="List PKGFILES which need to be build in the "
                             "order they need to be build")
    parser.set_defaults(func=main)


def main(args):
    repo_path = os.path.abspath(args.path)

    pkgbuilds_in_repo = get_packages_in_repo()

    packages_todo = set()
    for package in iter_packages(repo_path):
        if not args.show_vcs and package_name_is_vcs(package.pkgname):
            continue
        if package.pkgname not in pkgbuilds_in_repo:
            if args.show_missing:
                packages_todo.add(package)
        else:
            repo_version = pkgbuilds_in_repo[package.pkgname]
            if package.build_version != repo_version:
                packages_todo.add(package)

    if args.buildorder:
        print_build_order(packages_todo, pkgbuilds_in_repo)
    else:
        print_table(packages_todo, pkgbuilds_in_repo)
