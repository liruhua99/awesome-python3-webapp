#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Li Ruhua'

class APIError(Exception):
    def __init__(self, error, data = '', message = ''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message

class APIValueError(APIError):
    def __init__(self, field, message = ''):
        super(APIValueError, self).__init__('Value : Invalid', field, message)

class APIResourceNotFoundError(APIError):
    def __init__(self, field, message = ''):
        super(APIResourceNotFoundError, self).__init__('Value : Not Found', field, message)

class APIPermissionError(APIError):
    def __init__(self, message = ''):
        super(APIPermissionError, self).__init__('Permission : Forbidden', 'Permission', message)
