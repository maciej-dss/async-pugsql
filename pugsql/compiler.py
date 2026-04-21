"""
Code that processes SQL files and returns modules of database functions.
"""

import threading
from contextlib import contextmanager, suppress
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.exc import ResourceClosedError
from sqlalchemy.orm import sessionmaker

from .base import BaseModule
from .exceptions import NoConnectionError

__pdoc__ = {}


class Module(BaseModule):
    """
    Holds a set of SQL functions loaded from files.
    """

    def __init__(self, sqlpath: str, encoding: Optional[str] = None):
        """
        Loads functions found in the *sql files specified by `sqlpath` into
        properties on this object. An `encoding` for the files can optionally
        be provided.

        The named sql functions in files should be unique.
        """
        self._sessionmaker = None
        self._locals = threading.local()

        super().__init__(sqlpath, encoding=encoding)

    @contextmanager
    def transaction(self):
        """
        Returns a session that manages a transaction scope, in which
        many statements can be run. Statements run on this module will
        automatically use this transaction. The normal use case  is to use this
        like a context manager, rather than interact with the result:

            foo = pugsql.module('sql/foo')
            with foo.transaction():
                x = foo.get_x(x_id=1234)
                foo.update_x(x_id=1234, x+1)

            # when the context manager exits, the transaction is committed.
            # if an exception occurs, it is rolled back.

        The transaction is active for statements executed on the current thread
        only.

        For engines that support SAVEPOINT, calling this method a second time
        begins a nested transaction.

        For more info, see here:
        https://docs.sqlalchemy.org/en/13/orm/session_transaction.html
        """
        if not getattr(self._locals, "session", None):
            if not self._sessionmaker:
                raise NoConnectionError()

            self._locals.session = self._sessionmaker()

            session = self._locals.session
            try:
                yield session
                session.commit()
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
                self._locals.session = None
        else:
            session = self._locals.session.begin_nested()
            try:
                yield session
            except Exception as e:
                session.rollback()
                raise e
            else:
                with suppress(ResourceClosedError):
                    session.commit()

    def _execute(self, clause, *multiparams, **params):
        if getattr(self._locals, "session", None):
            if multiparams:
                return self._locals.session.execute(clause, *multiparams)
            else:
                return self._locals.session.execute(clause, params)

        if not self.engine:
            raise NoConnectionError()

        with self.engine.connect() as conn:
            if multiparams:
                result = conn.execute(clause, *multiparams)
            else:
                result = conn.execute(clause, params)
            conn.commit()
            return result

    def connect(self, connstr, **kwargs):
        """
        Sets the connection string for SQL functions on this module.

        See https://docs.sqlalchemy.org/en/13/core/engines.html for examples of
        legal connection strings for different databases.
        """
        self.setengine(create_engine(connstr, **kwargs))

    def setengine(self, engine):
        """
        Sets the SQLAlchemy engine for SQL functions on this module. This can
        be used instead of the connect method, when more customization of the
        connection engine is desired.

        See also: https://docs.sqlalchemy.org/en/13/core/connections.html
        """
        self.engine = engine
        self._sessionmaker = sessionmaker(bind=engine)


__pdoc__["Module.sqlpaths"] = (
    "A list of paths that the `pugsql.compiler.Module` was loaded from."
)
__pdoc__["Module.engine"] = (
    "The sqlalchemy engine object being used by the `pugsql.compiler.Module`."
)
