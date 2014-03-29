git-results
===========

A helper script / git extension for cataloging computation results

Usage
-----

Simply put git-results somewhere on your PATH.  Then from a git repository, 
type:

    git results -h

to show the tool's help.

At a bare minimum, you need two files in the base of your repository:
git-results-build and git-results-run.  These will not be committed,
and must be executable.  Build and run separation is important because
git-results automatically detects output files for you, and needs to distinguish
between files built as part of the build process and files generated at runtime.
The build step being in git-results is important for repeatability.  Though
these files aren't committed in your repo, their contents are archived in the
git-results-message file in the results folder.

Simplest scenario:

    $ git init
    $ touch git-results-build
    $ echo "echo 'Hello, world'" > git-results-run
    $ chmod a+x git-results-*

    ## -c means it is OK for git results to commit to its own branch.  It will
    ## still make changes to your local tree, but throw an error rather than
    ## commit on its own without -c.
    $ git results -c test/run -m "Let's see if it prints hello, world"
    Building results/test/run/1 in results/tmp/PP3C3DTC...
    Running results/test/run/1 in results/tmp/PP3C3DTC...
    ================================================================================
    ================================================================================
    Hello, world
    ================================================================================
    ================================================================================
    Copying results to results/test/run/1...
    OK

So, what happened there?  git-results created a tag, built your project, ran it,
and tidied all of the output files into a folder for you.  Neat, huh?

Note that it might be easier in e.g. a console to use the -p flag:

    $ git results -cp results/test/run -m "Let's see..."

The -p flag means that the first part of the path is the directory to store
results in.  Without -p this defaults to "results", which can be useful, but
paths do not tab-complete in a console.

For a little more detail, git-results tagged the head commit of your repository
with results/test/run/1 (note test/run comes from our argument; results is the
output folder, and 1 is the instance of this tag being run).  It then checked
out this tag to a temporary folder in order to guarantee build stability and
let you make other changes / start other tests in parallel.  It runs your
git-results-build script, takes a snapshot of the filesystem (only tests
existence, not contents), and then runs your git-results-run command.  The
output of git-results-run is duplicated in the terminal, and also into the
results folder into two files, stdout and stderr.  There is also a
git-results-message file in the results folder, containing the following
information:

    Let's see if it prints hello, world

    Commit: 91aa84e834c3ee6543161b34a95a5478c7ae77f3

    git-results-run
    ---------------
    ./hello_world


    git-results-build
    -----------------


    OK after 0.0212290287018s
    Build took 0.0212380886078s

This includes all essential information about our test - the message you entered
as a comment, the commit hash, the contents of your run and build scripts,
whether the test was successful or not (OK would be FAIL if it had failed),
and how long it took to run the run and build scripts.

Subsequent runs of the same command would create results/test/run/2,
results/test/run/3, etc.

Footnote on copying before building - if one of the files
in your repo were your test parameters, which is what this system is more or
less designed for at the moment, changing it could alter your running test if
builds were in-place).


Special Directories
-------------------

git-results automatically makes "dated" and "latest" folders.

"dated" contains
a folder hierarchy ending in symlinks to the results for experiments, organized
by date.  For instance, results/dated/2014/03/24-test/run/2 would be a symlink
to results/test/run/2.  It's a longer path of course, but it's indexed by date.

"latest" contains a folder hierarchy pointing the the most recent run of a test,
including in progress runs.


Moving / Linking results
------------------------
If you wish to rename a tag at a later date, you can do so with move:

    $ git results move test/run test/run2

This may not be the wisest idea if you are pushing your results to a remote repository, as git tags are relatively immutable on remote machines.  But, it will work locally anyway.

If you simply wish to link results into a new location, use link:

    $ git results link test/run test/run2

It just uses symlinks, meaning the data will not be copied, but subsequent moves will break the links.


Changelog
---------

* 2014-3-27 - "move" and "link" commands
* 2014-3-25 - "latest" special folder to allow access to paths without having
  to tab through the build number.  -run suffix for tests that are in progress.
* 2014-3-22 - -i --in-place flag for in-place builds.  Not recommended for 
  anything other than getting a build working or experiments with very short
  runtimes.
* 2014-3-21 - Print time it took to run in last message, flushes stdout and
  stderr with each line rather than when OS buffer is full.  Tests.  Removed ...
  so double-click works with paths.
* 2014-3-20 - Shared path trimming is opt-in with -t


TODO
----

* Need a move command for reorganizing

* Need a clean command to delete an exact tag an any children of it, also
  cleaning up the git repository, so that a tag can be reused.
"""
