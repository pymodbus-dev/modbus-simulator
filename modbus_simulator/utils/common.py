from __future__ import unicode_literals
from __future__ import absolute_import

import os
import json
import shutil


def path(name=""):
    """
    Retrieve the relative filepath to a supplied name 

    """
    if name.startswith(os.path.sep):
        return name
    actual = os.path.dirname(os.path.abspath(__file__)).split(os.path.sep)[:-3]
    if name:
        actual.extend(name.split(os.path.sep))
    return os.path.join(os.path.sep, *actual)


def from_this_dir(cur_dir, filename=""):
    """
    Returns the absolute path to a relative `filename` by joining it with
    the absolute dir from `cur_dir`.

    If the filename starts with the os path separator, it is considered an
    absolute path and returned as is.

    Args:
        cur_dir: The path to a dir whose directory name must be
            used as the base.
        filename: The relative filename or path which must be joined with
            cur_dir.

    """
    if filename.startswith(os.path.sep):
        return filename
    else:
        return os.path.join(os.path.abspath(cur_dir), filename)


def from_this_file(cur_file, filename=""):
    """
    Returns the absolute path to a relative `filename` by joining it with
    the absolute dir from `cur_file`. To get a file in the current script's
    directory call `from_this_file(__file__, "filename")`.

    If the filename starts with the os path separator, it is considered an
    absolute path and returned as is.

    Args:
        cur_file: The path to a file whose directory name must be
            used as the base.
        filename: The relative filename or path which must be joined to the
            cur_file's dirname.

    """
    cur_dir = os.path.dirname(cur_file)
    return from_this_dir(cur_dir, filename)


def from_cwd(filename=""):
    """
    Returns the absolute path to a relative `filename` by joining it with
    the current working directory.

    If the filename starts with the os path separator, it is considered an
    absolute path and returned as is.

    Args:
        filename: The relative filename or path which must be joined with
            the current working directory.

    """
    if filename.startswith(os.path.sep):
        return filename
    else:
        return os.path.join(os.getcwd(), filename)


def make_dir(name):
    """
    mkdir -p <name> if it doesn't exist.
    """
    if not os.path.exists(name):
        os.makedirs(name)


def remove_file(name):
    if os.path.exists(name):
        os.remove(name)


def remove_dir(name):
    """
    rm -rf <name> if it exists.
    """
    if os.path.exists(name):
        shutil.rmtree(name)
