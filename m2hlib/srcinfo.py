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

import sys
import os
import json
import threading
from collections import OrderedDict
import hashlib
import subprocess


class SrcInfoPool(object):

    def __init__(self):
        self._packages = {}

    def add_package(self, package):
        name = package.pkgname
        self._packages.setdefault(name, set()).add(package)

    def get_transitive_dependencies(self, package):
        packages_todo = set([package])
        packages_done = set()
        deps = set()

        while packages_todo:
            p = packages_todo.pop()
            packages_done.add(p)
            new_deps = set(p.depends + p.makedepends)
            deps.update(new_deps)
            for d in new_deps:
                for new_p in self._packages.get(d, set()):
                    if new_p not in packages_done:
                        packages_todo.add(new_p)
        return deps


class SrcInfoPackage(object):

    def __init__(self, pkgbuild_path, pkgname, pkgver, pkgrel):
        self.pkgbuild_path = pkgbuild_path
        self.pkgname = pkgname
        self.pkgver = pkgver
        self.pkgrel = pkgrel
        self.epoch = None
        self.depends = []
        self.makedepends = []

    def __repr__(self):
        return "<%s %s %s>" % (
            type(self).__name__, self.pkgname, self.build_version)

    @property
    def build_version(self):
        version = "%s-%s" % (self.pkgver, self.pkgrel)
        if self.epoch:
            version = "%s~%s" % (self.epoch, version)
        return version

    @classmethod
    def for_srcinfo(cls, pkgbuild_path, srcinfo):
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
                package = cls(pkgbuild_path, pkgname, pkgver, pkgrel)
                package.epoch = epoch
                package.depends = depends
                package.makedepends = makedepends
                packages.add(package)

        return packages

    @classmethod
    def for_pkgbuild(cls, pkgbuild_path):
        packages = set()

        srcinfo = get_srcinfo_for_pkgbuild(pkgbuild_path)
        if srcinfo is None:
            return packages

        packages.update(cls.for_srcinfo(pkgbuild_path, srcinfo))
        return packages


DIR = os.path.dirname(os.path.realpath(__file__))
CACHE = OrderedDict()
CACHE_LOCK = threading.Lock()


def _load_cache():
    with CACHE_LOCK:
        if CACHE:
            return
        try:
            with open(os.path.join(DIR, "_srcinfocache.json"), "rb") as h:
                cache = json.loads(h.read(), object_pairs_hook=OrderedDict)
        except EnvironmentError:
            return
        CACHE.update(cache)


def _save_cache():
    with CACHE_LOCK:
        with open(os.path.join(DIR, "_srcinfocache.json"), "wb") as h:
            cache = OrderedDict(sorted(CACHE.items()))
            h.write(json.dumps(cache, indent=2).encode("utf-8"))


def get_srcinfo_for_pkgbuild(pkgbuild_path):
    """Given a path to a PKGBUILD file returns the srcinfo text

    Args:
        pkgbuild_path (str): Path to PKGBUILD
    Return:
        str or None: srcinfo text or None in case it failed.
    """

    with open(pkgbuild_path, "rb") as f:
        h = hashlib.new("SHA1")
        h.update(f.read())
        digest = h.hexdigest()

    _load_cache()

    with CACHE_LOCK:
        text = CACHE.get(digest)

    if text is None:
        try:
            text = subprocess.check_output(
                ["bash", "/usr/bin/makepkg-mingw", "--printsrcinfo", "-p",
                 os.path.basename(pkgbuild_path)],
                cwd=os.path.dirname(pkgbuild_path),
                stderr=subprocess.STDOUT).decode("utf-8")
        except subprocess.CalledProcessError as e:
            print(
                "ERROR: %s %s" % (pkgbuild_path, e.output.splitlines()),
                file=sys.stderr)
            return

        with CACHE_LOCK:
            CACHE[digest] = text

        _save_cache()

    return text
