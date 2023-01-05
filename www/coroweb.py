# -*- encoding: utf-8 -*-
'''
@File    :   handlers.py
@Time    :   2023/01/04 15:53:50
@Author  :   Weibin Yang 
@Contact :   weibiny@outlook.com
'''

# here put the import lib
from aiohttp import web
import logging, functools, os, inspect, asyncio
from urllib import parse
from apis import APIError
logging.basicConfig(level=logging.INFO)

# 编写一个web框架
# 先写两个装饰器 便于接受url


def get(path):
    '''
    定义一个装饰器
    使用方法 @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator


def post(path):
    '''
    定义一个装饰器
    使用方法 @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator


def get_required_kw_args(fn):
    args = []
    # inspect.signature的作用是接受一个函数，
    # 获取 def foo(a,*,**kwargs)中的 (a,*,**kwargs)
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # default 表示该参数的默认值，如果是empty 表示没有设置默认值
        # kind 表示可能的取值
        # POSITIONAL_OR_KEYWORD 既可以以关键字参数的形式提供，也可以以位置参数的形式提供
        # KEYWORD_ONLY 必须以关键字实参的形式提供 例如 name='ss'
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            # 在 args 里加上仅包含关键字（keyword）的参数， 且不包括默认值， 然后返回 args
            args.append(name)
    return tuple(args)


def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    # 下划线表示，这个参数不会使用
    # KEYWORD_ONLY 表示存在关键字参数 即不考虑位置，只需要名字写对 例如name='xx',
    # name 写在第一个参数也可以，写在最后一个参数也可以
    for _, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True


def has_var_kw_arg(fn):
    # VAR_KEYWORD 表示有 **kwargs
    # kwargs = keyword Variable Arguments 即表示传入字典形式的参数
    # 如果是 *args 则表示传入列表或者元组
    params = inspect.signature(fn).parameters
    for _, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True


def has_request_arg(fn):
    # 判断函数是否有request这个参数，并且参数是否合法
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (
                fn.__name__, str(sig)))
    return found

# 定义处理URL的函数的类
# handler是aiohttp中的一种必要函数，主要作用就是
# 接受request 解析 返回特定的response
# 这里之所以要先定义一个类，而不是写具体的handler函数，是因为大部分的handler函数类似
# 所以我们可以先定义类，再创建handler实例，在进行注册 add_routes()
# 通过app.router.resources()可以查看所有已经注册的方法。


class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    async def __call__(self, request):
        # 用于当 print(函数)时，要输出的东西
        kw = None
        # self._has_var_kw_arg = True 说明有**kwargs这个参数
        # _has_named_kw_args = True 说明 有关键字参数 例如 type='xx'
        # _required_kw_args = True 说明 有request参数
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            # request 主要见https://docs.aiohttp.org/en/stable/web_reference.html
            if request.method == 'POST':
                # 判断是否header中带有content-type
                # content-type主要是告诉服务器，接下来reqeust的内容格式是什么
                # https://juejin.cn/post/6868277123824975886
                # https://blog.csdn.net/woaixiaoyu520/article/details/76690686
                # application/json 对应用request.json()方法
                # application/x-www-form-urlencoded 对应用request.post()方法，因为这种格式一般是提交信息
                # multipart/form-data 同样是提交信息，对应用request.post()方法，但是处理方式不同。
                if not request.content_type:
                    return web.HTTPBadRequest(reason='Missing Content-Type.')
                # 将contengt-type转换为小写，同时将其转换为字符串
                ct = request.content_type.lower()
                # startswith 是针对字符串string的一个方法，判断是否以xx为开头
                if ct.startswith('application/json'):
                    # 如果是json开头，则提取json格式的request结果
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(reason='JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(reason='Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                # query_string返回url中的查询字符串
                qs = request.query_string
                if qs:
                    kw = dict()
                    # parse.parse_qs是urllib库中的一个方法，用于将url字符串分割
                    # urllib.parse.parse_qs() 能够将url的查询参数进行解析，解析后返回一个字典
                    # 例如 http://docs.python.org:80/3/library/urllib.parse.html?highlight=params#url-parsing
                    # 这个url里面的highlight=就是查询的内容，前面是连接路径
                    # parse_qs就是查询这个highlight=xx的内容，并返回字典
                    # 字典的key 是前面链接部分http://docs.python.org:80/3/library/urllib.parse.html?highlight
                    # 字典的value 是等于号后面部分['params#url-parsing']
                    # 提取具体内容用value[0] >>> params#url-parsing
                    # 因为是字典，所以提取是采用.items()方法
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            # match_info方法是提取url中的参数
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning(
                        'Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest(reason='Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))


def add_route(app, fn):
    # app参数接受自aiohttp app = web.Application()
    # fn是具体的handler实例
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    # 判断是否提取到了url的方法和路径
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    # 判断该url处理函数 是否为一个协程，inspect模块主要用于检查是否为生成器
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (
        method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # add_route方法，当接收到 meth path 这类输入后，采用RequestHandeler函数进行处理
    # 例如 app.router.add_route('GET', '/hello/{name}', hello)
    # 指示，用hello函数，处理get方法请求/hellp/name路径的输入
    app.router.add_route(method, path, RequestHandler(app, fn))
# 需要注册的函数可能有很多，所以写一个routes的函数，自动扫描后进行注册
# 使用方式是 add_routes(app, '模块名称')


def add_routes(app, module_name):
    # rfind方法，返回字符串最后一次出现的位置
    # str = "this is really a string example....wow!!!";
    # substr = "is";
    # print str.rfind(substr);
    # >>> 5
    # module_name 指模块的名字，例如 import xx 这里的xx就是一个模块
    n = module_name.rfind('.')

    # 如果n等于-1，则说明module_name中没有.
    if n == (-1):
        # import 这个模块
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(
            module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        # 如果模块中的函数，有以下划线开头的，忽略 continue表示跳过这个for循环
        if attr.startswith('_'):
            continue
        # 得到这个函数的属性 <function index at 0x0000015D82EE7158>
        fn = getattr(mod, attr)
        print('注册函数: %s' % fn)
        if callable(fn):
            print('函数%s is callable' % fn)
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)

    # 判断这个函数是否合法，即参数内是否有request
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (
                fn.__name__, str(sig)))
    return
