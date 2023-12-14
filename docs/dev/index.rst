Contributing to ``stellarphot``
-------------------------------

Setup
~~~~~

These steps typically only need to be done once.

1. To setup ``stellarphot`` for development, first create your own copy in GitHub
   by forking the repository.
2. Clone your fork to your local machine.
3. Add the main ``stellarphot`` repository as a remote called ``upstream``.

Steps when Contributing
~~~~~~~~~~~~~~~~~~~~~~~

These typically need to be done every time you make a contribution.

1.  Create a new branch for your contribution that is based on the branch
    ``upstream/main``. Give the branch a descriptive name. For example, if you
    are adding a new feature, you might call the branch ``add-new-feature``. These
    git command to do this would be ``git checkout -b add-new-feature upstream/main``.
2.  Write a test for your contribution. This should be a new test in the
    appropriate ``tests`` directory. If you are adding a new feature, you should add a new
    test file. If you are fixing a bug, you should add a new test to an
    existing test file. The test should be written using the ``pytest`` framework.
    See the ``tests`` directories for examples. **Make sure your test fails before
    you make your contribution.**
3.  Make your contribution. This could be a new feature, a bug fix, or a
    documentation update. **Make sure your test passes after you make your
    contribution.**
4.  Commit your contribution to your branch. Your commit message should be
    short but descriptive. For example, if you are adding a new feature, you might
    use a commit message like ``Add new feature to do X``.
5.  Push your branch to your fork on GitHub.
6.  Create a pull request from your branch to the ``main`` branch of the main
    ``stellarphot`` repository. Give the pull request a descriptive name and
    description. If your pull request fixes an issue, reference the issue in
    the description using the ``#`` symbol. For example, if your pull request
    fixes issue 123, you would write ``Fixes #123`` in the description.
7.  Wait for your pull request to be reviewed. If there are any issues, you
    may need to make additional commits to your branch to address them. If
    you need to make additional commits, make sure you push them to your
    fork on GitHub. The pull request will be updated automatically.

Some specific examples
~~~~~~~~~~~~~~~~~~~~~~

.. toctree::
    :maxdepth: 1

    settings
    moving_code