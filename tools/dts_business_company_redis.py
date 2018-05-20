import pymysql
import concurrent.futures
pymysql.install_as_MySQLdb()
import markdown
import os.path
import re
import subprocess
import torndb
import json
import requests as req
import math,random
from bs4 import BeautifulSoup
import lxml
import redis,csv
import hashlib
import queue,threading
from tornado.options import define,options

from requests.adapters import HTTPAdapter

requests = req.Session()
requests.mount('http://', HTTPAdapter(max_retries=10))
requests.mount('https://', HTTPAdapter(max_retries=10))

define("mysql_host", default="127.0.0.1:4407", help="blog database host")
define("mysql_database", default="bigdata", help="blog database name")
define("mysql_user", default="root", help="blog database user")
define("mysql_password", default="kingdom88", help="blog database password")
class dts_stock():
    def __init__(self):
        self.db = torndb.Connection(
            host=options.mysql_host, database=options.mysql_database,
            user=options.mysql_user, password=options.mysql_password)
        self.rds7=redis.Redis(host="127.0.0.1",port=7000,db=7,password='kingdom88')
        self.rds8=redis.Redis(host="127.0.0.1",port=7000,db=8,password='kingdom88')

        self.headers = [
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36",'Proxy-Switch-Ip':'yes'},
            {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1180.71 Safari/537.1 LBBROWSER",'Proxy-Switch-Ip':'yes'},
            {"User-Agent": "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.84 Safari/535.11 SE 2.X MetaSr 1.0",'Proxy-Switch-Ip':'yes'},
            {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.122 UBrowser/4.0.3214.0 Safari/537.36",'Proxy-Switch-Ip':'yes'}
        ]
    def get_proxy_url(self,proxies):
        return requests.get("http://proxy.abuyun.com/current-ip",proxies=proxies).content
    def getjson_get(self,url,headers,timeout,par_md5=None):
        try:
            retry_count = 2
            i = 10
            # 代理服务器
            proxyHost = "http-cla.abuyun.com"
            proxyPort = "9030"

            # 代理隧道验证信息
            proxyUser = "HNN53770XH78Q74C"
            proxyPass = "0F542E65681C6DA3"

            proxyMeta = "http://%(user)s:%(pass)s@%(host)s:%(port)s" % {
                "host": proxyHost,
                "port": proxyPort,
                "user": proxyUser,
                "pass": proxyPass,
            }

            proxies = {
                "http": proxyMeta,
                "https": proxyMeta,
            }
            while retry_count > 0:
                try:
                    print('开始发起请求:',url)
                    response = requests.get(url, headers=headers,timeout=25)
                    # 使用代理访问
                    if response.status_code==200:
                        try:
                            print(len(response.json()))
                            a=self.rds7.set(par_md5, value=response.text)
                            print('存储数据执行成功', a, '索引值为：', par_md5)
                            retry_count=0
                        except Exception as e:
                            a = self.rds8.set(par_md5, value='')
                            print ('返回数据异常',e,'结果为：',len(response.json()))

                except Exception as e:
                    retry_count -= 1
                    print ('获取出错retry_count值为：',retry_count,'错误为：',e)
                    while retry_count>0:
                        retry_count-=1
                        a = self.rds8.set(par_md5, value='')
                        print("正在写入错误信息",a)
        except Exception as e:
            print('发起请求出错，需重试',e)
            retry_count -= 1
            a = self.rds8.set(par_md5, value='')
            print("正在写入异常错误信息", a)
    def execsql(self,vtype):
        print(vtype)
        try:
            entries =self.db.query("SELECT * from entries;")
            print(entries)
        except pymysql.ProgrammingError:
            print('error')

    def dict2list(self,dic:dict):
        ''' 将字典转化为列表 '''
        keys = dic.keys()
        vals = dic.values()
        lst = [(key, val) for key, val in zip(keys, vals)]
        return lst
    def request_company(self):
        csv_reader = csv.reader(open('business_list.csv',mode='r',encoding='utf-8'))  # 读取
        for i in csv_reader:
            bank_queue.put(i[0])
        return csv_reader
    def get_company(self):
        while True:
            company_name=bank_queue.get()
            print('开始采集公司名称:',company_name,'还有',str(bank_queue.queue.__len__()),'/',bank_queue.unfinished_tasks,'未完成')
            url='http://106.75.147.135:8800/key/%(name)s'%{"name":company_name}
            #print(url)
            header_i = random.randint(0, len(self.headers) - 1)
            par_md5=hashlib.md5(str(company_name).encode(encoding='UTF-8')).hexdigest()
            par_md5_erro='error:' + par_md5
            if self.rds7.exists(par_md5) == True:
                continue
            if self.rds8.exists(par_md5) == True:
                continue
            response=self.getjson_get(url=url,headers=self.headers[header_i],timeout=5,par_md5=par_md5)
            if response!=None:
                res = response
                print('数据节点共',len(res))
            else:
                print(response)
        bank_queue.task_done()

if __name__ == "__main__":
    a = dts_stock()
    dts_type='company'
    #读取公司所有信息
    if dts_type=='company':
        bank_queue=queue.Queue()
        a.request_company()
        thread_list = []
        for n in range(2):
            producer_thread = threading.Thread(target=a.get_company)  # 多线程
            thread_list.append(producer_thread)
        for t in thread_list:
            t.setDaemon(True)
            t.start()

        for t in thread_list:
            t.join()

