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
import subprocess
from contextlib import contextmanager


def package_name_is_vcs(package_name):
    """
    Args:
        package_name (str)
    Returns:
        bool: If the package is a VCS package
    """

    return package_name.endswith(
        ("-cvs", "-svn", "-hg", "-darcs", "-bzr", "-git"))


def version_cmp(v1, v2):
    """
    Args:
        v1 (str): 1st version
        v2 (str): 2nd version
    Returns:
        int: same as cmp()
    """

    # fast path
    if v1 == v2:
        return 0

    return int(
        subprocess.check_output(["vercmp", v1, v2]).decode("ascii"))


def version_is_newer_than(v1, v2):
    """
    Args:
        v1 (str): 1st version
        v2 (str): 2nd version
    Returns:
        boolean: True if v1 is newer than v2
    """

    assert v1 and v2

    return version_cmp(v1, v2) == 1


@contextmanager
def progress(total):
    width = 70
    last_blocks = [-1]

    def update(current, clear=False):
        blocks = int((float(current) / total) * width)
        if blocks == last_blocks[0] and not clear:
            return
        last_blocks[0] = blocks
        line = "[" + "#" * blocks + " " * (width - blocks) + "]"
        line += (" %%%dd/%%d" % len(str(total))) % (current, total)
        if clear:
            line = " " * len(line)
        sys.stdout.write(line)
        sys.stdout.write("\b" * len(line))
        sys.stdout.flush()

    update(0)
    yield update
    update(0, True)
