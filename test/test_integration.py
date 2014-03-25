
import datetime
import imp
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

GR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        "../git-results")
git_results = imp.new_module('git_results')
exec open(GR_FILE).read() in git_results.__dict__

def addExec(fname):
    os.chmod(fname, os.stat(fname).st_mode | stat.S_IEXEC)


def checked(cmd):
    p = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE,
            stderr = subprocess.PIPE)
    stdout, stderr = p.communicate()
    r = p.wait()

    if r != 0:
        raise AssertionError("Command failed {}: {}".format(r, stderr))


class TestGitResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rootDir = tempfile.mkdtemp()


    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.rootDir)


    def setUp(self):
        self.__oldDir = os.getcwd()
        os.chdir(self.rootDir)


    def tearDown(self):
        os.chdir(self.__oldDir)


    def _setupRepo(self):
        """Initializes the "tmp" directory with a basic repo from the readme."""
        try:
            shutil.rmtree("tmp")
        except OSError, e:
            # Does not exist
            if e.errno != 2:
                raise
        git_results.safeMake("tmp")
        os.chdir("tmp")
        checked("git init")
        with open("hello_world", "w") as f:
            f.write("echo 'Hello, world'")
        addExec("hello_world")
        checked("git add hello_world")
        checked("git commit -m 'First version'")

        with open("git-results-build", "w") as f:
            # Even though this isn't in the readme, ensure isolation is a thing
            f.write("cp hello_world hello_world_2")
        addExec("git-results-build")
        with open("git-results-run", "w") as f:
            f.write("./hello_world_2")
        addExec("git-results-run")


    def test_noMessage(self):
        # Ensure it works without a message...
        self._setupRepo()

        try:
            git_results.run(shlex.split("-c test/run"))
        except SystemExit, e:
            self.fail(str(e))

        self.assertEqual("Hello, world\n",
                open('results/test/run/1/stdout').read())
        self.assertEqual("", open('results/test/run/1/stderr').read())
        self.assertNotIn('hello_world_2', os.listdir('.'))
        self.assertNotIn('hello_world_2', os.listdir('results/test/run/1'))


    def test_readme(self):
        # Ensure the README behavior works
        self._setupRepo()

        now = datetime.datetime.now()
        datedFolder = 'results/dated/{}/{}/{}-test/run'.format(
                now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))

        try:
            git_results.run(shlex.split('-c test/run -m "Let\'s see if it '
                    'prints"'))
        except SystemExit, e:
            self.fail(str(e))

        self.assertEqual("Hello, world\n",
                open('results/test/run/1/stdout').read())
        self.assertEqual("Hello, world\n",
                open(os.path.join(datedFolder, '1/stdout')).read())
        self.assertEqual("Hello, world\n",
                open("results/latest/test/run/stdout").read())
        self.assertEqual("", open('results/test/run/1/stderr').read())
        self.assertNotIn('hello_world_2', os.listdir('.'))
        self.assertNotIn('hello_world_2', os.listdir('results/test/run/1'))

        # -p flag should work
        try:
            git_results.run(shlex.split('-cp results/test/run -m "Take 2"'))
        except SystemExit, e:
            self.fail(str(e))

        self.assertEqual("Hello, world\n",
                open('results/test/run/2/stdout').read())
        self.assertEqual("Hello, world\n",
                open(os.path.join(datedFolder, '2/stdout')).read())
        self.assertEqual("Hello, world\n",
                open("results/latest/test/run/stdout").read())
        self.assertEqual("", open('results/test/run/2/stderr').read())
        self.assertNotIn('hello_world_2', os.listdir('.'))
        self.assertNotIn('hello_world_2', os.listdir('results/test/run/2'))

        # Now see if a failed test gets renamed appropriately
        with open("hello_world", "w") as f:
            f.write("ezeeeeecho 'Hello, world'")
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split('-c test/run -m "take 3"'))

        self.assertEqual("", open('results/test/run/3-fail/stdout').read())
        self.assertEqual("",
                open(os.path.join(datedFolder, '3-fail/stdout')).read())
        self.assertEqual("", open("results/latest/test/run-fail/stdout").read())
        err = open('results/test/run/3-fail/stderr').read()
        self.assertIn("ezeeeeecho", err.lower())
        self.assertIn("not found", err.lower())
        self.assertNotIn('hello_world_2', os.listdir('.'))
        self.assertNotIn('hello_world_2', os.listdir('results/test/run/3-fail'))

        self.assertEqual(False, os.path.exists('results/test/run/3'))


    def test_inPlace(self):
        # Ensure that in-place works
        self._setupRepo()
        try:
            git_results.run(shlex.split("-cip wresults/in/place -m 'hmm'"))
        except SystemExit, e:
            self.fail(str(e))

        self.assertEqual("Hello, world\n",
                open('wresults/in/place/1/stdout').read())
        self.assertEqual("", open('wresults/in/place/1/stderr').read())
        # Build should have happened locally
        self.assertIn('hello_world_2', os.listdir('.'))
        # But not counted as a result
        self.assertNotIn('hello_world_2', os.listdir('wresults/in/place/1'))
