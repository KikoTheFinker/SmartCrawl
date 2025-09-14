import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Generic, TypeVar, Set, List

T = TypeVar('T')
R = TypeVar('R')


class AsyncWorkerPool(Generic[T, R]):
    def __init__(self, concurrency: int, processor: Callable[[T], R]):
        self.concurrency = concurrency
        self.processor = processor
        self.semaphore = asyncio.Semaphore(concurrency)
        self.processed_items: Set[T] = set()
        self.results: Set[R] = set()

    async def process_items(self, initial_items: list[T]) -> Set[R]:
        if not initial_items:
            return set()

        queue = asyncio.Queue()
        stop_event = asyncio.Event()

        for item in initial_items:
            await queue.put(item)

        async def worker():
            while not stop_event.is_set():
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                if item in self.processed_items:
                    queue.task_done()
                    continue

                self.processed_items.add(item)

                async with self.semaphore:
                    try:
                        result = await self.processor(item)
                        if result:
                            self.results.add(result)
                    except Exception:
                        pass

                queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(self.concurrency)]

        await queue.join()

        stop_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        return self.results


class QueueProcessor(ABC, Generic[T, R]):
    def __init__(self, concurrency: int, worker_timeout: float = 30.0):
        self.concurrency = concurrency
        self.worker_timeout = worker_timeout

    @abstractmethod
    async def process_item(self, item: T) -> R:
        pass

    @abstractmethod
    async def get_next_items(self, item: T) -> List[T]:
        pass

    async def process_with_queue(self, initial_items: List[T]) -> Set[R]:
        if not initial_items:
            return set()

        queue = asyncio.Queue()
        processed_items: Set[T] = set()
        results: Set[R] = set()
        semaphore = asyncio.Semaphore(self.concurrency)
        stop_event = asyncio.Event()
        active_workers = 0

        for item in initial_items:
            await queue.put(item)

        async def worker():
            nonlocal active_workers
            active_workers += 1

            try:
                while not stop_event.is_set():
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue

                    if item in processed_items:
                        queue.task_done()
                        continue

                    processed_items.add(item)

                    async with semaphore:
                        try:
                            result = await asyncio.wait_for(
                                self.process_item(item),
                                timeout=self.worker_timeout
                            )
                            if result:

                                if isinstance(result, (set, list, tuple)):
                                    results.update(result)
                                else:
                                    results.add(result)

                            next_items = await asyncio.wait_for(
                                self.get_next_items(item),
                                timeout=self.worker_timeout
                            )
                            for next_item in next_items:
                                if next_item not in processed_items:
                                    await queue.put(next_item)

                        except asyncio.TimeoutError:
                            pass
                        except Exception:
                            pass

                    queue.task_done()
            finally:
                active_workers -= 1

        workers = [asyncio.create_task(worker()) for _ in range(self.concurrency)]

        try:
            await queue.join()
        finally:
            stop_event.set()
            if workers:
                await asyncio.gather(*workers, return_exceptions=True)

        return results
