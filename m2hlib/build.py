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

from .srcinfo import SrcInfoPool, iter_packages
from .pacman import PacmanPackage


def get_pkgbuilds_to_build_in_order(packages_todo):
    """Returns a list of PKGBUILD files in the order they need to be build"""

    pool = SrcInfoPool()
    pkgbuilds = {}
    for package in packages_todo:
        pool.add_package(package)
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
            at.update(pool.get_transitive_dependencies(a))

        bt = set()
        for b in bb:
            b_name = b.pkgname
            bt.update(pool.get_transitive_dependencies(b))

        # make the result deterministic,
        # packages with fewer dependencies first
        a_key = (len(at), a_name)
        b_key = (len(bt), b_name)

        if a_name in bt and b_name in at:
            # cyclic dependency!
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

    return pool, do_sort(pkgbuilds.items())



class BuildError(Exception):
    pass


def build_source(pkgbuild, packages, targetdir):
    """Build source packages

    Returns:
        set(str): The paths to the resulting packages
    Raises:
        BuildError
    """

    targetdir = os.path.abspath(targetdir)
    pkgbuild = os.path.abspath(pkgbuild)

    try:
        output = subprocess.check_output(
            ["bash", "/usr/bin/makepkg", "--noconfirm", "--noprogressbar",
             "--skippgpcheck", "--allsource", "--config",
             "/etc/makepkg_mingw64.conf", "-f",
             "-p", os.path.basename(pkgbuild),
             "SRCPKGDEST=%s" % targetdir],
            cwd=os.path.dirname(pkgbuild),
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output
        raise BuildError(e)
    else:
        tarballs = set()
        for entry in os.listdir(targetdir):
            for p in packages:
                name = "%s-%s" % (p.pkgbase, p.build_version)
                if name in entry and ".src." in entry:
                    tarballs.add(os.path.join(targetdir, entry))
        return tarballs
    finally:
        some_pkg = list(packages)[0]
        target_key = "%s-%s" % (some_pkg.pkgbase, some_pkg.build_version)
        logpath = os.path.join(targetdir, target_key + ".src.log")
        with open(logpath, "wb") as h:
            h.write(output)


def build_and_install_binary(pkgbuild, packages, targetdir):
    """Build binary packages

    Returns:
        set(str): The paths to the resulting packages
    Raises:
        BuildError
    """

    targetdir = os.path.abspath(targetdir)
    pkgbuild = os.path.abspath(pkgbuild)

    try:
        output = subprocess.check_output(
            ["bash", "/usr/bin/makepkg-mingw", "--noconfirm",
             "--noprogressbar", "--skippgpcheck", "--nocheck", "--syncdeps",
             "--rmdeps", "--cleanbuild", "--install", "-f", "--noconfirm",
             "-p", os.path.basename(pkgbuild),
             "PKGDEST=%s" % targetdir],
            cwd=os.path.dirname(pkgbuild),
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output
        raise BuildError(e)
    else:
        tarballs = set()
        for entry in os.listdir(targetdir):
            for p in packages:
                name = "%s-%s" % (p.pkgname, p.build_version)
                if name in entry and ".pkg." in entry:
                    tarballs.add(os.path.join(targetdir, entry))
        return tarballs
    finally:
        some_pkg = list(packages)[0]
        target_key = "%s-%s" % (some_pkg.pkgbase, some_pkg.build_version)
        logpath = os.path.join(targetdir, target_key + ".pkg.log")
        with open(logpath, "wb") as h:
            h.write(output)


def build(pkgbuild, packages, targetdir):
    """Build packages

    Returns:
        set(str): The paths to the resulting packages
    Raises:
        BuildError
    """

    results = set()
    some_pkg = list(packages)[0]
    target_key = "%s-%s" % (some_pkg.pkgbase, some_pkg.build_version)

    targetdir = os.path.abspath(targetdir)
    pkgbuild = os.path.abspath(pkgbuild)
    fail_path = os.path.join(targetdir, "%s.failed" % target_key)

    if os.path.exists(fail_path):
        print("%s found, build aborted. Delete the file to not skip "
              "the build." % fail_path)
        raise BuildError

    try:
        results.update(build_source(pkgbuild, packages, targetdir))
        results.update(
            build_and_install_binary(pkgbuild, packages, targetdir))
    except BuildError:
        open(fail_path, "wb").close()

        # something failed, try to clean up
        for path in results:
            try:
                os.unlink(path)
            except EnvironmentError:
                pass
        raise
    else:
        return results


def add_parser(subparsers):
    parser = subparsers.add_parser("build",
        help="Auto builds PKGBUILD files where the packages in the database "
             "are out of date. Builds them in the right order according to "
             "their dependency relation.")
    parser.add_argument(
        "path", help="path to the directory containg PKGBUILD files or a "
                     "PKGBUILD file itself")
    parser.add_argument(
        "target", help="path to the directory where the build packages will "
                       "be saved to")
    parser.add_argument('--dry-run', action='store_true',
                        help="Only show which packages will be build")
    parser.set_defaults(func=main)


def main(args):
    repo_path = os.path.abspath(args.path)
    target_path = os.path.abspath(args.target)

    repo_packages = PacmanPackage.get_all_packages()
    repo_packages = dict((p.name, p) for p in repo_packages)

    # Find packages which not VCS and which are out of date
    packages_todo = set()
    for package in iter_packages(repo_path):
        if package.is_vcs:
            continue
        if package.pkgname in repo_packages:
            repo_pkg = repo_packages[package.pkgname]
            if package.build_version != repo_pkg.version:
                # TODO
                if not package.pkgname.startswith("mingw-w64-"):
                    raise Exception(
                        "Only mingw builds supported atm, please add "
                        "support! (%s isn't)" % (package.pkgbuild_path,))
                packages_todo.add(package)

    # Sort them according to their dependencies so no package is build
    # before any of its dependencies
    pool, pkgbuilds = get_pkgbuilds_to_build_in_order(packages_todo)

    if args.dry_run:
        for path, packages in pkgbuilds:
            print(path)
            for package in packages:
                print("    -> ", package.pkgname)
        return

    print("%d PKGBUILDs to build" % len(pkgbuilds))

    if pkgbuilds:
        try:
            os.makedirs(target_path)
        except EnvironmentError:
            pass

    failed_packages = set()
    skipped = set()
    for path, packages in pkgbuilds:
        # In case some build failed, check if this one needs to be
        # skipped because it depends on the failed one.
        can_build = True
        reason = set()
        for failed in failed_packages:
            for p in packages:
                if failed in pool.get_transitive_dependencies(p):
                    can_build = False
                    reason.add(failed)
        if not can_build:
            skipped.update(packages)
            print("SKIPPING %s because %s failed" % (path, ", ".join(reason)))
            continue

        # start the build
        print("STARTING %s" % path)
        try:
            build(path, packages, target_path)
        except BuildError:
            print("FAILED")
            failed_packages.update(packages)
        else:
            print("DONE")

    # Final report
    print("All done.")
    if failed_packages:
        print("The following packages failed to build:")
        for p in sorted(failed_packages):
            print(p.pkgname)
        print("As a result, the following packages got skipped:")
        for p in sorted(skipped):
            print(p.pkgname)
