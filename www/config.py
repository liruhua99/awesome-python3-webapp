#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Li Ruhua'

import config_default

def merge(defaults, override):
    result = dict()
    for k, v in defaults.items():
        if k in override:
            if isinstance(v, dict): result[k] = merge(v, override[k])
            else: result[k] = override[k]
        else: result[k] = v
    return result

configs = config_default.configs

try: # 不一定配置了config_override.py文件
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError: pass
