#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Li Ruhua'

import os, asyncio, logging, functools, inspect
from urllib import parse
from aiohttp import web
from apis import APIError

logging.basicConfig(level = logging.INFO)

######## 将函数映射为URL处理函数 ########
def method_decorate(path, *, method):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = method
        wrapper.__route__ = path
        return wrapper
    return decorator

get = functools.partial(method_decorate, method = 'GET')
post = functools.partial(method_decorate, method = 'POST')

######## URL处理函数参数扫描 ########
def get_required_kw_args(fn): # 获取函数的无默认值的关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn): # 获取函数的命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn): #判断有没有命名关键字参数
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn): #判断有没有关键字参数
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn): #判断是否含有名叫'request'参数，且该参数是否为最后一个参数
    sig = inspect.signature(fn); params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.VAR_KEYWORD)):
            raise ValueError('request parameter must be the last named parameter in function: {0}{1}'.format(fn.__name__, str(sig)))
        return found

######## URL函数协程处理对象 ########
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
        kw = None
        # 取出查询参数或提交参数作为字典
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'GET':
                qs = request.query_string # 查询字符串
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
            elif request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded', 'multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: {0}'.format(request.content_type))
        # 处理字典
        if kw is None:
            kw = dict(**request.match_info)
        else:
            # 清理未命名的关键字参数
            if (not self._has_var_kw_arg) and self._named_kw_args:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw: copy[name] = kw[name]
                kw = copy
            # 检查命名参数
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: {0}'.format(k))
                kw[k] = v
        # 处理'request'参数
        if self._has_request_arg: kw['request'] = request
        # 检查函数的参数要求与request对象的参数是否匹配
        if self._required_kw_args:
            for name in self._required_kw_args:
                if name not in kw:
                    return web.HTTPBadRequest('Missing argument: {0}'.format(name))
        # 执行URL处理函数
        logging.info('call with args: {0}'.format(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error = e.error, data = e.data, message = e.message)

######## URL函数自动扫描和注册 ########
def add_static(app): # 静态路由注册
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static {0} => {1}'.format('/static/', path))

def add_route(app, fn): # 单个URL函数注册
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if method is None or path is None:
        raise ValueError('@get or @post not defined in {0}.'.format(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route {0} {1} => {2}({3})'.format(method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))

def add_routes(app, module_name): # 自动按模块扫描注册
    n = module_name.rfind('.')
    if n == -1:
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'): continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path: add_route(app, fn)
