"""
Async module that processes SQL files and returns async database functions.
Uses SQLAlchemy 2.0 async engine and sessions for true async execution.
"""

from contextvars import ContextVar
from contextlib import asynccontextmanager, suppress
from typing import Optional

from sqlalchemy.exc import ResourceClosedError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from .async_statement import AsyncStatement
from .base import BaseModule
from .exceptions import NoConnectionError

__pdoc__ = {}

_current_session: ContextVar[Optional[AsyncSession]] = ContextVar(
    "_current_session", default=None
)


class AsyncModule(BaseModule):
    """
    Holds a set of async SQL functions loaded from files. Uses SQLAlchemy 2.0
    async engine for true async database access.
    """

    def __init__(self, sqlpath: str, encoding: Optional[str] = None):
        """
        Loads functions found in the *sql files specified by `sqlpath` into
        properties on this object. An `encoding` for the files can optionally
        be provided.

        The named sql functions in files should be unique.
        """
        self._sessionmaker = None
        self._session_var = _current_session

        super().__init__(sqlpath, encoding=encoding)

    def _wrap_statement(self, statement):
        """
        Converts a parsed Statement into an AsyncStatement.
        """
        return AsyncStatement.from_statement(statement)

    @asynccontextmanager
    async def transaction(self):
        """
        Returns a session that manages an async transaction scope, in which
        many statements can be run. Statements run on this module will
        automatically use this transaction. The normal use case is to use this
        like an async context manager, rather than interact with the result:

            foo = pugsql.async_module('sql/foo')
            async with foo.transaction():
                x = await foo.get_x(x_id=1234)
                await foo.update_x(x_id=1234, x+1)

            # when the context manager exits, the transaction is committed.
            # if an exception occurs, it is rolled back.

        The transaction is active for statements executed in the current async
        task only (uses contextvars).

        For engines that support SAVEPOINT, calling this method a second time
        begins a nested transaction.

        For more info, see here:
        https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
        """
        if self._session_var.get() is None:
            if not self._sessionmaker:
                raise NoConnectionError()

            session = self._sessionmaker()
            token = self._session_var.set(session)

            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()
                self._session_var.reset(token)
        else:
            session = self._session_var.get()
            nested = await session.begin_nested()
            try:
                yield nested
            except Exception as e:
                await nested.rollback()
                raise e
            else:
                with suppress(ResourceClosedError):
                    await nested.commit()

    async def _execute(self, clause, *multiparams, **params):
        session = self._session_var.get()
        if session is not None:
            if multiparams:
                return await session.execute(clause, *multiparams)
            else:
                return await session.execute(clause, params)

        if not self.engine:
            raise NoConnectionError()

        async with self.engine.connect() as conn:
            if multiparams:
                result = await conn.execute(clause, *multiparams)
            else:
                result = await conn.execute(clause, params)
            await conn.commit()
            return result

    def connect(self, connstr, **kwargs):
        """
        Sets the connection string for async SQL functions on this module.

        Use an async-compatible connection string, e.g.:
            sqlite+aiosqlite:///path/to/db.sqlite3
            postgresql+asyncpg://user:pass@host/db

        See https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
        """
        self.setengine(create_async_engine(connstr, **kwargs))

    def setengine(self, engine):
        """
        Sets the SQLAlchemy async engine for SQL functions on this module.
        This can be used instead of the connect method, when more
        customization of the connection engine is desired.

        See also:
        https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
        """
        self.engine = engine
        self._sessionmaker = async_sessionmaker(bind=engine)


__pdoc__["AsyncModule.sqlpaths"] = (
    "A list of paths that the `pugsql.async_compiler.AsyncModule` "
    "was loaded from."
)
__pdoc__["AsyncModule.engine"] = (
    "The sqlalchemy async engine object being used by the "
    "`pugsql.async_compiler.AsyncModule`."
)
