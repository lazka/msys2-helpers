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

from __future__ import print_function

import subprocess
import sys
import argparse
from multiprocessing.pool import ThreadPool

import requests

from m2hlib import package_name_is_vcs


def msys2_package_should_skip(package_name):
    """If the package should not be checked.

    Args:
        package_name (str): The msys2 package name suffix
    Returns:
        bool: If the package should be ignored
    """

    if package_name_is_vcs(package_name):
        return True

    # These packages will never be in Arch
    skip = [
        "windows-default-manifest",
        "wineditline",
        "libsystre",
        "wintab-sdk",
        "xpm-nox",
        "flexdll",
        "winsparkle",
    ]

    if package_name in skip:
        return True

    return False


def msys2_get_mingw_packages(installed_only):
    """
    Args:
        installed_only (bool): If only currently installed packages should be
            checked
    Returns:
        list(tuple(str, str)): A list of package name, version tuples.
    """

    v = {}
    if installed_only:
        cmd = ["pacman", "-Q"]
    else:
        cmd = ["pacman", "-Sl"]
    for line in subprocess.check_output(cmd).decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if not installed_only:
            line = line.split(" ", 1)[-1]
        line = line.rsplit("[", 1)[0]
        name, version = line.split()
        if not name.startswith("mingw-w64-"):
            continue
        name = name.split("-", 3)[-1]
        version = version.rsplit("-", 1)[0]
        if package_name_is_vcs(name):
            continue
        v[name] = version
    return sorted(list(v.items()))


def package_get_arch_name(package_name):
    """
    Args:
        package_name (str): The msys2 package name suffix
    Returns:
        str: The Arch package name
    """

    mapping = {
        "freetype": "freetype2",
        "lzo2": "lzo",
        "python2-bsddb3": "python2-bsddb",
        "graphite2": "graphite",
        "mpc": "libmpc",
        "eigen3": "eigen",
        "python2-icu": "python2-pyicu",
        "python3-icu": "python-pyicu",
        "python3-bsddb3": "python-bsddb",
        "python3": "python",
        "sqlite3": "sqlite",
        "gexiv2": "libgexiv2",
        "webkitgtk3": "webkitgtk",
        "python2-nuitka": "nuitka",
        "python2-ipython": "ipython",
        "openssl": "openssl-1.0",
    }

    if package_name in mapping:
        return mapping[package_name]

    if package_name.startswith("python3-"):
        package_name = package_name.replace("python3-", "python-")

    return package_name.lower()


def version_is_newer_than(v1, v2):
    """
    Args:
        v1 (str): 1st version
        v2 (str): 2nd version
    Returns:
        boolean: True if v1 is newer than v2
    """

    assert v1 and v2
    return int(
        subprocess.check_output(["vercmp", v1, v2]).decode("ascii")) == 1


def _fetch_version(args):
    name, = args
    arch_name = package_get_arch_name(name)

    # First try to get the package by name
    r = requests.get("https://www.archlinux.org/packages/search/json",
                     params={"name": arch_name})
    if r.status_code == 200:
        results = r.json()["results"]
    else:
        results = []

    def build_url(r):
        return "https://www.archlinux.org/packages/%s/%s/%s" % (
            r["repo"], r["arch"], r["pkgname"])

    versions = {}
    for result in results:
        url = build_url(result)
        versions[arch_name] = (result["pkgver"], url)
        for vs in result["provides"]:
            if "=" in vs:
                prov_name, ver = vs.split("=", 1)
                ver = ver.rsplit("-", 1)[0]
                versions[prov_name] = (ver, url)
            else:
                versions[vs] = (result["pkgver"], url)
        return versions

    # If all fails, search the AUR
    r = requests.get("https://aur.archlinux.org/rpc.php", params={
        "v": "5", "type": "search", "by": "name", "arg": arch_name})
    if r.status_code == 200:
        results = r.json()["results"]
    else:
        results = []

    for result in results:
        if result["Name"] == arch_name:
            url = "https://aur.archlinux.org/packages/%s" % result["Name"]
            return {arch_name: (result["Version"].rsplit("-", 1)[0], url)}
    
    return {}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", help="check all packages",
                        action="store_true")
    args = parser.parse_args(argv[1:])

    packages = msys2_get_mingw_packages(installed_only=not args.all)

    work_items = []
    for name, version in packages:
        work_items.append((name,))

    pool = ThreadPool(15)
    arch_versions = {}
    pool_iter = pool.imap(_fetch_version, work_items)
    for i, some_versions in enumerate(pool_iter):
        print("%d/%d" % (i + 1, len(work_items)), file=sys.stderr)
        arch_versions.update(some_versions)
    pool.close()
    pool.join()

    print("#" * 80, file=sys.stderr)
    for name, version in packages:
        arch_name = package_get_arch_name(name)
        arch_info = arch_versions.get(arch_name)
        if arch_info is not None:
            arch_version, arch_url = arch_info
            if not version_is_newer_than(arch_version, version):
                continue
        else:
            if msys2_package_should_skip(name):
                continue
            arch_version = "???"
            arch_url = ""

        print("%-30s %-20s %-20s %s" % (name, version, arch_version, arch_url))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
