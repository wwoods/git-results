
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


    def test_readme(self):
        # Ensure the README behavior works
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

        open("git-results-build", "w").close()
        addExec("git-results-build")
        with open("git-results-run", "w") as f:
            f.write("./hello_world")
        addExec("git-results-run")

        try:
            git_results.run(shlex.split('-c test/run -m "Let\'s see if it '
                    'prints"'))
        except SystemExit, e:
            self.fail(str(e))

        self.assertEqual("Hello, world\n",
                open('results/test/run/1/stdout').read())
        self.assertEqual("", open('results/test/run/1/stderr').read())

        # -p flag should work
        try:
            git_results.run(shlex.split('-cp results/test/run -m "Take 2"'))
        except SystemExit, e:
            self.fail(str(e))

        self.assertEqual("Hello, world\n",
                open('results/test/run/2/stdout').read())
        self.assertEqual("", open('results/test/run/2/stderr').read())

        # Now see if a failed test gets renamed appropriately
        with open("hello_world", "w") as f:
            f.write("ezeeeeecho 'Hello, world'")
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split('-c test/run -m "take 3"'))

        self.assertEqual("", open('results/test/run/3-fail/stdout').read())
        err = open('results/test/run/3-fail/stderr').read()
        self.assertIn("ezeeeeecho", err.lower())
        self.assertIn("not found", err.lower())

        self.assertEqual(False, os.path.exists('results/test/run/3'))
