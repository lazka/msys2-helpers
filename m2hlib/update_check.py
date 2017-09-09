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

from .utils import package_name_is_vcs, progress, version_is_newer_than
from .pacman import PacmanPackage
from .srcinfo import iter_packages


def msys2_package_should_skip(package_name):
    """If the package should not be checked.

    Args:
        package_name (str): The msys2 package name suffix
    Returns:
        bool: If the package should be ignored
    """

    if package_name.startswith("mingw-w64-i686-"):
        package_name = package_name.split("-", 3)[-1]

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


def package_get_arch_name(package_name):
    """
    Args:
        package_name (str): The msys2 package name suffix
    Returns:
        str: The Arch package name
    """

    if package_name.startswith("mingw-w64-i686-"):
        package_name = package_name.split("-", 3)[-1]

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
        "gtksourceviewmm3": "gtksourceviewmm",
        "librest": "rest",
        "gcc-libgfortran": "gcc-fortran",
        "meld3": "meld",
    }

    if package_name in mapping:
        return mapping[package_name]

    if package_name.startswith("python3-"):
        package_name = package_name.replace("python3-", "python-")

    return package_name.lower()


def _fetch_version(args):
    name, = args
    arch_name = package_get_arch_name(name)

    import requests

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

    def set_version(name, ver, url):
        if name in versions:
            old_ver = versions[name][0]
            if version_is_newer_than_lax(ver, old_ver):
                versions[name] = (ver, url)
        else:
            versions[name] = (ver, url)

    for result in results:
        url = build_url(result)
        set_version(arch_name, result["pkgver"], url)
        for vs in result["provides"]:
            if "=" in vs:
                prov_name, ver = vs.split("=", 1)
                ver = ver.rsplit("-", 1)[0]
                set_version(prov_name, ver, url)
            else:
                set_version(vs, result["pkgver"], url)

    if versions:
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


def extract_upstream_version(version):
    """Given a package version, try to extract the upstream one"""

    return version.rsplit(
        "-")[0].split("+", 1)[0].split("~", 1)[-1].split(":", 1)[-1]


def add_parser(subparsers):
    parser = subparsers.add_parser("updatecheck",
        help="Compares package versions in the package database against "
             "versions in the Arch Linux distribution and reports out of date "
             "ones")
    parser.add_argument('repo_path', nargs='?',
        help="Optional path to a PKGBUILD repo. Uses the versions of the "
             "PKGBUILD files instead of the database if given.")
    parser.add_argument("--all", help="check all packages",
                        action="store_true")
    parser.set_defaults(func=main)


def version_is_newer_than_lax(a, b):
    # workaround for 2.28 not matching 2.28.0, while there is a difference
    if b == a + ".0":
        a += ".0"
    if a == b + ".0":
        b += ".0"
    return version_is_newer_than(a, b)


def main(args):
    if args.all:
        packages = PacmanPackage.get_all_packages()
    else:
        packages = PacmanPackage.get_installed_packages()

    packages = [p for p in packages if p.repo == "mingw32" and not p.is_vcs
                and not msys2_package_should_skip(p.pkgname)]

    if args.repo_path is not None:
        repo_path = os.path.abspath(args.repo_path)
        new_packages = []
        package_names = set([p.pkgname for p in packages])
        for package in iter_packages(repo_path):
            if package.pkgname in package_names:
                new_packages.append(package)
        packages = new_packages

    work_items = [(p.pkgname,) for p in packages]
    pool = ThreadPool(20)
    arch_versions = {}
    pool_iter = pool.imap_unordered(_fetch_version, work_items)

    print("Fetching versions...")
    with progress(len(work_items)) as update:
        for i, some_versions in enumerate(pool_iter):
            update(i + 1)
            arch_versions.update(some_versions)
    pool.close()
    pool.join()

    print("%-30s %-20s %-20s %s" % ("Name", "Local", "Arch", "Arch Package"))
    print("%-30s %-20s %-20s %s" % ("-" * 30, "-" * 20 , "-" * 20, "-" * 20))
    for p in sorted(packages, key=lambda p: p.pkgname):
        arch_name = package_get_arch_name(p.pkgname)
        arch_info = arch_versions.get(arch_name)
        pkgver = extract_upstream_version(p.pkgver)
        if arch_info is not None:
            arch_version, arch_url = arch_info
            arch_version = extract_upstream_version(arch_version)
            if not version_is_newer_than_lax(arch_version, pkgver):
                continue
        else:
            arch_version = "???"
            arch_url = ""

        print("%-30s %-20s %-20s %s" % (
            p.pkgname.split("-", 3)[-1], pkgver, arch_version, arch_url))
