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
import subprocess
import hashlib
from collections import OrderedDict
import json
import threading
from contextlib import contextmanager


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


def package_name_is_vcs(package_name):
    """
    Args:
        package_name (str)
    Returns:
        bool: If the package is a VCS package
    """

    return package_name.endswith(
        ("-cvs", "-svn", "-hg", "-darcs", "-bzr", "-git"))


@contextmanager
def progress(total):
    width = 70

    def update(current):
        blocks = int((float(current) / total) * width)
        line = "[" + "#" * blocks + " " * (width - blocks) + "]"
        line += (" %%%dd/%%d" % len(str(total))) % (current, total)
        sys.stdout.write(line)
        sys.stdout.write("\b" * len(line))
        sys.stdout.flush()

    update(0)
    yield update

    sys.stdout.write("\n")
