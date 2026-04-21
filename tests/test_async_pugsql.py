import asyncio

import pytest
import pytest_asyncio

import pugsql
from pugsql import exceptions


@pytest_asyncio.fixture
async def fixtures():
    f = pugsql.async_module("tests/sql/fixtures")
    f.connect("sqlite+aiosqlite:///./tests/data/fixtures.sqlite3")
    yield f
    await f.engine.dispose()


@pytest.mark.asyncio
async def test_async_module():
    assert pugsql.async_module("tests/sql").sqlpaths == {
        "tests/sql",
    }


@pytest.mark.asyncio
async def test_get_one(fixtures):
    result = await fixtures.user_for_id(user_id=1)
    assert {"username": "mcfunley", "user_id": 1} == result


@pytest.mark.asyncio
async def test_many(fixtures):
    result = await fixtures.search_users(username="oscar")
    assert [{"username": "oscar", "user_id": 2}] == list(result)


@pytest.mark.asyncio
async def test_update(fixtures):
    result = await fixtures.update_username(user_id=3, username="dottie")
    assert 1 == result


@pytest.mark.asyncio
async def test_where_in(fixtures):
    result = await fixtures.find_by_usernames(
        usernames=("oscar", "dottie")
    )
    assert [
        {"user_id": 2, "username": "oscar"},
        {"user_id": 3, "username": "dottie"},
    ] == list(result)


@pytest.mark.asyncio
async def test_where_in_list(fixtures):
    result = await fixtures.find_by_usernames(
        usernames=["oscar", "dottie"]
    )
    assert [
        {"user_id": 2, "username": "oscar"},
        {"user_id": 3, "username": "dottie"},
    ] == list(result)


@pytest.mark.asyncio
async def test_where_in_set(fixtures):
    result = await fixtures.find_by_usernames(
        usernames={"oscar", "dottie"}
    )
    assert [
        {"user_id": 2, "username": "oscar"},
        {"user_id": 3, "username": "dottie"},
    ] == list(result)


@pytest.mark.asyncio
async def test_where_in_multiple_parameters(fixtures):
    result = await fixtures.find_by_username_or_id(
        user_id=1, usernames=("oscar", "dottie")
    )
    assert [
        {"user_id": 1, "username": "mcfunley"},
        {"user_id": 2, "username": "oscar"},
        {"user_id": 3, "username": "dottie"},
    ] == list(result)


@pytest.mark.asyncio
async def test_insert(fixtures):
    async with fixtures.transaction() as t:
        pk = await fixtures.insert_user(username="little_pug")
        result = await fixtures.user_for_id(user_id=pk)
        assert {"username": "little_pug", "user_id": pk} == result
        await t.rollback()


@pytest.mark.asyncio
async def test_multi_insert(fixtures):
    async with fixtures.transaction() as t:
        await fixtures.insert_user(
            [
                {"username": "joe"},
                {"username": "paul"},
                {"username": "topper"},
                {"username": "mick"},
            ]
        )

        sr = list(await fixtures.search_users(username="topper"))
        assert "topper" == sr[0]["username"]
        await t.rollback()


@pytest.mark.asyncio
async def test_scalar(fixtures):
    result = await fixtures.username_for_id(user_id=1)
    assert "mcfunley" == result


@pytest.mark.asyncio
async def test_scalar_null(fixtures):
    result = await fixtures.username_for_id(user_id=666)
    assert result is None


@pytest.mark.asyncio
async def test_bad_path():
    with pytest.raises(
        ValueError, match="Directory not found: does/not/exist"
    ):
        pugsql.async_module("does/not/exist")


@pytest.mark.asyncio
async def test_empty_many(fixtures):
    result = await fixtures.search_users(username="asdfjasdj")
    assert [] == list(result)


@pytest.mark.asyncio
async def test_null_one(fixtures):
    result = await fixtures.user_for_id(user_id=4123423)
    assert result is None


