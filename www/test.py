# -*- encoding: utf-8 -*-
'''
@File    :   test.py
@Time    :   2023/01/04 15:21:35
@Author  :   Weibin Yang 
@Contact :   weibiny@outlook.com
'''

# here put the import lib
# 测试使用ORM连接数据库能否成功
# 通过在mysql中，登陆webapp，使用awesome数据库
# 查询语句 SELECT * FROM users;
import asyncio
import orm
from model import User, Blog, Comment


async def test(loop):
    await orm.create_pool(loop=loop,
                          user='webapp', password='0506', db='awesome')

    u = User(name='Test', email='test@example.com',
             passwd='123456', image='about:blank')
    
    await u.save()
    orm.__pool.close()
    await orm.__pool.wait_closed()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop))
    loop.close()
