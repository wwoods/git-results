git-results
===========

A helper script / git extension for cataloguing computation results

Version 0.2.7.

## Installation

Put git-results somewhere on your PATH.  Proper setup can be verified by
running:

    git results -h

to show the tool's help.

## Usage

`git-results` is a tool for organizing and bookmarking experiments locally, so that the exact conditions for each experiment can be remembered and compared intuitively and authoritatively.  In its most basic mode, running `git-results` executes the following steps:

1. Switch to a temporary branch,
* Add all local source changes, and create a commit on the temporary branch with all of your code changes,
* Clone that commit to a temporary folder,
* Execute the build step within that folder\*,
* Snapshot the folder's contents,
* Execute the run step within that folder\*,
* Diff the folder's contents against the original snapshot, moving any new files
  to the specified results directory.

A basic invocation of `git-results` looks like this:

    $ git results results/my/experiment

This will open your favorite text editor (via environment variables `VISUAL` or `EDITOR`, or fallback to `vi`) and prompt for a message further describing the experiment.  After that, `git-results` will do its thing, moving any results files to `results/my/experiment/1` where they are archived.  Note the `/1` at the end of the path!  Every experiment ran through `git-results` is versioned, assisting with iterative development of a single experiment.

\* - Note that the environment used to execute scripts is minimal, and only includes `HOME`, `LOGNAME`, and `LANG`.  This is by design, so that experiments may be more easily replicated.  See the "Environment Configuration" section for a workaround.


## Configuration

`git-results` relies on a special file in your repository named `git-results.cfg`.  This file describes different branches of experiments as well as any configuration options.  The format of the file is similar to an ini; following is an example with documentation for each parameter:

```ini
[vars]
# Values in this section are available in strings in other sections; all
# strings (including those in [vars]) have .format() called on them with the
# values set in [vars] as kwargs.
cmd = "python test.py"

[/results]
# Most sections will start with a / and are parent paths relative to the folder
# containing git-results.cfg for experiments.  At least one entry matching
# any experiments is required.  When more than one path matches, the most
# specific path's parameters are used.

# Vars can be overridden in a sub path
vars = { "cmd": "python test.py arg" }

# Ignore results files from this list of extensions.  This is the default list:
ignoreExt = [ "pyc", "pyo", "swp" ]

# Ignore results files matching this glob (similar to .gitignore files)
# Default is an empty list [].
ignore = [ "*.chkpt*" ]

# Trim result paths aggressively?  False if unspecified.
# That is, if the application creates folder results/a.txt, then since
# results/ is a part of all created files, it will be trimmed (leaving just
# a.txt)
trim = False

# The command to run to build the application.  For python, this would often
# be the help command in order to check for syntax errors.  Note the usage
# of {cmd} to refer to the value from [vars].
#
# The build command is used to separate temporary files from building -
# compiled files, generated data, etc - from reaching the results that are
# copied over.  If unspecified, no build step will be taken.  Often, running
# a makefile or, for python and other interactive languages, running the help
# version of the script to scan for Syntax errors is a good idea.
#
# Executed in the context of git-result's checkout of the project.  Note that
# the special var {tag} can be used to pass the full tag as an argument.
build = "{cmd} --help"

# The command to run that will generate results files.
#
# Executed in the context of git-result's checkout of the project.  Note that
# the special var {tag} can be used to pass the full tag as an argument.
run = "{cmd}"

# Command to get progress; stdout must be a single floating point number that
# is expected to monotonically increase as tangible work is completed.  This
# might be a file timestamp or number of batches calculated, for instance.
#
# If specified, a few things are assumed:
# 1. When this application has a non-zero return code, it is safe to re-run
#     the application until it returns zero.
# 2. Every time this experiment is run, it should be re-run upon crashing until
#     one of:
#     A) The experiment returns zero.
#     B) The value returned by the progress command has not increased after
#        progress-tries consecutive failures of the experiment.
#     C) There should be a gap of progress-delay seconds between any crashing
#        of the experiment and a retry.
# 3. The git-results supervisor is in your crontab.  It should be run every
#    minute as `git results supervisor`.
#
# Executed in the context of git-result's checkout of the project.
progress = "stat -c %Y results.csv 2> /dev/null || echo -1"

# Number of retries without progress before failing the experiment.
progressTries = 3

# Number of seconds between retries.  Must be at least 10.
progressDelay = 30.

[/results/other]
# For /results/other, this run command will be used rather than the one under
# /results.
run = "{cmd} 2"
```


