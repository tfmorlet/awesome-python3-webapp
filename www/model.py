# -*- encoding: utf-8 -*-
'''
@File    :   model.py
@Time    :   2023/01/03 17:40:38
@Author  :   Weibin Yang 
@Contact :   weibiny@outlook.com
'''
import time, uuid

from orm import Model, StringField, BooleanField, FloatField, TextField

def next_id():
    # 这个函数主要是用于当没有输入id时，默认生成以当前时间为基础的一个id
    # uuid模块，主要用来生成一个唯一的id 标识某一个对象
    # https://docs.python.org/3/library/uuid.html
    # uuid.uuid4()基于随机数来生成一个id
    # hex属性是指返回的id为“32个字符的小写十六进制字符串形式”
    # %015d 表示接受一个数字，但这个数字前面会先增加15个0
    # time.time()方法返回当前时间，以秒为单位
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

# 构造我们后续webapp需要用到的三个table
class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)

class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)

class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)
