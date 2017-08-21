#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Li Ruhua'

from coroweb import *

@get('/')
async def index(request):
    body = '<h1>Awesome, Liruhua !</h1>'
    return body

@get('/greeting/{name}')
async def greeting(*, name, request):
    body = '<h1>Awesome: greeting {0} !</h1>'.format(name)
    return body
