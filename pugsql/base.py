"""
Base module containing shared SQL file loading logic for both sync and async
modules.
"""

import os
import re
from glob import glob
from typing import Optional

from . import context, parser
from .exceptions import NoConnectionError

__pdoc__ = {}


class BaseModule(object):
    """
    Base class for SQL modules. Provides shared SQL file loading logic.
    Subclasses must implement connection management and execution.
    """

    sqlpaths: set
    engine = None

    def __init__(self, sqlpath: str, encoding: Optional[str] = None):
        """
        Loads functions found in the *sql files specified by `sqlpath` into
        properties on this object. An `encoding` for the files can optionally
        be provided.

        The named sql functions in files should be unique.
        """
        self.sqlpaths = set()
        self._statements = {}

        self.add_queries(sqlpath, encoding=encoding)

    def add_queries(self, *paths: str, encoding: Optional[str] = None):
        """
        Adds queries from *sql files in one or more `paths` to the module.
        An `encoding` for the files can optionally be provided.

        The named sql functions in files should be unique.
        """
        for p in paths:
            self._add_path(p, encoding=encoding)
        self.sqlpaths |= set(paths)

    def _add_path(self, sqlpath: str, encoding: Optional[str] = None):
        if not os.path.isdir(sqlpath):
            raise ValueError("Directory not found: %s" % sqlpath)

        for sqlfile in sorted(glob(os.path.join(sqlpath, "*sql"))):
            with open(sqlfile, "r", encoding=encoding) as f:
                pugsql = f.read()

            # handle multiple statements per file
            statements = re.split(r"\n+(?=--+\s*:name)", pugsql)
            statement_line = 0
            for statement in statements:
                s = parser.parse(statement, ctx=context.Context(sqlfile,
                                 line=statement_line))
                statement_line += len(statement.splitlines()) + 1

                if hasattr(self, s.name):
                    if s.name not in self._statements:
                        raise ValueError(
                            'Error loading %s - the function name "%s" is '
                            "reserved. Please choose another name."
                            % (sqlfile, s.name)
                        )
                    raise ValueError(
                        "Error loading %s - a SQL function named %s was "
                        "already defined in %s."
                        % (sqlfile, s.name, self._statements[s.name].filename)
                    )

                s = self._wrap_statement(s)
                s.set_module(self)

                setattr(self, s.name, s)
                self._statements[s.name] = s

    def _wrap_statement(self, statement):
        """
        Hook for subclasses to wrap or convert parsed statements.
        The default implementation returns the statement unchanged.
        """
        return statement

    @property
    def _dialect(self):
        """
        Gets the dialect for the SQLAlchemy engine.
        """
        if not self.engine:
            raise NoConnectionError()
        return self.engine.dialect

    def disconnect(self):
        """
        Disassociates the module from any connection it was previously given.
        """
        self.engine = None
        self._sessionmaker = None

    def __iter__(self):
        return iter(self._statements.values())


__pdoc__["BaseModule.sqlpaths"] = (
    "A list of paths that the module was loaded from."
)
__pdoc__["BaseModule.engine"] = (
    "The sqlalchemy engine object being used by the module."
)
