import logging
import time
import traceback
from contextlib import contextmanager

from django.conf import settings
from django.db.backends.utils import CursorDebugWrapper

logger = logging.getLogger('leoorm')


class Measure:
    def __init__(self, start=None):
        self.start = time.time() if start is None else start

    def _delta(self):
        return (time.time() - self.start) * 1000

    def __float__(self):
        return self._delta()

    def __int__(self):
        return int(self._delta())

    def __str__(self):
        return self.timeformat(self._delta())

    def __repr__(self):
        return '<Measure: %s>' % self

    @classmethod
    def timeformat(cls, delta_ms):
        if delta_ms > 60 * 1000:
            return '%d m' % (delta_ms / 1000 / 60)
        elif delta_ms > 1000:
            return '%.01f s' % (delta_ms / 1000)
        elif delta_ms > 10:
            return '%d ms' % delta_ms
        elif delta_ms > 1:
            return '%.01f ms' % delta_ms
        else:
            return '%.03f ms' % delta_ms


@contextmanager
def profile_block(sortby='cumulative'):
    if settings.DEBUG:
        import cProfile
        import pstats
        import io
        pr = cProfile.Profile()
        pr.enable()
        yield
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())
    else:
        yield


@contextmanager
def django_db_warning():
    class counter:  # для передачи по ссылке
        i = 0

    if settings.DEBUG:
        real_execute = CursorDebugWrapper.execute
        real_executemany = CursorDebugWrapper.executemany

        def _execute(self, sql, params=None):
            ms = Measure()
            real_execute(self, sql, params)
            counter.i += 1
            _warn(sql, counter.i, ms)

        def _executemany(self, sql, param_list):
            ms = Measure()
            real_executemany(self, sql, param_list)
            counter.i += 1
            _warn(sql, counter.i, ms)

        CursorDebugWrapper.execute = _execute
        CursorDebugWrapper.executemany = _executemany
        yield
        CursorDebugWrapper.execute = real_execute
        CursorDebugWrapper.executemany = real_executemany
    else:
        yield


def _warn(sql, i, ms):
    # from raven.contrib.django.raven_compat.models import client
    # client.captureMessage(f'django_db_warning: {sql}')
    logger.warning(
        'leoorm.django_db_warning: #%d %s: %s\n%s',
        i,
        ms,
        sql,
        FromLine(10),
    )


class FromLine:
    def __init__(self, depth=1, skip=(
        __file__,
        'django',
        'leoorm' ,
        'asyncio',
        'logging',
        'Cython',
        'unittest',
    )):
        self.depth = depth
        self.skip = skip

    def __str__(self):
        if not settings.DEBUG:
            return ''
        lines = []
        for line in reversed(traceback.format_stack()):
            if any(s in line for s in self.skip):
                continue
            lines.append(line.split('\n')[0].strip())
            if len(lines) >= self.depth:
                break
        return '\n'.join(lines)
