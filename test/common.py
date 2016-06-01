
import imp
import os
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
sys.modules['git_results'] = git_results

def addExec(fname):
    os.chmod(fname, os.stat(fname).st_mode | stat.S_IEXEC)


# Import the checked() call
checked = git_results.checked

class GrTest(unittest.TestCase):
    """A test that has a temporary directory attached in which git-results
    activities happen."""
    @classmethod
    def setUpClass(cls):
        git_results.IS_TEST = True
        cls._OLD_STDERR = sys.stderr
        sys.stderr = sys.stdout

        cls.rootDir = os.path.join(tempfile.gettempdir(), "git-results-test")
        try:
            os.makedirs(cls.rootDir)
        except OSError, e:
            # Already exists?
            if e.errno != 17:
                raise


    @classmethod
    def tearDownClass(cls):
        #shutil.rmtree(cls.rootDir)
        sys.stderr = cls._OLD_STDERR
        git_results.IS_TEST = False


    def setUp(self):
        self.__oldDir = os.getcwd()
        os.chdir(self.rootDir)


    def tearDown(self):
        os.chdir(self.__oldDir)


    def initAndChdirTmp(self):
        try:
            shutil.rmtree("tmp")
        except OSError, e:
            # Does not exist
            if e.errno != 2:
                raise
        git_results.safeMake("tmp")
        os.chdir("tmp")
