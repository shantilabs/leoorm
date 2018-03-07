import base64

from django.conf import settings
from django.contrib.sessions.models import Session


async def get_dj_session(orm, cookies):
    import ujson
    # FIXME: non-dbbackend and non-json support
    session_key = cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_key:
        return {}

    dj_sess = await orm.get(Session, session_key=session_key)
    if not dj_sess:
        return {}

    # FIXME: hash checking
    _hash, decoded = base64.b64decode(dj_sess.session_data).split(b':', 1)
    return ujson.loads(decoded)


async def create_db_pool(using='default', **kwargs):
    import asyncpg
    return await asyncpg.create_pool(
        user=settings.DATABASES[using]['USER'],
        password=settings.DATABASES[using]['PASSWORD'],
        database=settings.DATABASES[using]['NAME'],
        host=settings.DATABASES[using]['HOST'],
        **kwargs
    )
