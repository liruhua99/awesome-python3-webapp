#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Li Ruhua'

from coroweb import *
from models import *

@get('/')
async def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id = '1', name = 'Test Blog', summary = summary, created_at = time.time()-120),
        Blog(id = '2', name = 'Something New', summary = summary, created_at = time.time()-3600),
        Blog(id = '3', name = 'Learn Swift', summary = summary, created_at = time.time()-7200)
    ]
    return {
        '__template__' : 'blogs.html',
        'blogs' : blogs
    }

@get('/greeting/{name}')
async def greeting(*, name, request):
    body = '<h1>Awesome: greeting {0} !</h1>'.format(name)
    return body

@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy = 'created_at desc')
    for u in users: u.passwd = '******'
    return dict(users = users)
