# TODO - reprconf was modified to use ConfigParser(strict=False).  Would be good
# if strict mode were enabled, though many changes in this file would be
# required.

from .common import GrTest, git_results, addExec, checked

import datetime
import os
import re
import shlex
import shutil
import subprocess
import textwrap

def checkTag(tag):
    """Returns the commit SHA of the given tag, or None if it does not exist."""
    o = checked([ "git", "tag", "-l", tag ])
    if not o.strip():
        return None
    return checked([ "git", "rev-list", tag, "--" ]).strip().split("\n")[
            0].strip()


class TestGitResults(GrTest):
    def _assertTagMatchesMessage(self, tag, suffix = ""):
        """Ensure that the git-results-message file matches the tagged commit.
        """
        commit = re.search("^Commit: ([a-z0-9]+)$",
                open('{}/git-results-message'.format(tag + suffix)).read(),
                re.M)
        self.assertNotEqual(None, commit)
        commit = commit.group(1)
        self.assertEqual(commit, checkTag(tag))


    def _config(self, opts, new=False, cfgPath="git-results.cfg"):
        """Appends opts to the config file."""
        with open(cfgPath, "a" if not new else "w") as f:
            f.write(textwrap.dedent(opts))


    def _getDatedBase(self):
        now = datetime.datetime.now()
        return os.path.join('results', 'dated', now.strftime('%Y'),
                now.strftime('%m'), now.strftime('%d'))


    def _setupRepo(self):
        """Initializes the "tmp" directory with a basic repo from the readme."""
        self.initAndChdirTmp()
        checked([ "git", "init" ])
        with open("hello_world", "w") as f:
            f.write("echo 'Hello, world'\n")
            f.write("echo 'Hello run' > hello_world_run\n")
        addExec("hello_world")
        checked([ "git", "add", "hello_world" ])
        checked([ "git", "commit", "-m", "First version" ])

        self._config("""
                [/]
                # Default build copies a file to make sure it doesn't reach
                # the results folder (part of build).
                build = "cp hello_world hello_world_2"
                run = "./hello_world_2"
                """, True)


    def test_buildFail(self):
        # Ensure that a failed build leaves no trace behind (except for the
        # commit).
        self._setupRepo()
        self._config("""
                [/results]
                build = "Fhgwgds"
                """)
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test/run -m 'Imma fail'"))

        self.assertEqual(None, checkTag("results/test/run/1"))
        self.assertEqual(False, os.path.lexists("results/test/run/1"))
        self.assertEqual(True, os.path.lexists("results/test/run/INDEX"))
        self.assertEqual(False, os.path.lexists("results/dated"))
        self.assertEqual(False, os.path.lexists("results/latest"))
        # Saved due to .gitignore
        self.assertEqual(True, os.path.lexists("results"))


    def test_copyLink(self):
        # Copying a link with a relative path didn't work previous to this
        # patch.
        self._setupRepo()
        os.makedirs("a/b/c")
        with open("a/b/test1", "w") as f:
            f.write("echo 'COOL'")
        addExec("a/b/test1")
        os.symlink("../test1", "a/b/c/test2")
        os.symlink(os.path.abspath("a/b/test1"), "a/b/c/test3")
        self._config(r"""
                [/]
                run = "a/b/c/test2 && a/b/c/test3"
                """)

        git_results.run(shlex.split("results/test -m 'Ok'"))

        self.assertEqual("COOL\nCOOL\n", open("results/test/1/stdout").read())


    def test_exception_output(self):
        # Ensure that an exception gets logged...
        self._setupRepo()
        with open("test.py", "w") as f:
            f.write("raise ValueError('yodel')")
        self._config("""
                [/]
                run = "python test.py"
                """)
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/t1 -m 't1'"))

        self.assertEqual(True, os.path.lexists("results/t1/1-fail/stderr"))
        err = open("results/t1/1-fail/stderr").read()
        print(err)
        self.assertIn("ValueError", err)
        self.assertIn("yodel", err)


    def test_gitGetsTag(self):
        # Ensure that build and run both get the tag when {tag} is used so they
        # can do something with it
        self._setupRepo()
        self._config("""
                [/]
                build = "echo {tag} > build_pre"
                run = "mv build_pre build_post && echo {tag} > run"
                """)

        git_results.run(shlex.split("results/t1 -m 't1'"))
        git_results.run(shlex.split("results/t2 -m 't2'"))

        self.assertEqual("results/t1\n", open("results/t1/1/build_post").read())
        self.assertEqual("results/t1\n", open("results/t1/1/run").read())
        self.assertEqual("results/t2\n", open("results/t2/1/build_post").read())
        self.assertEqual("results/t2\n", open("results/t2/1/run").read())


    def test_ignore(self):
        self._setupRepo()
        with open("test", "w") as f:
            f.write(r"""
                    set -e
                    touch a; touch b; touch c;
                    mkdir d; touch d/a; touch d/b;
                    mkdir e; touch e/a; touch e/b;
                    mkdir f;
                        mkdir f/e; touch f/e/a; touch f/e/b; touch f/e/c;
                    """)
        addExec("test")
        self._config(r"""
                [/]
                build = None
                run = "./test"
                ignore = [ "a", "!e/a", "/e/b", "/**/c" ]
                """)
        os.makedirs("sub")
        self._config(r"""
                [/]
                run = "../test"
                ignore = [ "a", "!e/a", "/e/b", "/**/c" ]
                """, cfgPath="sub/git-results.cfg")

        git_results.run(shlex.split("r/test -m 'Woo'"))
        git_results.run(shlex.split("sub/r/test -m 'Woo'"))
        for root in [ 'r/test/1', 'sub/r/test/1' ]:
            print("Looking at {}".format(root))
            self.assertEqual(False, os.path.lexists(root + "/a"))
            self.assertEqual(True, os.path.lexists(root + "/b"))
            self.assertEqual(True, os.path.lexists(root + "/c"))
            self.assertEqual(True, os.path.lexists(root + "/d"))
            self.assertEqual(False, os.path.lexists(root + "/d/a"))
            self.assertEqual(True, os.path.lexists(root + "/d/b"))
            self.assertEqual(True, os.path.lexists(root + "/e/a"))
            self.assertEqual(False, os.path.lexists(root + "/e/b"))
            self.assertEqual(True, os.path.lexists(root + "/f/e/a"))
            self.assertEqual(True, os.path.lexists(root + "/f/e/b"))


    def test_link(self):
        # Check linking
        self._setupRepo()
        git_results.run(shlex.split("results/test/run -m 'Woo'"))
        with self.assertRaises(ValueError):
            git_results.run(shlex.split("link test/run test/run2"))
        git_results.run(shlex.split("link results/test/run results/test/run2"))
        self._assertTagMatchesMessage("results/test/run/1")
        self._assertTagMatchesMessage("results/test/run2/1")
        self.assertEqual(checkTag("results/test/run/1"),
                checkTag("results/test/run2/1"))
        self.assertEqual("Hello, world\n",
                open("results/latest/test/run/stdout").read())
        self.assertEqual("Hello, world\n",
                open("results/latest/test/run2/stdout").read())

        # Ensure status carry over
        self._config("""
                [/]
                run = "wihefiaheifwf"
                """)

        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test/run -m 'Woo'"))
        git_results.run(shlex.split("link results/test/run results/test/run3"))
        self._assertTagMatchesMessage("results/test/run/2", "-fail")
        self._assertTagMatchesMessage("results/test/run3/2", "-fail")
        self.assertEqual("",
                open("results/latest/test/run3-fail/stdout").read())


    def test_move(self):
        # Check basic move case
        self._setupRepo()
        dateBase = self._getDatedBase()
        git_results.run(shlex.split("results/test/run -m 'Woo'"))
        git_results.run(shlex.split("move results/test/run results/test/trash/run2"))
        self.assertEqual(None, checkTag("results/test/run/1"))
        self._assertTagMatchesMessage("results/test/trash/run2/1")
        self.assertEqual(False, os.path.lexists("results/test/run"))
        self.assertEqual(True, os.path.lexists("results/test/trash/run2/INDEX"))

        # Check dated / latest updates
        print("Testing {}".format(dateBase + "-test/run"))
        self.assertEqual(False, os.path.lexists(dateBase + '-test/run'))
        self.assertEqual(True, os.path.lexists(dateBase + '-test/trash/run2'))
        self.assertEqual(False, os.path.lexists('results/latest/test/run'))
        self.assertEqual(True,
                os.path.lexists('results/latest/test/trash/run2'))

        # Should allow running a new experiment at the moved tag
        git_results.run(shlex.split("results/test/run -m 'Woooo'"))
        self._assertTagMatchesMessage("results/test/run/1")


    def test_moveExperiment(self):
        # Accidentally ran a tag as another tag, move the experiment
        self._setupRepo()
        git_results.run(shlex.split("results/test/run -m Woo"))
        git_results.run(shlex.split("move results/test/run/1 results/test/run2/1"))
        dateBase = self._getDatedBase()
        self.assertEqual(True, os.path.lexists("results/test/run"))
        self.assertEqual(True, os.path.lexists("results/test/run/INDEX"))
        self.assertEqual(False, os.path.lexists("results/test/run/1"))
        self.assertEqual("1 (move) - (moved to results/test/run2/1) Woo\n",
                open("results/test/run/INDEX").read())

        self.assertEqual(True, os.path.lexists("results/test/run2/1"))
        self.assertEqual(True, os.path.lexists("results/test/run2/INDEX"))
        self.assertEqual("1 (  ok) - Woo\n",
                open("results/test/run2/INDEX").read())

        self.assertEqual(False, os.path.lexists(dateBase + '-test/run'))
        self.assertEqual(True, os.path.lexists(dateBase + '-test/run2/1'))

        self.assertEqual(False, os.path.lexists("results/latest/test/run"))
        self.assertEqual(True, os.path.lexists("results/latest/test/run2"))


    def test_moveFail(self):
        # Ensure dated-fail moves
        self._setupRepo()
        self._config("""
                run = "hiwehfiahef"
                """)
        dateBase = self._getDatedBase()
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test/run -m 'woo'"))
        try:
            git_results.run(shlex.split("move results/test/run results/test/run2"))
        except SystemExit as e:
            self.fail(str(e))
        self.assertEqual(False, os.path.lexists("results/test/run"))
        self.assertEqual(False, os.path.lexists(dateBase + "-test/run"))
        self.assertEqual(True, os.path.lexists(dateBase + "-test/run2"))
        self.assertEqual("", open(dateBase + "-test/run2/1-fail/stdout").read())
        self._assertTagMatchesMessage("results/test/run2/1", suffix="-fail")


    def test_moveMissing(self):
        # Ensure that a request to move something missing is helpful
        self._setupRepo()
        try:
            git_results.run(shlex.split("move results/blah results/blah2"))
            self.fail("No error raised")
        except ValueError as e:
            text = str(e)
        print("Got error: {}".format(text))
        self.assertTrue("Results folder 'results' not found" in text)

        # Now make the results folder, but do it again
        git_results.run(shlex.split("results/test -m 'yee'"))

        print("Doing move")
        try:
            git_results.run(shlex.split("move results/blah results/blah2"))
            self.fail("No error raised")
        except ValueError as e:
            text = str(e)
        print("Got error: {}".format(text))
        self.assertTrue("No result found under 'results/blah'" in text)


    def test_moveMissing_git(self):
        ## Ensure that a move that is missing a git tag but does exist on the
        # filesystem works.

        self._setupRepo()
        git_results.run(shlex.split("results/test -m 'yee'"))
        checked([ "git", "tag", "--delete", "results/test/1" ])
        git_results.run(shlex.split("move results/test results/test2"))

        self.assertTrue(os.path.lexists("results/test2/1"))
        self.assertFalse(os.path.lexists("results/test"))
        self._assertTagMatchesMessage("results/test2/1")


    def test_moveMissing_git_fail(self):
        ## Ensure that a move that is missing a git tag and was a failure will
        # work

        self._setupRepo()
        self._config("""
                run = "echo LALALA && echehfeif ooooooojefwij i"
                """)
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("results/test -m 'yee'"))

        checked([ "git", "tag", "-d", "results/test/1" ])
        os.chdir("results")
        git_results.run(shlex.split("move test test2"))
        os.chdir("..")
        self.assertTrue(os.path.lexists("results/test2/1-fail"))
        self.assertFalse(os.path.lexists("results/test/1-fail"))
        self._assertTagMatchesMessage("results/test2/1", suffix="-fail")


    def test_moveSingle(self):
        # Should fail to move an instance of a tag in a mixed fashion (instance
        # to instance, experiment to experiment)
        self._setupRepo()
        git_results.run(shlex.split("results/test/run -m Woo"))
        with self.assertRaises(ValueError):
            git_results.run(shlex.split("move results/test/run/1 results/test/run2"))
        with self.assertRaises(ValueError):
            git_results.run(shlex.split("move results/test/run results/test/run2/1"))


    def test_moveSub(self):
        # Moving a sub-results folder should work alright
        self._setupRepo()
        os.makedirs("round2")
        self._config("""
                [/]
                run = "echo ROUND2"
                """, cfgPath="round2/git-results.cfg")
        git_results.run(shlex.split("round2/results/test/run1 -m Woo1"))
        git_results.run(shlex.split("round2/results/test/run2 -m Woo2"))
        git_results.run(shlex.split("round2/results/test/run3 -m Woo3"))

        # Move from repo root
        git_results.run(shlex.split("move round2/results/test/run2/1 round2/results/test/run1/2"))

        os.chdir("round2")
        # Can't overwrite existing
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split("move results/test/run3/1 results/test/run1/2"))
        print("Now doing OK move...")
        git_results.run(shlex.split("move results/test/run3/1 results/test/run1/3"))
        os.chdir("..")

        self._assertTagMatchesMessage("round2/results/test/run1/1")
        self._assertTagMatchesMessage("round2/results/test/run1/2")
        self._assertTagMatchesMessage("round2/results/test/run1/3")

        ex = [ "run1/1", "run1/2", "run1/3", "run2/INDEX", "run3/INDEX" ]
        noex = [ "run2/1", "run3/1" ]
        for path in ex:
            print("Testing existence of {0}".format(path))
            self.assertTrue(os.path.lexists("round2/results/test/" + path))
        for path in noex:
            print("Testing absence of {0}".format(path))
            self.assertFalse(os.path.lexists("round2/results/test/" + path))

        mainIndex = "1 (  ok) - Woo1\n2 (  ok) - Woo2\n3 (  ok) - Woo3\n"
        self.assertEqual(mainIndex,
                open("round2/results/test/run1/INDEX").read())
        otherIndex = "1 (move) - (moved to round2/results/test/run1/2) Woo2\n"
        self.assertEqual(otherIndex,
                open("round2/results/test/run2/INDEX").read())
        otherIndex = "1 (move) - (moved to round2/results/test/run1/3) Woo3\n"
        self.assertEqual(otherIndex,
                open("round2/results/test/run3/INDEX").read())


    def test_multiple(self):
        # Check multiple git-results.cfg files working together
        self._setupRepo()
        self._config(r"""
                [/]
                run = "echo HMM | tee outMain"
                """)
        os.makedirs("round2")
        self._config(r"""
                [/r/test]
                run = "echo ROUND2 | tee outTwo"
                """, cfgPath="round2/git-results.cfg")

        git_results.run(shlex.split("r/test -m 'Check this out'"))
        git_results.run(shlex.split("round2/r/test -m 'Check that out'"))
        try:
            os.chdir("round2")
            git_results.run(shlex.split("r/test -m 'Check us out'"))
        finally:
            os.chdir("..")

        self.assertEqual("\n/r\n/round2/r", open(".gitignore").read())

        self._assertTagMatchesMessage("r/test/1")
        self._assertTagMatchesMessage("round2/r/test/1")
        self._assertTagMatchesMessage("round2/r/test/2")

        self.assertEqual(True, os.path.lexists("r/test/INDEX"))
        self.assertEqual("1 (  ok) - Check this out\n",
                open("r/test/INDEX").read())
        self.assertEqual(True, os.path.lexists("round2/r/test/INDEX"))
        self.assertEqual("1 (  ok) - Check that out\n2 (  ok) - Check us out\n",
                open("round2/r/test/INDEX").read())

        # Check content
        self.assertEqual("HMM\n", open("r/test/1/outMain").read())
        self.assertEqual("ROUND2\n", open("round2/r/test/1/outTwo").read())
        self.assertEqual("ROUND2\n", open("round2/r/test/2/outTwo").read())



    def test_noMessage(self):
        # Ensure it does not work without a message, and that only valid
        # messages are accepted.
        self._setupRepo()

        try:
            try:
                # Replace editor with bunk editor
                os.environ['EDITOR'] = 'ls > /dev/null'
                git_results.run(shlex.split("results/test/run"))
            except ValueError as e:
                self.assertEqual("Commit message must be at least 5 "
                        "characters; got: ''", str(e))

            try:
                os.environ['EDITOR'] = 'echo "Comm" >'
                git_results.run(shlex.split("results/test/run"))
            except ValueError as e:
                self.assertEqual("Commit message must be at least 5 "
                        "characters; got: 'Comm'", str(e))

            os.environ['EDITOR'] = 'echo "Commt" >'
            git_results.run(shlex.split("results/test/run"))
            self.assertEqual("Hello, world\n",
                    open("results/test/run/1/stdout").read())

            # If no commit is required, it should still prompt for a
            # message.
            os.environ['EDITOR'] = 'echo "Commz" >'
            git_results.run(shlex.split("results/test/run2"))
            self.assertEqual("Hello, world\n",
                    open("results/test/run2/1/stdout").read())
        except SystemExit as e:
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

        # OK, now commit.
        try:
            git_results.run(shlex.split('results/test/run -m "Let\'s see if it '
                    'prints"'))
        except SystemExit as e:
            self.fail(str(e))

        # Check that our commit properly ignored stuff
        self.assertTrue(checked([ "git", "status", "--porcelain", "--ignored",
                "results" ])
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

        # Ensure that the index was created
        self.assertEqual("1 (  ok) - Let's see if it prints\n",
                open('results/test/run/INDEX').read())

        # Now see if a failed test gets renamed appropriately
        with open("hello_world", "w") as f:
            f.write("ezeeeeecho 'Hello, world'")
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split('results/test/run -m "take 2"'))

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

        # One more just to see
        with self.assertRaises(SystemExit):
            git_results.run(shlex.split('results/test/run -m "take 3"'))
        testFail(3)

        self.assertEqual(
                "1 (  ok) - Let's see if it prints\n"
                "2 (fail) - take 2\n"
                "3 (fail) - take 3\n",
                open('results/test/run/INDEX').read())


    def test_extraFile(self):
        self._setupRepo()
        self._config("""
                run = "cat sa"
                """)
        with open('someTestFile', 'w') as f:
            f.write("Yay!")
        try:
            with self.assertRaises(SystemExit):
                git_results.run(shlex.split("results/test/run -m 'h'"))
            git_results.run(shlex.split(
                    "results/test/run -m 'h' -x someTestFile:sa"))
            git_results.run(shlex.split(
                    "results/test/run -m 'h' --extra-file someTestFile:sa"))
            self.assertEqual(True, os.path.lexists("results/test/run/1-fail"))
            self.assertEqual(False, os.path.lexists("results/test/run/1-fail/sa"))
            self.assertEqual(True, os.path.lexists("results/test/run/2/sa"))
            self.assertEqual(True, os.path.lexists("results/test/run/2/sa"))
            self.assertEqual(True, os.path.lexists("results/test/run/3/sa"))
            self.assertEqual("Yay!", open("results/test/run/2/stdout").read())
            self.assertEqual("Yay!", open("results/test/run/3/stdout").read())
        finally:
            os.remove('someTestFile')


    def test_extraFile_nonRoot(self):
        self._setupRepo()
        os.makedirs("round2")
        self._config("""
                [/r/blah]
                run = "ls  && cp f a && cp ../f b"
                """, cfgPath="round2/git-results.cfg")
        with open("test1", 'w') as f:
            f.write("1")
        with open("test2", "w") as f:
            f.write("2")
        git_results.run(
                shlex.split("round2/r/blah -m 'a' -x test1:f -x test2:../f"))
        self.assertEqual(True, os.path.lexists("round2/r/blah/1"))
        self.assertEqual(True, os.path.lexists("round2/r/blah/1/f"))
        self.assertEqual("1", open("round2/r/blah/1/a").read())
        self.assertEqual("2", open("round2/r/blah/1/b").read())
        # These two files existed above git-results.cfg, so shouldn't be
        # included
        self.assertEqual(False, os.path.lexists("round2/r/blah/1/test1"))
        self.assertEqual(False, os.path.lexists("round2/r/blah/1/test2"))


    def test_configVars(self):
        ## Ensure that configuration works
        self._setupRepo()
        self._config("""
                [vars]
                cmd = "test"
                cmd2 = "{cmd} ok"
                cmd3 = "{cmd2}, really"

                [/r/a]
                run = "echo {cmd}"

                [/r/b]
                run = "echo {cmd2}"

                [/r/c]
                vars = { "cmd": "test2" }
                run = "echo {cmd}"

                [/r/c/b]
                run = "echo {cmd2}"

                [/r/d]
                run = "echo {cmd3}"
                """, True)

        git_results.run(shlex.split("r/a -m 'h'"))
        git_results.run(shlex.split("r/b -m 'h'"))
        git_results.run(shlex.split("r/c/a -m 'h'"))
        git_results.run(shlex.split("r/c/b -m 'h'"))
        git_results.run(shlex.split("r/d -m 'h'"))

        self.assertEqual("test\n", open("r/a/1/stdout").read())
        self.assertEqual("test ok\n", open("r/b/1/stdout").read())
        self.assertEqual("test2\n", open("r/c/a/1/stdout").read())
        self.assertEqual("test2 ok\n", open("r/c/b/1/stdout").read())
        self.assertEqual("test ok, really\n", open("r/d/1/stdout").read())


    def test_configVars_cycles(self):
        ## Ensure that a self-cycle is broken
        self._setupRepo()
        self._config("""
                [vars]
                a = "{a} a"

                [/]
                run = "echo {a}"
                """)

        try:
            git_results.run(shlex.split("r/a -m 'h'"))
        except ValueError as e:
            text = str(e)
        else:
            self.fail("Self-cycle passed rather than failing")

        print("Got error: {}".format(text))
        self.assertTrue("Cannot self-reference: a was '{a} a'" in text)


        self._config("""
                [vars]
                a = "{b}"
                b = "{a}"

                [/]
                run = "echo {a}"
                """, True)
        try:
            git_results.run(shlex.split("r/b -m 'h'"))
        except ValueError as e:
            text = str(e)
        else:
            self.fail("Cycle passed rather than failing")

        print("Got error: {}".format(text))
        self.assertTrue(
                "'a' seems cyclical on {'a', 'b'}: {b}" in text
                or "'b' seems cyclical on {'b', 'a'}: {a}" in text)


    def test_continuation(self):
        # Ensure that the next run # is one higher than the greatest.
        self._setupRepo()
        git_results.run(shlex.split("results/test/run -m 'h'"))
        git_results.run(shlex.split("results/test/run -m 'h'"))
        shutil.rmtree("results/test/run/1")
        git_results.run(shlex.split("results/test/run -m 'h'"))
        self.assertEqual(True, os.path.lexists("results/test/run/3"))


    def test_env(self):
        # Ensure that the environment of build / run / progress is different
        # from our environment.
        self._setupRepo()
        self._config("""
                [/results]
                run = "/bin/echo Lucky was $LUCKY"
                """)
        os.environ['LUCKY'] = '7'

        # Ensure behavior works without fix
        old = git_results.shellOpen
        def new(cmd):
            return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
        git_results.shellOpen = new
        try:
            git_results.run(shlex.split("results/t -m 'h'"))
            self.assertEqual("Lucky was 7\n",
                    open('results/t/1/stdout').read())
        finally:
            git_results.shellOpen = old

        # Ensure LUCKY is NOT present
        git_results.run(shlex.split("results/t -m 'h'"))
        self.assertEqual("Lucky was\n", open('results/t/2/stdout').read())

        # But show that LUCKY can be passed:
        self._config("""
                [/results]
                run = "LUCKY=8 /bin/bash -c '/bin/echo Lucky was $LUCKY'"
                """)
        git_results.run(shlex.split("results/t -m 'h'"))
        self.assertEqual("Lucky was 8\n", open('results/t/3/stdout').read())


    def test_failToMoveResults(self):
        # Ensure that if a result file fails to move, the test is marked as
        # failed
        old = git_results.FolderState.moveResultsTo
        def newMove(self, dir, trimCommonPaths = False):
            oldRename = os.rename
            def newRename(a, b):
                print("RENAMING {}".format(a))
                if os.path.basename(a) == "blah":
                    raise OSError(88, "blah is a silly file")
                else:
                    return oldRename(a, b)
            os.rename = newRename
            try:
                return old(self, dir, trimCommonPaths = trimCommonPaths)
            finally:
                os.rename = oldRename
        git_results.FolderState.moveResultsTo = newMove
        try:
            self._setupRepo()
            self._config("""
                    run = "echo yodel > alpha; echo gosh > blah; echo gee > cansas"
                    """)

            ctmp = None
            if os.path.lexists('results/.tmp'):
                ctmp = os.listdir('results/.tmp')

            with self.assertRaises(SystemExit):
                git_results.run(shlex.split("results/test/run -m 'h'"))

            self.assertEqual(True, os.path.lexists("results/test/run/1"))
            self.assertEqual(False, os.path.lexists("results/test/run/1-fail"))
            self.assertEqual(True, os.path.lexists("results/test/run/1/alpha"))
            self.assertEqual(False, os.path.lexists("results/test/run/1/blah"))
            self.assertEqual(True, os.path.lexists("results/test/run/1/cansas"))
            self.assertIn("blah: OSError: [Errno 88] blah is a silly file\n",
                    open("results/test/run/1/stderr").read())

            # Ensure that the .tmp directory wasn't deleted
            if ctmp is None:
                self.assertEqual(True, os.path.lexists('results/.tmp'))
            else:
                self.assertNotEqual(ctmp, os.listdir('results/.tmp'))

            # And that the blah file resides there
            self.assertEqual(True, os.path.lexists(
                    "results/test/run/1/git-results-tmp/blah"))
            self.assertEqual(False, os.path.lexists(
                    "results/test/run/1/git-results-tmp/alpha"))
        finally:
            git_results.FolderState.moveResultsTo = old


    def test_ignoreExt(self):
        # Make sure ignoreExt works
        self._setupRepo()
        self._config("""
                [/]
                ignoreExt = [ "a", "c" ]
                run = "touch 1.a && touch 1.b && touch 1.c && touch 1.d"
                """)
        git_results.run(shlex.split("results/test -m 'h'"))
        self.assertFalse(os.path.lexists("results/test/1/1.a"))
        self.assertTrue(os.path.lexists("results/test/1/1.b"))
        self.assertFalse(os.path.lexists("results/test/1/1.c"))
        self.assertTrue(os.path.lexists("results/test/1/1.d"))


    def test_indexAbort(self):
        # Ensure that failed build (which deletes the tag), remains marked
        # (gone) forever.  Also ensure that next run gets the same message by
        # default
        self._setupRepo()
        git_results.run(shlex.split("results/test/run -m 'h'"))

        self._config("""
                [/]
                build = "hehehihoweihfowhef"
                """)
        try:
            git_results.run(shlex.split("results/test/run -m 'h1'"))
            self.fail("Build didn't fail?")
        except SystemExit:
            pass
        self.assertEqual("1 (  ok) - h\n2 (gone) - h1\n",
                open('results/test/run/INDEX').read())

        os.environ['EDITOR'] = 'echo ", now h2" >>'
        self._config("""
                [/]
                build = "cp hello_world hello_world_2"
                """)
        git_results.run(shlex.split("results/test/run"))
        self.assertEqual("1 (  ok) - h\n2 (  ok) - h1, now h2\n",
                open('results/test/run/INDEX').read())


    def test_indexUtils(self):
        # Check index stuff
        self._setupRepo()
        def contents(f):
            with open(f + '/INDEX') as fp:
                return fp.read()
        git_results.indexWrite("", "a/b/1", "move", "    Here is a message!    ")
        self.assertEqual("1 (move) - Here is a message!\n", contents("a/b"))
        self.assertEqual( ('1', 'move', 'Here is a message!'),
                git_results.indexRead("", "a/b/1"))

        git_results.indexWrite("", "a/b/2", "  ok", "I was ok")
        self.assertEqual("1 (move) - Here is a message!\n2 (  ok) - I was ok\n",
                contents("a/b"))
        self.assertEqual( ('1', 'move', 'Here is a message!'),
                git_results.indexRead("", "a/b/1"))
        self.assertEqual( ('2', '  ok', 'I was ok'),
                git_results.indexRead("", "a/b/2"))

        git_results.indexWrite("", "a/b/1", "fail", "Here lies a longer message")
        self.assertEqual("1 (fail) - Here lies a longer message\n2 (  ok) - I was ok\n",
                contents("a/b"))
        self.assertEqual( ('1', 'fail', 'Here lies a longer message'),
                git_results.indexRead("", "a/b/1"))
        self.assertEqual( ('2', '  ok', 'I was ok'),
                git_results.indexRead("", "a/b/2"))


    def test_inPlace(self):
        # Ensure that in-place works
        self._setupRepo()
        try:
            git_results.run(shlex.split("-i wresults/in/place -m 'hmm'"))
        except SystemExit as e:
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
            git_results.run(shlex.split('qresults/test/run -m "Take 2"'))
        except SystemExit as e:
            self.fail(str(e))

        # Check that our commit properly ignored stuff
        self.assertTrue(checked([ "git", "status", "--porcelain", "--ignored",
                "qresults" ])
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
        self.initAndChdirTmp()
        checked([ "git", "init" ])
        self._config(r"""
                [/]
                run = 'echo "Hello, world"'
                """)
        try:
            git_results.run(shlex.split("results/test/run -m \"Let's see if it "
                    "prints\""))
        except SystemExit as e:
            self.fail(str(e))
        self.assertEqual("Hello, world\n",
                open("results/test/run/1/stdout").read())


    def test_tagFail(self):
        # Induce a scenario where a tag exists and we try to write over it.
        # Ensure that the folder no longer exists
        self._setupRepo()

        git_results.run(shlex.split('results/test -m "take 1"'))
        self.assertTrue(os.path.lexists("results/test/1"))
        # Note that the tag isn't deleted!
        shutil.rmtree("results")

        with self.assertRaises(Exception):
            git_results.run(shlex.split('results/test -m "take 2"'))
        # Ensure our folder doesn't exist
        self.assertFalse(os.path.lexists("results/test/1"))


    def test_tagNextFromIndex(self):
        # Ensure that the next test number comes not only from folders, but
        # also the index
        self._setupRepo()

        git_results.run(shlex.split('results/test -m "take 1"'))
        self.assertTrue(os.path.lexists("results/test/1"))
        shutil.rmtree("results/test/1")
        git_results.run(shlex.split('results/test -m "take 2"'))
        self.assertTrue(os.path.lexists("results/test/2"))
        # Ensure multiline support works OK
        shutil.rmtree("results/test/2")
        git_results.run(shlex.split('results/test -m "take 3"'))
        self.assertTrue(os.path.lexists("results/test/3"))
