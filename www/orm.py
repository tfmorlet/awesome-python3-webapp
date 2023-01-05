# -*- encoding: utf-8 -*-
'''
@File    :   orm.py
@Time    :   2023/01/03 17:40:59
@Author  :   Weibin Yang 
@Contact :   weibiny@outlook.com
'''

# here put the import lib
# 用于web 访问数据库，处理数据
# 创建函数，用于执行Select insert update delete 操作

import time
import json
import os
from aiohttp import web
from datetime import datetime
import aiomysql
import asyncio
import logging
logging.basicConfig(level=logging.INFO)


# @asyncio.coroutine 这个装饰器的作用是让这个函数的操作变成协程
# 创建连接池
# create_pool函数最基本的功能就是创建一个和Mysql数据库的连接
# 函数传入一个参数loop，loop为通过asyncio创建的连接事件


@asyncio.coroutine
async def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    # 把__pool设置为全局变量，再将其定义为一个和数据库的连接
    global __pool
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        # db参数为要连接使用的数据库database
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        # 设置最小和最大的连接数
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )

# 定义一个函数，能够帮助我们执行SELECT操作，用于在数据库中选择数据
# select函数传入sql语句


@asyncio.coroutine
async def select(sql, args, size=None):
    # log是做记录
    logging.info(sql, args)
    # 全局变量
    global __pool
    # 从连接池中返回一个连接
    with (await __pool) as conn:
        # cursor 获取角标
        # aiomysql.DictCursor是将返回的角标作为字典形式返回
        cur = await conn.cursor(aiomysql.DictCursor)
        # cursor的execute方法，执行SQL语句
        # 之所以要用replace，是因为sql和mysql的占位符不同，我们连接的是
        # mysql，但是输入的语句是sql，sql用的是？ mysql用的是%s
        # %s表示向语句中传递args参数
        await cur.execute(sql.replace('?', '%s'), args or ())
        # 是否调用函数时有输入size参数
        if size:
            # 如果有，那么调用fetchmany方法获取mysql返回的数据
            # 返回的数据数量，根据size参数决定
            rs = await cur.fetchmany(size)
        else:
            # 如果没有size参数，则返回所有数据，并且是以字典的形式
            rs = await cur.fetchall()
        # 关闭角标
        await cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs

# 再定义函数完成 Insert, Updata, Delete操作
# 因为这三个操作在Mysql语句下传入的参数相同，返回的内容也类似，因此
# 可以用一个函数实现


@asyncio.coroutine
async def execute(sql, args):
    logging.info(sql)
    global __pool
    # 从连接池中继续
    with (await __pool) as conn:
        try:
            # 提取角标，因为返回的内容不是数据，所以不用返回字典
            cur = await conn.cursor()
            # 执行sql语句
            await cur.execute(sql.replace('?', '%s'), args)
            # rowcount属性是sql语句返回的行数，即受影响的行数
            affected = cur.rowcount
            await cur.close()
        except BaseException as e:
            raise
        return affected

# 有了基本函数了，开始编写ORM
# ORM （object/Relational Mapping）
# 所实现的是 对象-关系映射，即数据库中的一行=一个对象，一个类对应一个表
# 我们预期 使用ORM的方式如下：
# class User(Model):
# # __开头为访问限制变量
# # 不通过__init__初始化的方式设置table，是因为这个默认，以此类创建的实例都
# # 是这个属性，不需要传入参数
#     __table__ = 'users'
#     id = IntegerField(primary_key=True)
#     name = StringField()
# 通过这种方式，能够将类User和users这个表相联系，之后所建立的所有User类实例，就相当于
# 在user这个表中新建了一行


# 先定义 数据类型（这部分可以先不看，先看后面对元类的定义）
# 定义Field类和子类如StringField IntegerField
# mysql中数据类型包括几个大类
# 1. 设置类型 IntegerField
# 2. 日期与时间 TimeField
# 3. 字符串类型 StringField FloatField
# 4. 布尔值 BooleanField

class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        # 列名
        self.name = name
        # 列的属性
        self.column_type = column_type
        # 是否为主键
        self.primary_key = primary_key
        # 该列的默认值是什么
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'real', primary_key,default)

class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

# 要实现上述的调用形式
# 首先，先定义元类，类似于类的类
# 这个create函数，主要用于元类中insert操作的默认值。默认为？

def create_args_string(num):
    L = []
    for _ in range(num):
        # 源码是 for n in range(num):  我看着反正 n 也不会用上，改成这个就不报错了
        L.append('?')
    return ', '.join(L)

