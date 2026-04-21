import pytest

from pugsql import async_compiler, exceptions
from pugsql.async_statement import AsyncStatement


class TestBasicAsyncCompiler:
    def test_setsattr(self):
        m = async_compiler.AsyncModule("tests/sql")
        assert m.username_for_id.name == "username_for_id"

    def test_sets_sqlpaths(self):
        m = async_compiler.AsyncModule("tests/sql")
        assert {"tests/sql"} == m.sqlpaths

    def test_function_redefinition(self):
        msg = (
            "Error loading tests/sql/duplicate-name/foo2.sql - a SQL function "
            "named foo was already defined in "
            "tests/sql/duplicate-name/foo.sql."
        )
        with pytest.raises(ValueError, match=msg):
            async_compiler.AsyncModule("tests/sql/duplicate-name")

    def test_reserved_function_name(self):
        msg = (
            "Error loading tests/sql/reserved/disconnect.sql - the function "
            'name "disconnect" is reserved. Please choose another name.'
        )
        with pytest.raises(ValueError, match=msg):
            async_compiler.AsyncModule("tests/sql/reserved")

    def test_multiple_statements_per_file(self):
        m = async_compiler.AsyncModule("tests/sql")
        assert m.basic_statement.name == "basic_statement"
        assert m.multiline_statement.name == "multiline_statement"
        assert m.extra_comments.name == "extra_comments"
        assert m.interstitial_comments.name == "interstitial_comments"
        assert m.multiline_syntax.name == "multiline_syntax"

    def test_statements_are_async(self):
        m = async_compiler.AsyncModule("tests/sql")
        assert isinstance(m.username_for_id, AsyncStatement)


class TestAsyncModuleConnection:
    def test_dialect_no_connection(self):
        m = async_compiler.AsyncModule("tests/sql")
        with pytest.raises(exceptions.NoConnectionError):
            _ = m._dialect

    def test_dialect_works(self):
        m = async_compiler.AsyncModule("tests/sql")
        m.connect("sqlite+aiosqlite:///./tests/data/fixtures.sqlite3")
        assert m._dialect.name == "sqlite"

    def test_add_queries(self):
        m = async_compiler.AsyncModule("tests/sql/mod1")
        m.add_queries("tests/sql/mod2")
        assert {"tests/sql/mod1", "tests/sql/mod2"} == m.sqlpaths
        assert isinstance(m.scalar, AsyncStatement)
        assert isinstance(m.insert, AsyncStatement)

    def test_disconnect(self):
        m = async_compiler.AsyncModule("tests/sql")
        m.connect("sqlite+aiosqlite:///./tests/data/fixtures.sqlite3")
        m.disconnect()
        assert m.engine is None
        assert m._sessionmaker is None
