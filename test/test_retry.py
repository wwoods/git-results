
import os
import shlex
import shutil
import tempfile
import textwrap
import time

from .common import GrTest, git_results, addExec, checked

class TestRetry(GrTest):
    def _setupRepo(self):
        self.initAndChdirTmp()
        checked([ "git", "init" ])
        with open("run.py", "w") as f:
            f.write(textwrap.dedent(r"""
                    import os
                    v = len(open('work').read().split('\n') if os.path.lexists('work') else [])
                    if v < 3:
                        open('work', 'a').write('HI\n')
                        raise Exception('Booo!')
                    """))
        with open("git-results.cfg", "w") as f:
            f.write(textwrap.dedent(r"""
                    [/]
                    run = "python run.py"
                    progress = "cat work | wc -l"
                    # Some networked file systems don't do well when comparing
                    # time() to file stamps... allow up to two minutes of
                    # tolerance for testing purposes.
                    progressDelay = -120.
                    """))


    def test_manualResume_corruptBuildState(self):
        self._setupRepo()
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m a"))
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
        with open("run.py", "w") as f:
            f.write(textwrap.dedent(r"""
                    #! /usr/bin/env python2
                    import os
                    with open('test', 'w') as f:
                        f.write("WOO")
                    raise Exception('Booo!')
                    """))
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m a"))
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
        # 3rd failure without progress; should switch to manual mode
        self.assertEqual(True, os.path.lexists(keyFolder))
        os.chdir(odir)
        # Make sure it got closed and moved to the 1-fail folder
        self.assertEqual('', open('results/test/1-manual-retry/stdout').read())
        self.assertEqual('WOO',
                open('results/test/1-manual-retry/git-results-tmp/test')
                .read())

        # Ensure that supervisor --manual works... for now, it only retries, it
        # will NOT prompt the user and cannot be used to fail an experiment.
        with open('results/test/1-manual-retry/git-results-tmp/run.py', 'w') \
                as f:
            f.write(textwrap.dedent(r"""
                    #! /usr/bin/env python2
                    import os
                    with open('test', 'w') as f:
                        f.write("WOO2")
                    raise Exception('Booo!')
                    """))

        # Start a new experiment that won't be at manual point yet, ensure only
        # one gets started with and without manual flag
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m a"))

        started = git_results._runSupervisor(['--manual'])
        self.assertEqual(1, len(started))
        [ p.wait() for p in started ]
        self.assertEqual("WOO2",
                open("results/test/1-manual-retry/git-results-tmp/test")
                .read())
        self.assertTrue(os.path.lexists("results/test/2-run"))
        started = git_results._runSupervisor([])
        self.assertEqual(1, len(started))
        [ p.wait() for p in started ]
        # Not yet at manual fail point, still marked as run
        self.assertTrue(os.path.lexists("results/test/2-run"))
        key2 = open('results/test/2-run/git-results-retry-key').read()
        keyFolder2 = os.path.join(os.path.expanduser('~/.gitresults/'), key2)
        # Abort that experiment so it doesn't mess up future tests
        shutil.rmtree(keyFolder2)

        # Abort
        git_results.IS_TEST_FAIL_MANUAL = True
        try:
            self.assertEqual(True, os.path.lexists(keyFolder))
            started = git_results._runSupervisor(['--manual'])
            self.assertEqual(1, len(started))
            [ p.wait() for p in started ]
            self.assertTrue(os.path.lexists("results/test/1-abrt"))
            self.assertTrue(os.path.lexists("results/test/1-abrt/test"))
            self.assertEqual("WOO2", open("results/test/1-abrt/test").read())
            self.assertFalse(os.path.lexists(keyFolder))
        finally:
            git_results.IS_TEST_FAIL_MANUAL = False


    def test_manualResume_ok(self):
        self._setupRepo()
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m a"))
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
            git_results.run(shlex.split("results/test -m a"))
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
