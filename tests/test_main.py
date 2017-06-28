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

from m2hlib import utils, pacman, srcinfo


def test_utils():
    assert not utils.package_name_is_vcs("foo")
    assert utils.package_name_is_vcs("foo-git")

    with utils.progress(1) as update:
        update(1)

    assert utils.version_is_newer_than("2", "1")
    assert utils.version_is_newer_than("2~1", "1~2")
    assert utils.version_is_newer_than("2", "2rc")
    assert utils.version_is_newer_than("1.0-2", "1.0-1")
    assert not utils.version_is_newer_than("1.0-1", "1.0-1")


def test_pacman():
    pacman.PacmanPackage.get_all_packages()
    pacman.PacmanPackage.get_installed_packages()


def test_srcinfo():
    packages = srcinfo.SrcInfoPackage.for_srcinfo("foo", """\
pkgbase = mingw-w64-gtk3
        pkgdesc = GObject-based multi-platform GUI toolkit (v3) (mingw-w64)
        pkgver = 3.22.16
        pkgrel = 1
        url = http://www.gtk.org
        install = gtk3-x86_64.install
        arch = any
        license = LGPL
        makedepends = mingw-w64-x86_64-gcc
        makedepends = mingw-w64-x86_64-pkg-config
        makedepends = mingw-w64-x86_64-python2
        makedepends = mingw-w64-x86_64-gobject-introspection
        makedepends = autoconf
        makedepends = automake
        makedepends = libtool
        depends = mingw-w64-x86_64-gcc-libs
        depends = mingw-w64-x86_64-adwaita-icon-theme
        depends = mingw-w64-x86_64-atk
        depends = mingw-w64-x86_64-cairo
        depends = mingw-w64-x86_64-gdk-pixbuf2
        depends = mingw-w64-x86_64-glib2
        depends = mingw-w64-x86_64-json-glib
        depends = mingw-w64-x86_64-libepoxy
        depends = mingw-w64-x86_64-pango
        depends = mingw-w64-x86_64-shared-mime-info
        options = strip
        options = !debug
        options = staticlibs
        source = https://download.gnome.org/sources/gtk+/3.22/gtk+-3.22.16.tar.xz
        sha256sums = 3e0c3ad01f3c8c5c9b1cc1ae00852bd55164c8e5a9c1f90ba5e07f14f175fe2c

pkgname = mingw-w64-x86_64-gtk3

pkgbase = mingw-w64-gtk3
        pkgdesc = GObject-based multi-platform GUI toolkit (v3) (mingw-w64)
        pkgver = 3.22.16
        pkgrel = 1
        url = http://www.gtk.org
        install = gtk3-i686.install
        arch = any
        license = LGPL
        makedepends = mingw-w64-i686-gcc
        makedepends = mingw-w64-i686-pkg-config
        makedepends = mingw-w64-i686-python2
        makedepends = mingw-w64-i686-gobject-introspection
        makedepends = autoconf
        makedepends = automake
        makedepends = libtool
        depends = mingw-w64-i686-gcc-libs
        depends = mingw-w64-i686-adwaita-icon-theme
        depends = mingw-w64-i686-atk
        depends = mingw-w64-i686-cairo
        depends = mingw-w64-i686-gdk-pixbuf2
        depends = mingw-w64-i686-glib2
        depends = mingw-w64-i686-json-glib
        depends = mingw-w64-i686-libepoxy
        depends = mingw-w64-i686-pango
        depends = mingw-w64-i686-shared-mime-info
        options = strip
        options = !debug
        options = staticlibs
        source = https://download.gnome.org/sources/gtk+/3.22/gtk+-3.22.16.tar.xz
        sha256sums = 3e0c3ad01f3c8c5c9b1cc1ae00852bd55164c8e5a9c1f90ba5e07f14f175fe2c

pkgname = mingw-w64-i686-gtk3
""")

    assert len(packages) == 2
    packages = sorted(packages, key=lambda x: x.pkgname)

    assert packages[0].pkgname == "mingw-w64-i686-gtk3"
    assert packages[1].pkgname == "mingw-w64-x86_64-gtk3"
    assert packages[0].pkgbase == "mingw-w64-gtk3"
    assert "mingw-w64-i686-glib2" in packages[0].depends
    assert "mingw-w64-i686-pkg-config" in packages[0].makedepends
    assert packages[0].build_version == "3.22.16-1"
