import asyncio

from server.core.bus import Bus
from server.tests.support import wait_until


def test_publish_delivers_to_subscriber():
    async def body():
        bus = Bus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("topic", handler)
        bus.publish("topic", "hello")
        await wait_until(lambda: received == ["hello"])
        assert received == ["hello"]

    asyncio.run(body())


def test_delivery_order_is_fifo_per_subscriber():
    async def body():
        bus = Bus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("topic", handler)
        for i in range(5):
            bus.publish("topic", i)
        await wait_until(lambda: len(received) >= 5)
        assert received == [0, 1, 2, 3, 4]

    asyncio.run(body())


def test_publish_with_no_subscribers_does_not_raise():
    Bus().publish("nobody-listening", "event")


def test_unsubscribe_stops_further_delivery():
    async def body():
        bus = Bus()
        received = []

        async def handler(event):
            received.append(event)

        unsubscribe = bus.subscribe("topic", handler)
        unsubscribe()
        bus.publish("topic", "should not arrive")
        for _ in range(5):
            await asyncio.sleep(0)
        assert received == []

    asyncio.run(body())


def test_subscriber_exception_does_not_kill_the_consumer_loop():
    async def body():
        bus = Bus()
        received = []

        async def sometimes_failing_handler(event):
            if event == "boom":
                raise ValueError("boom")
            received.append(event)

        bus.subscribe("topic", sometimes_failing_handler)
        bus.publish("topic", "boom")
        bus.publish("topic", "after")
        await wait_until(lambda: received == ["after"])
        assert received == ["after"]

    asyncio.run(body())


def test_slow_subscriber_does_not_block_publish():
    async def body():
        bus = Bus()
        started = asyncio.Event()

        async def slow_handler(event):
            started.set()
            await asyncio.sleep(10)

        bus.subscribe("topic", slow_handler)
        bus.publish("topic", "event")
        # publish() never awaits, so this proves control returned immediately
        # rather than waiting out the handler's 10s sleep.
        await asyncio.wait_for(started.wait(), timeout=1)

    asyncio.run(body())


def test_full_queue_drops_the_event_instead_of_blocking():
    async def body():
        bus = Bus()
        release = asyncio.Event()
        received = []

        async def handler(event):
            if event == "block":
                await release.wait()
            else:
                received.append(event)

        bus.subscribe("topic", handler, maxsize=1)
        bus.publish("topic", "block")
        for _ in range(5):
            await asyncio.sleep(0)  # let the consumer task pick "block" up
        bus.publish("topic", "fills-queue")
        bus.publish("topic", "dropped")  # queue already full -> silently dropped
        release.set()
        await wait_until(lambda: received == ["fills-queue"])
        assert received == ["fills-queue"]

    asyncio.run(body())
