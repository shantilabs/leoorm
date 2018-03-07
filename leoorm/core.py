import json
import logging
from collections import namedtuple, defaultdict
from functools import lru_cache
from itertools import chain

import django.apps
from django.contrib.postgres.fields import JSONField
from django.db.models import FileField, OneToOneRel
from django.db.models.base import ModelState
from django.utils.functional import lazy
from django.utils.itercompat import is_iterable
from django.utils.timezone import now

from .debug import Measure, FromLine

logger = logging.getLogger('leoorm')


class LeoORM:
    def __init__(self, conn):
        self.conn = conn
        self.i = 0
        models = defaultdict(dict)
        for m in django.apps.apps.get_models(include_auto_created=True):
            models[m._meta.app_label][m._meta.object_name] = self.db_table(m)
        self.tables = {}
        for app, models in models.items():
            self.tables[app] = namedtuple(app, models)
            for k in models:
                setattr(self.tables[app], k, models[k])

    async def save(self, instance_or_list, **update_fields):
        """
        await orm.save(instance) -> instance
        await orm.save(instances) -> None
        await orm.save(instance, field1=value, field2=value, ...) -> instance
        """
        if not instance_or_list:
            return []
        if is_iterable(instance_or_list):
            return await self._save_bulk(instance_or_list)
        instance = instance_or_list
        model_class = instance.__class__
        if getattr(instance, self.pk(model_class)):
            return await self._update(instance, update_fields)
        assert not update_fields
        return await self._save_bulk([instance])

    async def _save_bulk(self, instances):
        if not instances:
            return
        first_obj = instances[0]
        model_class = first_obj.__class__
        pk = self.pk(model_class)
        assert not any(getattr(obj, pk) for obj in instances)
        names, values = self._names_values(instances)
        num_names = len(names)
        num_instances = len(instances)
        sql = (
            'INSERT INTO {db_table} ({names}) '
            'VALUES {values} '
            'RETURNING {pk}'
        ).format(
            db_table=self.db_table(model_class),
            pk=pk,
            names=', '.join(names),
            values=', '.join('({})'.format(
                ', '.join('${}'.format(num_names * j + i + 1) for i in range(num_names))
            ) for j in range(num_instances)),
        )
        if num_instances == 1:
            args = values[0]
            coro = self.conn.fetchval(sql, *args)
            val = await self._exec(coro, 'leoorm._save_one', sql, args)
            first_obj.pk = val
            setattr(first_obj, pk, val)
            await self._call_post_save(model_class, [first_obj], True)
            return first_obj
        else:
            coro = self.conn.fetch(sql, *chain(*values))
            pks = await self._exec(coro, 'leoorm._save_many', sql)
            for obj, (val,) in zip(instances, pks):
                obj.pk = val
                setattr(obj, pk, val)
            await self._call_post_save(model_class, instances, True)
            return instances

    async def _call_post_save(self, model_class, objects, is_new):
        if not hasattr(model_class, 'async_post_save'):
            return
        for obj in objects:
            await obj.async_post_save(self, is_new)

    async def _update(self, instance, update_fields):
        model_class = instance.__class__
        names, values = self._names_values([instance], update_fields)
        sql = 'UPDATE {db_table} SET {values} WHERE {pk} = $1'.format(
            db_table=self.db_table(model_class),
            pk=self.pk(model_class),
            values=', '.join('{k} = ${i}'.format(
                k=k,
                i=i + 2,
            ) for i, k in enumerate(names)),
        )
        args = [instance.pk] + values[0]
        coro = self.conn.execute(sql, *args)
        await self._exec(coro, 'leoorm._update', sql, args)
        await self._call_post_save(model_class, [instance], False)
        return instance

    async def get(self, model_class, *args, **kwargs):
        """
        await orm.get(model_class, field1=value, field2=value, ...) -> instance or None
        await orm.get(model_class, SQL, arg1, arg2, ...) -> instance or None
        """
        if kwargs:
            assert not args
            cond, values = self._and(kwargs)
            sql = 'SELECT * FROM {db_table} WHERE {cond}'.format(
                db_table=self.db_table(model_class),
                cond=cond,
            )
        elif args:
            values = list(args)
            sql = self._norm_sql(values.pop(0))
        else:
            assert False
        coro = self.conn.fetchrow(sql, *values)
        data = await self._exec(coro, 'leoorm.get', sql, values)
        return self.to_model(model_class, data) if data else None

    async def get_list(self, model_class, *args, **kwargs):
        """
        await orm.get_list(model_class, field1=value, field2=value, ...) -> [instance]
        await orm.get_list(model_class, SQL, arg1, arg2, ...) -> [instance]
        """
        if args:
            values = list(args)
            sql = self._norm_sql(values.pop(0))
        else:
            cond, values = self._and(kwargs)
            sql = 'SELECT * FROM {db_table} {maybecond} {maybeordering}'.format(
                db_table=self.db_table(model_class),
                maybecond='WHERE {}'.format(cond) if cond else '',
                maybeordering='ORDER BY {}'.format(', '.join(
                    f'{f[1:]} DESC'
                    if f.startswith('-') else f
                    for f in model_class._meta.ordering)
                ) if model_class._meta.ordering else '',
            )
        coro = self.conn.fetch(sql, *values)
        res = await self._exec(coro, 'leoorm.get_list', sql, values)
        return [self.to_model(model_class, d) for d in res]

    async def count(self, model_class, **kwargs):
        """
        await orm.count(model_class, field1=value, field2=value, ...)
        """
        cond, values = self._and(kwargs)
        sql = 'SELECT COUNT(*) FROM {db_table} {maybecond}'.format(
            db_table=self.db_table(model_class),
            maybecond='WHERE {}'.format(cond) if cond else '',
        )
        coro = self.conn.fetchval(sql, *values)
        return await self._exec(coro, 'leoorm.count', sql)

    async def delete(self, instance, **kwargs):
        """
        await orm.delete(instance)
        await orm.delete(model_class, field=value, field2=value, ...)
        """
        if hasattr(instance, 'objects'):
            model_class = instance
            assert kwargs
        else:
            model_class = instance.__class__
            assert not kwargs
            kwargs = {self.pk(model_class): instance.pk}
        cond, values = self._and(kwargs)
        sql = 'DELETE FROM {db_table} {maybecond}'.format(
            db_table=self.db_table(model_class),
            maybecond='WHERE {}'.format(cond) if cond else '',
        )
        coro = self.conn.fetchval(sql, *values)
        return await self._exec(coro, 'leoorm.delete', sql, values)

    async def exec(self, sql, *values):
        sql = self._norm_sql(sql)
        coro = self.conn.fetchval(sql, *values)
        return await self._exec(coro, 'leoorm.exec', sql, values)

    async def get_raw_list(self, sql, *values):
        sql = self._norm_sql(sql)
        coro = self.conn.fetch(sql, *values)
        return await self._exec(coro, 'leoorm.get_raw_list', sql, values)

    async def prefetch(self, instance_or_list, *fields):
        """
        await orm.prefetch(instance, 'field', 'field', ...)
        await orm.prefetch([instance, instance], 'field', 'field', ...)
        """
        if is_iterable(instance_or_list):
            if not instance_or_list:
                return
            lst = list(instance_or_list)
            model_class = lst[0].__class__
            if any(not isinstance(instance, model_class) for instance in lst):
                raise ValueError(instance_or_list)
        else:
            if not instance_or_list:
                raise ValueError(instance_or_list)
            lst = [instance_or_list]
            model_class = instance_or_list.__class__
        fields = list(fields)
        model_fields = self._fields(model_class, one_to_one=True)
        for f in model_fields:
            if not f.is_relation or f.name not in fields:
                continue
            fields.remove(f.name)
            if hasattr(f, 'attname'):
                related_ids = {
                    getattr(instance, f.attname) for instance in lst
                    if not self.has_prefetched(instance, f.name) and
                    getattr(instance, f.attname)
                }
                if not related_ids:
                    continue
                logger.debug(
                    'leoorm.prefetch: %s from %s: %s',
                    f.name,
                    f.related_model.__qualname__,
                    related_ids,
                )
                related_objects = {
                    instance.pk: instance
                    for instance in await self.get_list(f.related_model, '''
                        SELECT * FROM {db_table} WHERE {pk} = ANY($1)
                    '''.format(
                        db_table=self.db_table(f.related_model),
                        pk=self.pk(f.related_model),
                    ), related_ids)
                }
                for instance in lst:
                    val = getattr(instance, f.attname)
                    if val and val in related_objects:
                        self.set_prefetched(instance, f.name, related_objects[val])  # noqa
                    elif not self.has_prefetched(instance, f.name):
                        self.set_prefetched(instance, f.name, None)
            else:
                one2one_ids = {
                    instance.pk for instance in lst
                    if not self.has_prefetched(instance, f.name) and instance.pk
                }
                logger.debug(
                    'leoorm.prefetch: %s from %s: %s',
                    f.name,
                    f.related_model.__qualname__,
                    one2one_ids,
                )
                if not one2one_ids:
                    continue
                one2one_objects = {
                    getattr(instance, f.field.column): instance
                    for instance in await self.get_list(
                        f.related_model,
                        **{f.field.column + '__in': one2one_ids}
                    )
                }
                for instance in lst:
                    val = one2one_objects.get(instance.pk)
                    self.set_prefetched(instance, f.name, val)

        if fields:
            raise ValueError('Incorrect fields: {}. Allowed: {}'.format(
                fields,
                ', '.join(f.name for f in model_fields)
            ))

    @classmethod
    def set_prefetched(cls, obj, *args, **kwargs):
        """
        orm.set_prefetched(instance, field, value)
        orm.set_prefetched(instance, field1=value1, field2=value2, ...)
        """
        if args:
            assert not kwargs and len(args) == 2
            name, rel_obj = args
            if is_iterable(obj):
                for x in obj:
                    setattr(x, '_{}_cache'.format(name), rel_obj)
                    cls._set_prefetched(x, name, rel_obj)
            else:
                cls._set_prefetched(obj, name, rel_obj)
        else:
            if is_iterable(obj):
                for name, rel_obj in kwargs.items():
                    for x in obj:
                        cls._set_prefetched(x, name, rel_obj)
            else:
                for name, rel_obj in kwargs.items():
                    cls._set_prefetched(obj, name, rel_obj)

    if hasattr(ModelState, 'fields_cache'):
        @classmethod
        def _set_prefetched(cls, obj, name,val):
            obj._state.fields_cache[name] = val

        @classmethod
        def has_prefetched(cls, obj, name):
            return name in obj._state.fields_cache
    else:
        @classmethod
        def _set_prefetched(cls, obj, name, val):
            setattr(obj, '_{}_cache'.format(name), val)

        @classmethod
        def has_prefetched(cls, obj, name):
            return hasattr(obj, '_{}_cache'.format(name))

    @classmethod
    def to_model(cls, model_class, d):
        instance = model_class(**d)
        for f in cls._fields(model_class):
            if isinstance(f, JSONField):
                val = getattr(instance, f.attname)
                if isinstance(val, str):
                    val = json.loads(val)
                setattr(instance, f.attname, val)
        return instance

    @classmethod
    def db_table(cls, obj):
        return obj._meta.db_table

    @classmethod
    def pk(cls, model_class):
        return model_class._meta.pk.name

    def _norm_sql(self, sql):
        return ' '.join(sql.format(**self.tables).strip().split())

    async def _exec(self, coro, name, sql, values=None):
        ms = Measure()
        self.i += 1
        try:
            result = await coro
        except:
            # from_line не надо, внизу целый traceback
            logger.error(
                '%s: #%d %s: %s %s',
                name,
                self.i,
                ms,
                sql,
                lazy(lambda: str(dict(enumerate(values, start=1)) if values else '')),  # noqa
            )
            raise
        logger.debug(
            '%s: #%d %s: %s %s\n%s',
            name,
            self.i,
            ms,
            sql,
            lazy(lambda: str(dict(enumerate(values, start=1)) if values else '')),  # noqa
            lazy(lambda: str(FromLine(1))),
        )
        return result

    _ops = {
        'gt': '>',
        'gte': '>=',
        'lt': '<',
        'lte': '<=',
        'in': 'ANY',
        'isnull': 'IS NULL',
    }

    def _and(self, kwargs):
        i = 1
        bits = []
        values = []
        for k in kwargs:
            if '__' in k:
                field, *etc = k.split('__')
                assert len(etc) == 1
                op = self._ops.get(etc[0])
                assert op, 'bad condition: {}'.format(k)
            else:
                field = k
                op = '='
            if kwargs[k] is None:
                assert op == '='
                bits.append('{} IS NULL'.format(field))
            else:
                if (
                    op == 'ANY' or
                    isinstance(kwargs[k], (list, set, dict, tuple))  # XXX:
                ):
                    kwargs[k] = list(kwargs[k])
                    bits.append('{} = ANY(${})'.format(field, i))
                elif op == 'IS NULL':
                    if kwargs[k]:
                        bits.append('{} IS NULL'.format(field))
                    else:
                        bits.append('{} IS NOT NULL'.format(field))
                    continue  # чтобы аргумен пропустить
                else:
                    bits.append('{} {} ${}'.format(field, op, i))
                values.append(kwargs[k])
                i += 1
        return ' AND '.join(bits), values

    def _names_values(self, instances, update_fields=None):
        names = []
        values = [[] for _ in instances]
        model_class = instances[0].__class__
        assert all(isinstance(obj, model_class) for obj in instances)

        for field in self._fields(model_class):
            if field.name == self.pk(model_class):
                continue
            if (
                not update_fields or
                field.attname in update_fields or  # 'task_group_id'
                field.name in update_fields  # 'task_group'
            ):
                names.append(field.column)
                for i, obj in enumerate(instances):
                    if update_fields:
                        if field.attname in update_fields:
                            val = update_fields[field.attname]
                            setattr(obj, field.attname, val)
                        elif field.name in update_fields:
                            rel_obj = update_fields[field.name]
                            val = None if rel_obj is None else rel_obj.pk
                            self.set_prefetched(obj, **{field.name: rel_obj})
                            setattr(obj, field.attname, val)
                        else:
                            continue
                    else:
                        val = getattr(obj, field.attname)
                    if isinstance(field, JSONField):
                        if val is not None:
                            val = json.dumps(val, ensure_ascii=False)
                    elif isinstance(field, FileField):
                        val = str(val)
                    if getattr(field, 'auto_now', False) or (
                        not val and getattr(field, 'auto_now_add', False)
                    ):
                        val = now()
                        setattr(obj, field.attname, val)
                    values[i].append(val)
        assert names
        if update_fields:
            assert len(update_fields) == len(names)
        return names, values

    @classmethod
    @lru_cache()
    def _fields(cls, model_class, one_to_one=False):
        result = []
        for f in model_class._meta.get_fields():
            if one_to_one and isinstance(f, OneToOneRel):
                result.append(f)
                continue
            if hasattr(f, 'attname') and not hasattr(f, 'm2m_column_name'):
                result.append(f)
                continue
        return result
