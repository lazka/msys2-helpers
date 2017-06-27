Some maintenance helper scripts for MSYS2. Works with Python 2 or 3.

Depends on the stdlib and the requests module.

In mintty things aren't line buffered for some reason, so best use the "-u"
switch: python2 -u m2h.py

::

    $ python2 -u m2h.py --help
    usage: m2h.py [-h] {buildcheck,updatecheck,dllcheck,urlcheck,build} ...

    Provides various tools for automating maintainance work for the MSYS2
    repositories

    optional arguments:
      -h, --help            show this help message and exit

    subcommands:
      {buildcheck,updatecheck,dllcheck,urlcheck,build}
        buildcheck          Compares the package versions of PKGBUILD files with
                            the versions in the database and reports packages
                            which need to be build/updated
        updatecheck         Compares package versions in the package database
                            against versions in the Arch Linux distribution and
                            reports out of date ones
        dllcheck            Searches for missing DLL dependencies
        urlcheck            Checks if the source URLs of all packages are still
                            reachable
        build               Auto builds PKGBUILD files where the packages in the
                            database are out of date. Builds them in the right
                            order according to their dependency relation.

