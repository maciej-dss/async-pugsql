"""
Async compiled SQL function objects.
"""

from contextvars import ContextVar
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

import sqlalchemy

from .statement import Result, _compile_context
from .exceptions import InvalidArgumentError

if TYPE_CHECKING:
    from .async_compiler import AsyncModule


class AsyncStatement(object):
    """
    An async version of Statement that awaits module._execute().
    """

    def __init__(
        self,
        name: str,
        sql: str,
        doc: str,
        result: Result,
        filename: Optional[str] = None,
    ):
        self.filename = filename

        if not name:
            self._value_err("Statement must have a name.")

        if sql is None:
            self._value_err("Statement must have a SQL string.")
        sql = sql.strip()
        if not len(sql):
            self._value_err("SQL string cannot be empty.")

        if not result:
            self._value_err("Statement must have a result type.")

        self.name = name
        self.sql = sql
        self.__doc__ = doc
        self.result = result
        self.filename = filename
        self._module = None
        self._text = sqlalchemy.sql.text(self.sql)

    def _value_err(self, msg):
        if self.filename:
            raise ValueError("%s In: %s" % (msg, self.filename))
        raise ValueError(msg)

    def set_module(self, module: "AsyncModule"):
        self._module = module

    def _assert_module(self) -> "AsyncModule":
        if self._module is None:
            raise RuntimeError(
                "This statement is not associated with a module"
            )
        return self._module

    async def __call__(self, *multiparams, **params):
        module = self._assert_module()
        multiparams, params = self._convert_params(multiparams, params)
        self._validateMultiparams(params, multiparams)
        with _compile_context(multiparams, params):
            try:
                r = await module._execute(
                    self._text, *multiparams, **params
                )
            except AttributeError as e:
                if str(e) == "'tuple' object has no attribute 'keys'":
                    self._positionalArgError()
                raise
        return self.result.transform(r)

    def _validateMultiparams(self, params, multiparams):
        if not len(multiparams):
            return

        if len(params):
            self._positionalArgError()

        for p in multiparams:
            if not type(p) in {dict, list, set, tuple}:
                self._positionalArgError()

    def _positionalArgError(self):
        raise InvalidArgumentError(
            "Pass keyword arguments to statements (received "
            "positional arguments)."
        )

    def _convert_params(self, multiparams, params):
        def conv(x):
            if isinstance(x, set) or isinstance(x, list):
                return tuple(x)
            return x

        return (
            [conv(p) for p in multiparams],
            {k: conv(v) for k, v in params.items()},
        )

    def _param_names(self):
        def kfn(p):
            return self.sql.index(":" + p)

        return sorted(self._text._bindparams.keys(), key=kfn)

    def __str__(self):
        paramstr = ", ".join(["%s=None" % k for k in self._param_names()])
        return "pugsql.async_statement.AsyncStatement: %s(%s) :: %s" % (
            self.name,
            paramstr,
            self.result.display_type,
        )

    def __repr__(self):
        return str(self)

    @classmethod
    def from_statement(cls, stmt):
        """
        Creates an AsyncStatement from a parsed (sync) Statement.
        """
        return cls(
            name=stmt.name,
            sql=stmt.sql,
            doc=stmt.__doc__,
            result=stmt.result,
            filename=stmt.filename,
        )