class ModelMetaclass(type):
    # __new__()方法接收到的参数依次是：
    # cls：当前准备创建的类的对象 class
    # name：类的名字 str
    # bases：类继承的父类集合 Tuple
    # attrs：类的方法集合

    def __new__(cls, name, bases, attrs):
        # 排除Model类本身:
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # 获取table名称:
        # 在建立一个表的类时，需要输入__table__ = 'xx'属性
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        # 获取所有的Field和主键名:
        # 主键：为数据中的某一列，必须满足任意两行不相同，且每行都有这一列。
        mappings = dict()
        # fields包括除主键外所有的列的列名
        fields = []
        # 将primaryKey默认设置为None，如果有某一列映射设置了其属性为True，那么这一列
        # 就是主键列
        primaryKey = None
        # 这个items 应该是所有的列，现在要将列和数据库形成映射
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                # 表明 k列 的属性是v v可能是 str  int 等等
                mappings[k] = v
                if v.primary_key:
                    # 如果主键是True，先判断是否已经有主键，如果有，报错
                    # 因为主键不允许重复
                    if primaryKey:
                        raise RuntimeError(
                            'Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    # 非主键列，增加到field列表
                    fields.append(k)
        # 映射完后，如果还没有设置主键，报错
        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        # 添加完映射后，从attrs这个字典中删除已经添加的。后续会构建新的内容
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings  # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey  # 主键属性名
        attrs['__fields__'] = fields  # 除主键外的属性名
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (
            primaryKey, ', '.join(escaped_fields), tableName)
        # mysql的插入语句 INSERT INTO 表名(列名) VALUES(每一列的值都必须提供，NULL也需要)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(
            escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(
            map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (
            tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)

# 定义所有映射的基类 model:
# 之后新建立的数据都是以这个类为基础建立
# 实际上就是一个字典，只是在字典的基础上，多了两个功能
class Model(dict, metaclass=ModelMetaclass):

    def __init__(self, **kw):
        # super函数用于继承字典的所有方法
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        # 实现user['id']返回该行该列的值
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        # 实现user.id = xx 设置该行（user）该列（id）的值
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' %
                              (key, str(value)))
                setattr(self, key, value)
        return value

    # classmethod的作用在于，可以直接通过类调用find这个方法
    # 见https://blog.csdn.net/handsomekang/article/details/9615239
    # 实现 User.find('xx')
    @classmethod
    async def find(cls, pk):
        ' find object by primary key. '
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])
    # 实现FindAll方法，用于查询
    # 使用方法为User.findAll()
    # 相当于在整个表中进行查询
    # 前面的save update remove等都是在某一行中进行操作，所以是实例方法
    # 除了where和args，还可以输入limit，orderBy
    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        # mysql中根据WHERE条件进行查询的语句是
        # SELECT field1 FROM tablename WHERE condition1
        # 实际上只是在基础的select语句的后面，加上了WHERE condition
        sql = [cls.__select__]
        # 首先判断是否输入了where参数
        if where:
            # 先添加where关键字
            sql.append('where')
            # 在添加具体的条件
            sql.append(where)
        if args is None:
            # args参数的作用是什么还不清楚
            args = []
        # sql 语句可以传入order by ... 来指示返回的数据根据什么排列
        # 先判断调用findAll方法时是否有传入这个参数
        # kw.get方法 用于提取**kw参数
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        # sql 可以传入limit参数，限制返回的数据行数
        # 如果是limit N 则返回N条数据
        # 如果是limit N, M 则从N开始，返回M条数据
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            # 首先判断limit是N 还是N，M
            if isinstance(limit, int):
                # 如果 limit 为整数
                # ? 会被转换为%s 然后被args中的参数填充替换
                sql.append('?')
                args.append(limit)
            # 如果是元祖，且有两个字符，那就是N，M
            elif isinstance(limit, tuple) and len(limit) == 2:
                # 如果 limit 是元组且里面只有两个元素
                sql.append('?, ?')
                # extend 把 limit 加到末尾
                args.extend(limit)
            else:
                # 不行就报错
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args)
        print('rs is %s' % [cls(**r) for r in rs])
        return [cls(**r) for r in rs]

    # 再实现findNumber方法。这个方法的目的是实现SQL语句 select count(*)
    # 该语句返回指定列的值的数目，例如查看id这一列，有多少行，则返回多少
    # select count(id) from database
    # 同样该语句可以在后续加上where限制条件
    # 加上where则表示查询，该列中符合该数值情况的烈数有多少
    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ## find number by select and where
        #找到选中的数及其位置
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, size=1)
        if len(rs) == 0:
            # 如果 rs 内无元素，返回 None ；有元素就返回某个数
            return None
        return rs[0]['_num_']

    # 再添加save方法。这样以此生成的每个实例，或者说每一行都可以执行save保存
    # 即执行 yield from user.save() user 是User类的一个实例
    async def save(self):
        # 提取这一行的不同列的值
        args = list(map(self.getValueOrDefault, self.__fields__))
        # 提取这一行 主键列的值
        args.append(self.getValueOrDefault(self.__primary_key__))
        # 执行execute函数中的insert方法
        rows = await execute(self.__insert__, args)
        # 一般情况都是添加新的一行。返回行数1
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warning(
                'failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warning(
                'failed to remove by primary key: affected rows: %s' % rows)
