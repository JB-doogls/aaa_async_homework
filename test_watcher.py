import asyncio
from typing import Any

import pytest
from asyncio import Queue

from abstract_watcher import AbstractRegistrator, AbstractWatcher, StudentWatcher


class ResultsRegistrator(AbstractRegistrator):
    def __init__(self):
        self.values = []
        self.errors = []

    def register_value(self, value: Any) -> None:
        self.values.append(value)

    def register_error(self, error: BaseException) -> None:
        self.errors.append(error)


@pytest.fixture
def registrator() -> ResultsRegistrator:
    return ResultsRegistrator()


@pytest.fixture
async def bcg(registrator: ResultsRegistrator) -> AbstractWatcher:
    # В тестах мы передадим в ваш Watcher нашу реализацию Registrator
    # и проверим корректность сохранения результатов
    obj = StudentWatcher(registrator)
    await obj.start()
    return obj


def assert_no_extra_running_tasks():
    assert len(asyncio.all_tasks()) == 1


@pytest.mark.asyncio
async def test_just_works(bcg: AbstractWatcher, registrator: ResultsRegistrator):
    async def toggler():
        return True

    coro = toggler()
    bcg.start_and_watch(coro)

    await bcg.stop()

    assert_no_extra_running_tasks()
    assert registrator.values == [True]
    assert not registrator.errors


@pytest.mark.asyncio
async def test_exception_handle(bcg: AbstractWatcher, registrator: ResultsRegistrator):
    value, error = 42, ValueError(r'("\(*;..;*)/")')

    async def good():
        return value

    async def bad():
        raise error

    bcg.start_and_watch(good())
    bcg.start_and_watch(bad())

    await bcg.stop()

    assert_no_extra_running_tasks()
    assert registrator.values == [value]
    assert registrator.errors == [error]


@pytest.mark.asyncio
async def test_ping_pong(bcg: AbstractWatcher, registrator: ResultsRegistrator):
    ping_chan = Queue(maxsize=1)
    pong_chan = Queue(maxsize=1)
    n_iterations = 5

    ball = '⚽'

    async def pinger():
        for _ in range(n_iterations):
            await pong_chan.put(ball)
            await ping_chan.get()

        return True

    async def ponger():
        for _ in range(n_iterations):
            await pong_chan.get()
            await ping_chan.put(ball)

        return True

    bcg.start_and_watch(pinger())
    bcg.start_and_watch(ponger())

    await bcg.stop()

    assert_no_extra_running_tasks()
    assert registrator.values == [True, True]
    assert not registrator.errors


@pytest.mark.asyncio
async def test_pipeline(bcg: AbstractWatcher, registrator: ResultsRegistrator):
    first = Queue(maxsize=1)
    second = Queue(maxsize=1)
    third = Queue(maxsize=1)

    ball = '⚽'

    async def worker(input: Queue, output: Queue):
        ball = await input.get()
        await output.put(ball)
        return True

    bcg.start_and_watch(worker(first, second))
    bcg.start_and_watch(worker(second, third))

    await first.put(ball)
    await bcg.stop()
    assert await third.get() == ball

    assert_no_extra_running_tasks()
    assert registrator.values == [True, True]
    assert not registrator.errors
