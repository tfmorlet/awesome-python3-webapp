# -*- encoding: utf-8 -*-
'''
@File    :   handlers.py
@Time    :   2023/01/05 11:14:02
@Author  :   Weibin Yang 
@Contact :   weibiny@outlook.com
'''

# here put the import lib

from coroweb import get

from model import User

@get('/')
async def index(request):
    users = await User.findAll()
    print(users)
    return {
        '__template__': 'test.html',
        'users': users
    }