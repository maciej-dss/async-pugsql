"""
PugSQL is an anti-ORM that facilitates interacting with databases using SQL
in files. A minimal usage example:

    # create a module from sql files on disk
    queries = pugsql.module('path/to/sql/files')

    # connect to the database and use the sql queries as functions
    queries.connect(connection_string)
    queries.update_username(user_id=42, username='mcfunley')

For async usage:

    # create an async module from sql files on disk
    queries = pugsql.async_module('path/to/sql/files')

    # connect to the database with an async connection string
    queries.connect('sqlite+aiosqlite:///path/to/db.sqlite3')

    # use the sql queries as async functions
    result = await queries.update_username(user_id=42, username='mcfunley')

"""

from . import compiler
from . import async_compiler

__version__ = "0.3.7"


def module(sqlpath, encoding=None) -> compiler.Module:
    """
    Compiles a set of SQL files in the directory specified by sqlpath, and
    returns a module. The module contains a function for each named query
    found in the files.

        # create a module from sql files on disk
        queries = pugsql.module('path/to/sql/files')

        # connect to the database and use the sql queries as functions
        queries.connect(connection_string)
        queries.update_username(user_id=42, username='mcfunley')
    """
    return compiler.Module(sqlpath, encoding=encoding)


def async_module(sqlpath, encoding=None) -> async_compiler.AsyncModule:
    """
    Compiles a set of SQL files in the directory specified by sqlpath, and
    returns an async module. The module contains an async function for each
    named query found in the files.

        # create an async module from sql files on disk
        queries = pugsql.async_module('path/to/sql/files')

        # connect with an async-compatible connection string
        queries.connect('sqlite+aiosqlite:///path/to/db.sqlite3')

        # use the sql queries as async functions
        result = await queries.update_username(
            user_id=42, username='mcfunley'
        )
    """
    return async_compiler.AsyncModule(sqlpath, encoding=encoding)


__all__ = [
    "__version__",
    "module",
    "async_module",
]
