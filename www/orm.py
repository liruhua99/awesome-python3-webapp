#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Li Ruhua'

import logging, asyncio, aiomysql

def log(sql, args = ()):
    logging.info('SQL: {0}'.format(sql))

######## 数据库操作协程 ########
async def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host', 'localhost'),
        port = kw.get('port', 3306),
        user = kw['user'],
        password = kw['password'],
        db = kw['db'],
        charset = kw.get('charset', 'utf8'),
        autocommit = kw.get('autocommit', True),
        maxsize = kw.get('maxsize', 10),
        minsize = kw.get('minsize', 1),
        loop = loop
        )

async def select(sql, args, size = None):
    log(sql, args)
    global __pool
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args or ())
            rs = await (cur.fetchmany(size) if size else cur.fetchall())
        logging.info('rows returned: {0}'.format(len(rs)))
        return rs

async def execute(sql, args, autocommit = True):
    log(sql)
    global __pool
    async with __pool.get() as conn:
        if not autocommit: await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit: await conn.commit()
        except BaseException as e:
            if not autocommit: await conn.rollback()
            raise
        return affected

######## 数据库字段类 ########
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<{0}, {1}:{2}>'.format(self.__class__.__name__, self.column_type, self.name)

class StringField(Field):
    def __init__(self, name = None, primary_key = False, default = None, ddl = 'varchar(100)'):
        super(StringField, self).__init__(name, ddl, primary_key, default)

class BooleanField(Field):
    def __init__(self, name = None, default = False):
        super(BooleanField, self).__init__(name, 'boolean', False, default)

class IntegerField(Field):
    def __init__(self, name = None, primary_key = False, default = 0):
        super(IntegerField, self).__init__(name, 'bigint', primary_key, default)

class FloatField(Field):
    def __init__(self, name = None, primary_key = False, default = 0.0):
        super(FloatField, self).__init__(name, 'real', primary_key, default)

class TextField(Field):
    def __init__(self, name = None, default = None):
        super(TextField, self).__init__(name, 'text', False, default)

######## ORM模型 ########
def create_args_string(num):
    return ', '.join(['?' for n in range(num)])

class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model': # 排除Model类本身
            return type.__new__(cls, name, bases, attrs)
        # 获取数据表名称
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: {0} (table: {1})'.format(name, tableName))
        # 获取所有的字段和主键
        mappings = dict(); fields = []; primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: {0} ==> {1}'.format(k, v))
                mappings[k] = v
                if v.primary_key:
                    if primaryKey: raise StandardError('Duplicate primary key for field: {0}'.format(k))
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey: raise StandardError('Primary key not found.')
        for k in mappings.keys(): attrs.pop(k)
        # 存储所有的字段和主键
        escaped_fields = list(map(lambda f : '`{0}`'.format(f), fields))
        attrs['__table__'] = tableName
        attrs['__mappings__'] = mappings
        attrs['__primary_key__'] = primaryKey
        attrs['__fields__'] = fields
        # 构造SQL语句
        attrs['__select__'] = 'select `{0}`, {1} from `{2}`'.format(primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `{0}` ({1}, `{2}`) values ({3})'.format(tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `{0}` set {1} where `{2}`=?'.format(tableName, ', '.join(map(lambda f : '`{0}`=?'.format(mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `{0}` where `{1}`=?'.format(tableName, primaryKey)
        # 返回类
        return type.__new__(cls, name, bases, attrs)

class Model(dict, metaclass = ModelMetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try: return self[key]
        except KeyError:
            raise AttributeError("'Model' object has no attribute '{0}'".format(key))

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for {0}: {1}'.format(key, str(value)))
                setattr(self, key, value)
        return value

    @classmethod
    async def findAll(cls, where = None, args = None, **kw):
        'find objects by where clause.'
        sql = [cls.__select__]
        if where:
            sql.append('where'); sql.append(where)
        if args is None: args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by'); sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?'); args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?'); args.extend(limit)
            else:
                raise ValueError('Invalid limit value: {0}'.format(str(limit)))
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where = None, args = None):
        'find number by select and where.'
        sql = ['select {0} _num_ from `{1}`'.format(selectField, cls.__table__)]
        if where:
            sql.append('where'); sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0: return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        'find object by primary key.'
        rs = await select('{0} where `{1}`=?'.format(cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0: return None
        return cls(**rs[0])

    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1: logging.warn('failed to insert record: affected rows: {0}'.format(rows))

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1: logging.warn('failed to update by primary key: affected rows: {0}'.format(rows))

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1: logging.warn('failed to remove by primary key: affected rows: {0}'.format(rows))
