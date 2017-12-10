#!/usr/bin/env python
import os.path
import re
import pymysql
pymysql.install_as_MySQLdb()
import torndb
import tornado.escape
from tornado import gen
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web

class restapi():
    def __init__(self,**kwargs):
        print(self)
    @property
    def db(self):
        return self.application.db

    def dbexc(api_name,api_params):
        results=restapi.db.get('SELECT  a.registerProvince,  COUNT(a.registerProvince) as vcount, a.officeProvince FROM bigdata.pf_base a WHERE a.registerProvince <> a.officeProvince and a.registerProvince<>'' GROUP BY a.registerProvince , a.officeProvince ')
        return results



