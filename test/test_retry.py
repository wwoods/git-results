
import os
import shlex
import shutil
import tempfile
import time

from .common import GrTest, git_results, addExec, checked

class TestRetry(GrTest):
    def _setupRepo(self):
        self.initAndChdirTmp()
        checked([ "git", "init" ])
        with open('git-results-build', 'w') as f:
            f.write("")
        with open('git-results-run', 'w') as f:
            f.write("#! /usr/bin/env python2\n")
            f.write("import os\n")
            f.write("v = len(open('work').read().split('\\n') if os.path.lexists('work') else [])\n")
            f.write("if v < 3:\n")
            f.write("    open('work', 'a').write('HI\\n')\n")
            f.write("    raise Exception('Booo!')\n")
        with open('git-results-progress', 'w') as f:
            f.write("cat work | wc -l")
        [ addExec(p) for p in [ 'git-results-build', 'git-results-run',
                'git-results-progress' ] ]


    def test_manualResume_corruptBuildState(self):
        self._setupRepo()
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m a -r --retry-delay 0"))
        key = open('results/test/1-run/git-results-retry-key').read()
        keyFolder = os.path.join(os.path.expanduser('~/.gitresults/'), key)
        with open(os.path.join(keyFolder, "build-state"), 'w') as f:
            f.write("Hehfaiwehf")
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("--internal-retry-continue " + key))
        self.assertEqual(True, os.path.lexists("results/test/1-fail/stderr"))
        self.assertEqual(False, os.path.lexists(keyFolder))


    def test_manualResume_fail(self):
        self._setupRepo()
        with open('git-results-run', 'w') as f:
            f.write("#! /usr/bin/env python2\n")
            f.write("raise Exception('Booo!')\n")
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m a -r --retry-delay 0"))
        key = open('results/test/1-run/git-results-retry-key').read()
        keyFolder = os.path.join(os.path.expanduser('~/.gitresults/'), key)
        # Switch cwd so that we ensure --internal-retry-continue works out of
        # the correct directory
        odir = os.getcwd()
        os.chdir(tempfile.gettempdir())
        self.assertEqual(True, os.path.lexists(keyFolder))
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("{} --internal-retry-continue".format(
                    key)))
        self.assertEqual(True, os.path.lexists(keyFolder))
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("{} --internal-retry-continue".format(
                    key)))
        self.assertEqual(True, os.path.lexists(keyFolder))
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("{} --internal-retry-continue".format(
                    key)))
        os.chdir(odir)
        # Make sure it got closed and moved to the 1-fail folder
        self.assertEqual('', open('results/test/1-fail/stdout').read())
        self.assertEqual(False, os.path.lexists(keyFolder))


    def test_manualResume_ok(self):
        self._setupRepo()
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m a -r --retry-delay 0"))
        key = open('results/test/1-run/git-results-retry-key').read()
        keyFolder = os.path.join(os.path.expanduser('~/.gitresults/'), key)
        self.assertEqual(True, os.path.lexists(keyFolder))
        # Switch cwd so that we ensure --internal-retry-continue works out of
        # the correct directory
        odir = os.getcwd()
        os.chdir(tempfile.gettempdir())
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("{} --internal-retry-continue".format(
                    key)))
        self.assertEqual(True, os.path.lexists(keyFolder))
        git_results.run(shlex.split("{} --internal-retry-continue".format(
                key)))
        os.chdir(odir)
        self.assertEqual('HI\nHI\n', open('results/test/1/work').read())
        self.assertEqual(False, os.path.lexists(keyFolder))


    def test_supervisorDeleteBad(self):
        rottenExperiment = os.path.expanduser("~/.gitresults/rtestBlahTest")
        if os.path.lexists(rottenExperiment):
            shutil.rmtree(rottenExperiment)
        os.mkdir(rottenExperiment)
        self.assertEqual(True, os.path.lexists(rottenExperiment))
        git_results._runSupervisor([])
        self.assertEqual(False, os.path.lexists(rottenExperiment))


    def test_supervisorIgnoreCorrupt(self):
        rottenExperiment = os.path.expanduser("~/.gitresults/rtestBlahTest")
        archiveExperiment = os.path.expanduser("~/.gitresults/bad_rtestBlahTest")
        if os.path.lexists(rottenExperiment):
            shutil.rmtree(rottenExperiment)
        os.mkdir(rottenExperiment)
        with open(os.path.join(rottenExperiment, "settings"), 'w') as f:
            f.write("Yhawehf")
        # Bad settings file, should get moved to bad_
        git_results._runSupervisor([])
        self.assertEqual(False, os.path.exists(rottenExperiment))
        self.assertEqual(True, os.path.exists(archiveExperiment))
        shutil.rmtree(archiveExperiment)


    def test_supervisorResume_ok(self):
        self._setupRepo()
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m a -r --retry-delay 0"))
        key = open('results/test/1-run/git-results-retry-key').read()
        keyFolder = os.path.join(os.path.expanduser('~/.gitresults/'), key)
        self.assertEqual(True, os.path.lexists(keyFolder))
        # Switch cwd so that we ensure --internal-retry-continue works out of
        # the correct directory
        odir = os.getcwd()
        os.chdir(tempfile.gettempdir())
        # Should retry our application
        started = git_results._runSupervisor([])
        self.assertEqual(1, len(started))
        [ p.wait() for p in started ]
        self.assertEqual(True, os.path.lexists(keyFolder))
        started = git_results._runSupervisor([])
        self.assertEqual(1, len(started))
        [ p.wait() for p in started ]
        self.assertEqual(False, os.path.lexists(keyFolder))
        started = git_results._runSupervisor([])
        self.assertEqual([], started)