@pytest.mark.asyncio
async def test_rolling_back_transaction(fixtures):
    class FooException(RuntimeError):
        pass

    try:
        async with fixtures.transaction():
            await fixtures.update_username(user_id=1, username="foo")
            result = await fixtures.user_for_id(user_id=1)
            assert {"username": "foo", "user_id": 1} == result

            raise FooException()
    except FooException:
        pass

    result = await fixtures.user_for_id(user_id=1)
    assert {"username": "mcfunley", "user_id": 1} == result


@pytest.mark.asyncio
async def test_nesting_transactions(fixtures):
    async with fixtures.transaction():
        async with fixtures.transaction():
            result = await fixtures.user_for_id(user_id=1)
            assert {"username": "mcfunley", "user_id": 1} == result


@pytest.mark.asyncio
async def test_transaction_not_connected():
    f = pugsql.async_module("tests/sql/fixtures")
    f.disconnect()
    with pytest.raises(exceptions.NoConnectionError):
        async with f.transaction():
            pass


@pytest.mark.asyncio
async def test_not_connected():
    f = pugsql.async_module("tests/sql/fixtures")
    f.disconnect()
    with pytest.raises(exceptions.NoConnectionError):
        await f.user_for_id(user_id=1)


@pytest.mark.asyncio
async def test_iterable(fixtures):
    names = {s.name for s in fixtures}
    assert names == {
        "find_by_username_or_id",
        "find_by_usernames",
        "insert_user",
        "search_users",
        "update_username",
        "user_for_id",
        "username_for_id",
        "find_date",
        "delete_by_usernames",
    }


@pytest.mark.asyncio
async def test_positional_args_mistake(fixtures):
    with pytest.raises(
        exceptions.InvalidArgumentError,
        match="Pass keyword arguments to statements",
    ):
        await fixtures.find_by_username_or_id(1, ("oscar", "dottie"))


@pytest.mark.asyncio
async def test_mixed_positional_args_mistake(fixtures):
    with pytest.raises(
        exceptions.InvalidArgumentError,
        match="Pass keyword arguments to statements",
    ):
        await fixtures.find_by_username_or_id(
            1, usernames=("oscar", "dottie")
        )


@pytest.mark.asyncio
async def test_nesting_transactions_rollback(fixtures):
    id = None
    id2 = None
    async with fixtures.transaction() as tr1:
        id = await fixtures.insert_user(username="little_bug")
        async with fixtures.transaction() as tr2:
            result = await fixtures.user_for_id(user_id=1)
            assert {"username": "mcfunley", "user_id": 1} == result
            id2 = await fixtures.insert_user(username="little_bug2")
            await tr2.commit()
        await tr1.rollback()

    result = await fixtures.user_for_id(user_id=id)
    assert result != {"username": "little_bug", "user_id": id}
    result2 = await fixtures.user_for_id(user_id=id2)
    assert result2 != {"username": "little_bug2", "user_id": id2}


@pytest.mark.asyncio
async def test_nesting_transactions_rollback_inner(fixtures):
    async with fixtures.transaction() as outer:
        await fixtures.insert_user(username="scratch1")
        async with fixtures.transaction() as inner:
            await fixtures.insert_user(username="scratch2")
            await inner.rollback()

        result = await fixtures.find_by_usernames(
            usernames={"scratch1", "scratch2"}
        )
        users = {u["username"] for u in result}
        assert users == {"scratch1"}
        await outer.rollback()


@pytest.mark.asyncio
async def test_concurrent_queries(fixtures):
    """Test that multiple async tasks can execute concurrently."""
    async def query_user(user_id):
        return await fixtures.user_for_id(user_id=user_id)

    results = await asyncio.gather(
        query_user(1),
        query_user(2),
        query_user(3),
    )
    assert results[0] == {"username": "mcfunley", "user_id": 1}
    assert results[1] == {"username": "oscar", "user_id": 2}
    assert results[2] == {"username": "dottie", "user_id": 3}