### Environment Configuration

As previously mentioned, scripts ran through `git-results` run in a minimal environment.  If your application or script relies on some `PATH` value, or perhaps on `DISPLAY=:0`, then it is recommended to accomplish this by adding the following section to `git-results.cfg`:

```ini
[vars]
env = "PATH=./bin:$PATH DISPLAY=:0"

[/results/path]
run = "{env} command"
```


## What does `git-results` put in the output folder and the folders above it?

### Meta information
If your `git-results.cfg` file lives at `project/git-results.cfg` relative to your git repository root, then executing an experiment from the `project` folder as `git results results/a` does the following:

1. Establishes a results root in `project/results`.

 The results root is the folder one deeper than the folder containing `git-results.cfg`; in this example, `project` contains `git-results.cfg`, so that folder is the results root.  If this folder is not already treated as a results root, then `git-results` will prompt for confirmation of result root creation.  Results roots are automatically added to the git repository's `.gitignore`.

* Creates a versioned instance of the experiment named `a` in the results root `project/results`.

 Most experiments need to be iteratively refined; `git-results` helps you to manage this by automatically creating subfolders `1`, `2`, etc. for your experiments.  When an experiment completes successfully, these folders will not have a suffix.  However, if they are still running, or the run command returns non-zero (failure), then these subfolders will be renamed to reflect the experiment's ultimate status (`1-run`, or `1-fail`).

* Adds the experiment version to the `INDEX` file.

 Each experiment directory gets a special `INDEX` file that correlates the number of the experiment to the message that was typed in when it was executed.

* In the results root, symlinks `latest/experiment` to the last-run version.
* Creates a link to the experiment version in the `dated` folder of the results root, with the same name and version as the experiment but prefixed with today's date. E.g., `dated/2015/04/13-your/experiment/here/1`

Note that these steps are identical and the results will be the same as if `git results project/results/a` had been run from the git root.  `git-results` always stores information relative to the results root, calculated based on where `git-results.cfg` last occurs in the specified path.

### Experiment results
The versioned experiment folder will contain the following:

* stdout
* stderr
* A meta-information file git-results-message, containing:
    * The git tag that marks the experiment.
    * The message entered when the experiment was ran.
    * The contents of the `run` and `build` commands from `git-results.cfg`.
    * The starting timestamp, total duration, and whether or not the program exited successfully.
* Any files created during the execution of the run command.


(can also be executed as `git results project/results/a` from the git root; the path to `git-results.cfg` determines the working directory)


## Comparing code from two experiments

    git diff path/to/results/experiment/version path/toresults/other/version --

Note the `--` at the end - without this, git doesn't know what to do.


Resuming / Re-Entrant `run` Commands
-------------------------------------------

Check out `progress` above in the config file.


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

* 2018-09-20 - catch KeyboardInterrupts to avoid deleting experiments that
  should be marked as aborted.
* 2017-12-18 - Clarification of exception message when trying to use an
  experiment folder with only one folder name (e.g. /results-of-experiment).
  git-results requires an experiment root, which was made more clear.
* 2017-8-10 - No arguments will print the help message rather than erroring out.

  PYTHONUNBUFFERED=1 is automatically passed as part of the git-results
  environment.
* 2017-2-9 - Fixed missing output when the supervisor was spawned via crontab.

  When running under crontab, sometimes stderr or stdout gets closed before git-results finishes streaming all of the spawned process' output.  In those cases, a bug in the tee() function stopped further output from being captured.
* 2017-1-3 - Fixing an issue when using path trimming and the result contains only a single file.
* 2016-12-7 - Supervisor ran as `git results supervisor --manual` now allows the user to abort an experiment rather than retry it.
* 2016-10-27 - Supervisor / internal retry will no longer automatically mark an experiment that keeps failing as failed.  It will instead rename the folder with -manual-retry, which requires that the user run `git results supervisor --manual` and enter `Y` to the prompt asking them to resume the experiment.

  Also added ignore=['*.txt', '/tmp/*.blah'] option to git-results.cfg.  Any files matching the given globs will not be copied as results.  Syntax is similar to `.gitignore` files: https://git-scm.com/docs/gitignore.

  Version set to 0.2.1.
* 2016-8-8 - Supervisor (and other experiments) now run in a minimal
  environment, like cron.  This was done to prevent experiments from working
  when run from the terminal, but failing when the supervisor runs them.

  Version set to 0.2.0.
