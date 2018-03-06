import asyncio
import cProfile
import unittest

from leoorm.utils import create_db_pool
from leoorm.debug import Measure, profile_block
from leoorm import LeoORM
from .models import Author


class LeoORMTestCase(unittest.TestCase):
    pool = None
    loop = None
    multi_db = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.async_init())

    def _run_coro(self, coro):
        async def decorated():
            async with self.pool.acquire() as db_conn:
                orm = LeoORM(conn=db_conn)
                await coro(orm)
        self.loop.run_until_complete(decorated())

    async def async_init(self):
        self.pool = await create_db_pool(loop=self.loop)
    #
    # def test_count(self):
    #     Author.objects.all().delete()
    #     author = Author.objects.create(name='john smith')
    #     self.assertEquals(Author.objects.count(), 1)
    #
    #     @self._run_coro
    #     async def test(orm):
    #         self.assertEquals(await orm.count(Author), 1)
    #
    # def test_get(self):
    #     Author.objects.all().delete()
    #     author = Author.objects.create(name='john smith 2')
    #     self.assertEquals(Author.objects.count(), 1)
    #
    #     @self._run_coro
    #     async def test(orm):
    #         author2 = await orm.get(Author, name='john smith 2')
    #         self.assertEquals(author2.id, author.id)

    def test_speed_create(self, n=1000):
        Author.objects.all().delete()
        ms = Measure()
        # with profile_block():
        Author.objects.bulk_create([
            Author(name='john smith {}'.format(i))
            for i in range(n)
        ])
        self.assertEquals(Author.objects.count(), n)
        print('test_speed_create: django: {}'.format(ms))

        @self._run_coro
        async def test(orm):
            ms = Measure()
            # with profile_block():
            await orm.save([
                Author(name='john smith {}'.format(i))
                for i in range(n)
            ])
            self.assertEquals(await orm.count(Author), n * 2)
            print('test_speed_create: leoorm: {}'.format(ms))
