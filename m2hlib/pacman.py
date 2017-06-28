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

import subprocess

from .utils import package_name_is_vcs, package_name_get_repo


class PacmanPackage(object):

    def __init__(self, repo, pkgname, version):
        self.repo = repo
        assert package_name_get_repo(pkgname) == repo
        self.pkgname = pkgname
        self.epoch = None
        if "~" in version:
            self.epoch, version = version.split("~", 1)
        self.pkgver, self.pkgrel = version.rsplit("-", 1)

    def __repr__(self):
        return "<%s %s %s>" % (
            type(self).__name__, self.pkgname, self.build_version)

    @property
    def is_vcs(self):
        """bool: If the package is a VCS one"""

        return package_name_is_vcs(self.pkgname)

    @property
    def build_version(self):
        version = "%s-%s" % (self.pkgver, self.pkgrel)
        if self.epoch:
            version = "%s~%s" % (self.epoch, version)
        return version

    @classmethod
    def get_all_packages(cls):
        """Returns a set of packages with the version they are installed
        (not the version they are in the repo)

        Returns:
            set(PacmanPackage)
        """

        pkgbuilds_in_repo = set()
        text = subprocess.check_output(["pacman", "-Sl"]).decode("utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            repo, package_name, version = line.split()[:3]
            if "[installed:" in line:
                version = line.rsplit(":", 1)[-1].strip("]").strip()
            pkgbuilds_in_repo.add(cls(repo, package_name, version))
        return pkgbuilds_in_repo

    @classmethod
    def get_installed_packages(cls):
        """Returns a set of installed packages with the version they are
        installed (not the version they are in the repo)

        Returns:
            set(PacmanPackage)
        """

        text = subprocess.check_output(["pacman", "-Q"]).decode("utf-8")
        installed = set()
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            installed.add(line.split()[0])

        packages = cls.get_all_packages()
        return set([p for p in packages if p.pkgname in installed])