* 2016-8-7 - Changed --extra-file to be local to working directory:local to
  the git-results.cfg file used.
* 2016-7-1 - An error while moving files will now preserve the temporary
  directory as well as symlinks to it, to prevent data loss.

  Also Python 3 support.
* 2016-6-8 - Config vars now do dependency sorting, substituting at the last
  possible moment.
* 2016-6-1 - Config overhaul.  Rather than several binary files, there is now
  a single git-results.cfg file.
* 2016-6-1 - Various fixes - method for ignoring e.g. '.pyc' files,
  git results move fixes, trim to git-results-run root by default.
* 2016-5-30 - Fixed bug where symlinks were copied incorrectly.
* 2016-4-7 - Added the tag (without results directory) as an argument to
  git-results-build and git-results-run in case different behavior is desired
  for different experiment paths.
* 2016-1-4 - Fixed git-results move for sub-results folders.
* 2015-4-13 - git-results now respects multiple results folders in a single
  directory, and each can have their own git-results-run and git-results-build.
  These files are also no longer .gitignored.

  Supervisor now deletes experiments whose folder no longer exists; its
  output can be appended to a log file, and the log file won't get too big.
* 2015-4-8 - If a new results directory will be created / added to .gitignore,
  then the user is prompted to enter a string starting with y.
* 2015-4-8 - Moving experiments works better now and updates index.  Build
  failures preserve the old message.  -c and -p are no longer needed, as they
  are implied.  git-results now recursively scans parents of a tag until it
  finds a git-results-run, the sibling of which is the results directory (which
  is checked in .gitignore, etc).  Prompts are given for updating .gitignore.
  git-results-build and git-results-run are now version controlled.
* 2015-2-26 - If a folder is deleted and experiments are run again, will
  correctly remove tags and folders from partially-created experiments.
  Consults INDEX file for next index to allocate.
* 2015-1-7 - Fixed up crashes during filesystem move in two ways: First, all
  files that can be copied are copied before an error is reported.  Second,
  any errors during this phase of the simulation will cause the experiment to
  be marked failed rather than deleted.
* 2014-12-11 - Added -r or --retry-until-stall flag to register a run with
  git-results --supervisor, which scans a user's .gitresults directory attempting to
  start any experiments that have stopped and are still in -run state.  Note
  that without a git-results-progress file, which MUST OUTPUT A SINGLE,
  MONOTONICALLY INCREASING NUMBER BASED ON PROGRESS, an experiment registered
  with -r will complain.  This file is mandatory so that transient errors can
  be detected.  Even with no change in progress, an experiment will be retried
  3 times (--retry-minimum) with 60 seconds between tries (--retry-delay).
* 2014-12-5 - Added -x or --extra-file flags to copy a non-build file before the
  build process.  I use this to "continue" old experiments currently.  It might
  be better to just have a --resurrect flag in the future, but for now -x works.
* 2014-9-23 - Added INDEX file at root of all experiment directories to help
  distinguish between different runs at a glance.  Message is required.
* 2014-8-28 - -f flag for a follow-up shell command to be run in the completed
  folder on success.  Try to delete experiment folder for up to 10 seconds if
  files are still being written.
* 2014-6-25 - -m flag is optional; if a commit is made, then a commit message
  is prompted
* 2014-4-7 - Minor fix for "move" and Python 2.6 support (must install argparse of course).
  -A to auto add removed files.
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

* git-results.cfg.local for local [vars] values.  Should be auto-added to .gitignore.
* -i flag should use its own permanent home, to avoid accidentally mucking up the home directory
  * Or... obsolete -i flag.  Use a pool of LIFO temporary folders, store git-results script pid to make sure you're not overwriting one that's in use.  If something goes wrong (files not copied out, e.g. pid file exists), delete a temporary directory.  None exist, make a new one.  This could shave minutes off of every experiment for long builds.
* --clean flag to clean up extant -run that aren't registered with -r.
* Latest linking is broken if two tests are started and the second one finishes
  first (it looks for test-run, doesn't find it, bails)
* Git results -v should show either a curses or webpage view of available files
  and log entries to make perusing prior results more straightforward.
* Git results message should be saved across build-fail runs.  That is, if build
  fails, it should preserve the old message so I can simply amend it.
* -i should create a temporary file; git-results should never execute a new
  test / commit if this file exists.
* -run tags should be cleaned up by subsequent runs if they have been terminated
    * Might want to just say if there's been no output for a day, drop it?
    * Can we actually detect a dead process that we have no relation to?  I forget.
