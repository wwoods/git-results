
import datetime
import imp
import os
import re
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
    return stdout


def checkTag(tag):
    """Returns the commit SHA of the given tag, or None if it does not exist."""
    o = checked("git tag -l {}".format(tag))
    if not o.strip():
        return None
    return checked("git rev-list {} --".format(tag)).strip().split("\n")[
            0].strip()


class TestGitResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._OLD_STDERR = sys.stderr
        sys.stderr = sys.stdout
        cls.rootDir = tempfile.mkdtemp()


    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.rootDir)
        sys.stderr = cls._OLD_STDERR


    def setUp(self):
        self.__oldDir = os.getcwd()
        os.chdir(self.rootDir)


    def tearDown(self):
        os.chdir(self.__oldDir)


    def _assertTagMatchesMessage(self, tag, suffix = ""):
        """Ensure that the git-results-message file matches the tagged commit.
        """
        commit = re.search("^Commit: ([a-z0-9]+)$",
                open('{}/git-results-message'.format(tag + suffix)).read(),
                re.M)
        self.assertNotEqual(None, commit)
        commit = commit.group(1)
        self.assertEqual(commit, checkTag(tag))


    def _getDatedBase(self):
        now = datetime.datetime.now()
        return os.path.join('results', 'dated', now.strftime('%Y'),
                now.strftime('%m'), now.strftime('%d'))


    def _remakeAndChdirTmp(self):
        try:
            shutil.rmtree("tmp")
        except OSError, e:
            # Does not exist
            if e.errno != 2:
                raise
        git_results.safeMake("tmp")
        os.chdir("tmp")


    def _setupRepo(self):
        """Initializes the "tmp" directory with a basic repo from the readme."""
        self._remakeAndChdirTmp()
        checked("git init")
        with open("hello_world", "w") as f:
            f.write("echo 'Hello, world'\n")
            f.write("echo 'Hello run' > hello_world_run\n")
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


    def test_buildFail(self):
        # Ensure that a failed build leaves no trace behind (except for the
        # commit).
        self._setupRepo()
        with open("git-results-build", "w") as f:
            f.write("Fhgwgds")
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("-c test/run -m 'Imma fail'"))

        self.assertEqual(None, checkTag("results/test/run/1"))
        self.assertEqual(False, os.path.lexists("results/test"))
        self.assertEqual(False, os.path.lexists("results/dated"))
        self.assertEqual(False, os.path.lexists("results/latest"))
        # Saved due to .gitignore
        self.assertEqual(True, os.path.lexists("results"))


    def test_link(self):
        # Check linking
        self._setupRepo()
        git_results.run(shlex.split("-c test/run -m 'Woo'"))
        git_results.run(shlex.split("link test/run test/run2"))
        self._assertTagMatchesMessage("results/test/run/1")
        self._assertTagMatchesMessage("results/test/run2/1")
        self.assertEqual(checkTag("results/test/run/1"),
                checkTag("results/test/run2/1"))
        self.assertEqual("Hello, world\n",
                open("results/latest/test/run/stdout").read())
        self.assertEqual("Hello, world\n",
                open("results/latest/test/run2/stdout").read())

        # Ensure status carry over
        with open("git-results-run", "w") as f:
            f.write("wihefiaheifwf")

        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("-c test/run -m 'Woo'"))
        git_results.run(shlex.split("link test/run test/run3"))
        self._assertTagMatchesMessage("results/test/run/2", "-fail")
        self._assertTagMatchesMessage("results/test/run3/2", "-fail")
        self.assertEqual("",
                open("results/latest/test/run3-fail/stdout").read())


    def test_move(self):
        # Check basic move case
        self._setupRepo()
        dateBase = self._getDatedBase()
        git_results.run(shlex.split("-c test/run -m 'Woo'"))
        git_results.run(shlex.split("move test/run test/run2"))
        self.assertEqual(None, checkTag("results/test/run/1"))
        self._assertTagMatchesMessage("results/test/run2/1")
        self.assertEqual(False, os.path.lexists("results/test/run"))

        # Check dated / latest updates
        print("Testing {}".format(dateBase + "-test/run"))
        self.assertEqual(False, os.path.lexists(dateBase + '-test/run'))
        self.assertEqual(True, os.path.lexists(dateBase + '-test/run2'))
        self.assertEqual(False, os.path.lexists('results/latest/test/run'))
        self.assertEqual(True, os.path.lexists('results/latest/test/run2'))

        # Should allow running a new experiment at the moved tag
        git_results.run(shlex.split("-c test/run -m 'Woooo'"))
        self._assertTagMatchesMessage("results/test/run/1")


    def test_moveFail(self):
        # Ensure dated-fail moves
        self._setupRepo()
        with open('git-results-run', 'w') as f:
            f.write("hiwehfiahef")
        dateBase = self._getDatedBase()
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("-c test/run -m 'woo'"))
        try:
            git_results.run(shlex.split("move test/run test/run2"))
        except SystemExit, e:
            self.fail(str(e))
        self.assertEqual(False, os.path.lexists("results/test/run"))
        self.assertEqual(False, os.path.lexists(dateBase + "-test/run"))
        self.assertEqual(True, os.path.lexists(dateBase + "-test/run2"))
        self.assertEqual("", open(dateBase + "-test/run2/1-fail/stdout").read())


    def test_moveSingle(self):
        # Should fail to move an instance of a tag
        self._setupRepo()
        git_results.run(shlex.split("-c test/run -m Woo"))
        with self.assertRaises(ValueError):
            git_results.run(shlex.split("move test/run/1 test/run2"))
        with self.assertRaises(ValueError):
            git_results.run(shlex.split("move test/run test/run2/1"))
        with self.assertRaises(ValueError):
            git_results.run(shlex.split("move test/run/1 test/run2/1"))


    def test_noMessage(self):
        # Ensure it does not work without a message...
        self._setupRepo()

        try:
            with self.assertRaises(NotImplementedError):
                git_results.run(shlex.split("-c test/run"))
        except SystemExit, e:
            self.fail(str(e))

        '''
        self.assertEqual("Hello, world\n",
                open('results/test/run/1/stdout').read())
        self.assertEqual("", open('results/test/run/1/stderr').read())
        self.assertNotIn('hello_world_2', os.listdir('.'))
        self.assertNotIn('hello_world_2', os.listdir('results/test/run/1'))
        '''


    def test_basic(self):
        # Ensure that basic behavior works - experiment indexing, .gitignore
        # changes, commits,
        self._setupRepo()

        now = datetime.datetime.now()
        datedFolder = 'results/dated/{}/{}/{}-test/run'.format(
                now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))

        # The first commit here would want to commit since we haven't ignored
        # files we should, so this should fail
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split('test/run -m "Should fail"'))

        self.assertEqual(None, checkTag("results/test/run/1"))

        # OK, now commit.
        try:
            git_results.run(shlex.split('-c test/run -m "Let\'s see if it '
                    'prints"'))
        except SystemExit, e:
            self.fail(str(e))

        # Check that our commit properly ignored stuff
        self.assertTrue(checked(
                "git status --porcelain --ignored git-results-build")
                .startswith("!!"))
        self.assertTrue(checked(
                "git status --porcelain --ignored git-results-run")
                .startswith("!!"))
        self.assertTrue(checked(
                "git status --porcelain --ignored results")
                .startswith("!!"))

        # Check that the git repo was tagged correctly
        self._assertTagMatchesMessage("results/test/run/1")

        # Check the results
        self.assertEqual("Hello, world\n",
                open('results/test/run/1/stdout').read())
        self.assertEqual("Hello, world\n",
                open(os.path.join(datedFolder, '1/stdout')).read())
        self.assertEqual("Hello, world\n",
                open("results/latest/test/run/stdout").read())
        self.assertEqual("", open('results/test/run/1/stderr').read())
        self.assertNotIn('hello_world_2', os.listdir('.'))
        self.assertNotIn('hello_world_2', os.listdir('results/test/run/1'))

        # Now see if a failed test gets renamed appropriately
        with open("hello_world", "w") as f:
            f.write("ezeeeeecho 'Hello, world'")
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split('-c test/run -m "take 2"'))

        def testFail(n):
            pth = "{}-fail".format(n)
            self._assertTagMatchesMessage("results/test/run/{}".format(n),
                    "-fail")
            self.assertEqual("",
                    open('results/test/run/{}/stdout'.format(pth)).read())
            self.assertEqual("",
                    open(os.path.join(datedFolder, '{}/stdout'.format(pth))
                        ).read())
            self.assertEqual("", open("results/latest/test/run-fail/stdout").read())
            self.assertEqual(False, os.path.lexists("results/latest/test/run"))
            err = open('results/test/run/{}/stderr'.format(pth)).read()
            self.assertIn("ezeeeeecho", err.lower())
            self.assertIn("not found", err.lower())
            self.assertNotIn('hello_world_2', os.listdir('.'))
            self.assertNotIn('hello_world_2', os.listdir('results/test/run/{}'
                    .format(pth)))
        testFail(2)
        self.assertEqual(False, os.path.lexists('results/test/run/2'))

        # Ensure that no -c flag works now that we have no changes
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split('test/run -m "take 3"'))
        testFail(3)


    def test_continuation(self):
        # Ensure that the next run # is one higher than the greatest.
        self._setupRepo()
        git_results.run(shlex.split("-c test/run -m 'h'"))
        git_results.run(shlex.split("-c test/run -m 'h'"))
        shutil.rmtree("results/test/run/1")
        git_results.run(shlex.split("-c test/run -m 'h'"))
        self.assertEqual(True, os.path.lexists("results/test/run/3"))


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
        # Result file should have been moved instead of copied
        self.assertIn('hello_world_run', os.listdir('wresults/in/place/1'))
        self.assertNotIn('hello_world_run', os.listdir('.'))


    def test_pFlag(self):
        self._setupRepo()

        now = datetime.datetime.now()
        datedFolder = 'qresults/dated/{}/{}/{}-test/run'.format(
                now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))

        # -p flag should work
        try:
            git_results.run(shlex.split('-cp qresults/test/run -m "Take 2"'))
        except SystemExit, e:
            self.fail(str(e))

        # Check that our commit properly ignored stuff
        self.assertTrue(checked(
                "git status --porcelain --ignored git-results-build")
                .startswith("!!"))
        self.assertTrue(checked(
                "git status --porcelain --ignored git-results-run")
                .startswith("!!"))
        self.assertTrue(checked(
                "git status --porcelain --ignored qresults")
                .startswith("!!"))

        self._assertTagMatchesMessage("qresults/test/run/1")

        self.assertEqual("Hello, world\n",
                open('qresults/test/run/1/stdout').read())
        self.assertEqual("Hello, world\n",
                open(os.path.join(datedFolder, '1/stdout')).read())
        self.assertEqual("Hello, world\n",
                open("qresults/latest/test/run/stdout").read())
        self.assertEqual("", open('qresults/test/run/1/stderr').read())
        self.assertNotIn('hello_world_2', os.listdir('.'))
        self.assertNotIn('hello_world_2', os.listdir('qresults/test/run/1'))


    def test_readme(self):
        # Ensure that the README scenario works
        self._remakeAndChdirTmp()
        checked("git init")
        checked("touch git-results-build")
        checked("echo 'echo \"Hello, world\"' > git-results-run")
        checked("chmod a+x git-results-*")
        try:
            git_results.run(shlex.split("-c test/run -m \"Let's see if it "
                    "prints\""))
        except SystemExit, e:
            self.fail(str(e))
        self.assertEqual("Hello, world\n",
                open("results/test/run/1/stdout").read())
