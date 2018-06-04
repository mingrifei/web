'''
通过队列的方式获取内存数据库1中采集的数据进行更新到关系型数据库中；
基本信息由dts_company_v0.1_redis.py和dts_bank_company_v0.1_redis.py采集到内存数据库的信息
by mingrifei
'''
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
import lxml,time
import redis
import hashlib
import threading,queue
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
        self.rds=redis.Redis(host="127.0.0.1",port=7000,password='kingdom88')
        self.rds_db7=redis.Redis(host="127.0.0.1",port=7000,db=7,password='kingdom88')
        self.rds_db_9=redis.Redis(host="127.0.0.1",port=7000,db=9,password='kingdom88')
        self.headers = [
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36",'Proxy-Switch-Ip':'yes'},
            {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1180.71 Safari/537.1 LBBROWSER",'Proxy-Switch-Ip':'yes'},
            {"User-Agent": "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.84 Safari/535.11 SE 2.X MetaSr 1.0",'Proxy-Switch-Ip':'yes'},
            {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.122 UBrowser/4.0.3214.0 Safari/537.36",'Proxy-Switch-Ip':'yes'}
        ]
    def get_proxy_url(self,proxies):
        return requests.get("http://proxy.abuyun.com/current-ip",proxies=proxies).content
    def getjson_post(self,url,data,headers,timeout,par_md5=None):
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
                    print('发起请求参数:',data)
                    print('使用的代理为:',proxies)
                    print('使用的真实代理为:',str(self.get_proxy_url(proxies=proxies)))
                    response = requests.post(url, data=data,headers=headers,timeout=3,proxies=proxies)
                    #response = requests.post(url, data=data,headers=headers,timeout=timeout,)
                    # 使用代理访问
                    if response.status_code==200:

                        a=self.rds_db_4.set(par_md5, value=data)
                        print ('存储数据执行成功',a,'索引值为：',par_md5)
                        if '访问过于频繁' in response.text:
                            print('访问受禁止',response.text)
                            self.getjson_post(url, data, headers, timeout)
                        return response.json()
                    else:
                        return None
                except Exception as e:

                    print ('获取出错retry_count值为：',retry_count,'错误为：',e)
                    while i>0:
                        i=i-1
                        self.getjson_post(url, data, headers, timeout)
        except Exception as e:
            print('发起请求出错，需重试',e)
            self.getjson_post(url, data, headers, timeout)
    def execsql(self,vtype):
        print(vtype)
        try:
            entries =mysqldb.query("SELECT * from entries;")
            print(entries)
        except pymysql.ProgrammingError:
            print('error')

    def dict2list(self,dic:dict):
        ''' 将字典转化为列表 '''
        keys = dic.keys()
        vals = dic.values()
        lst = [(key, val) for key, val in zip(keys, vals)]
        return lst

    def text_create(self,name, msg):
        try:
            desktop_path = './log/'
            full_path = desktop_path + name + '.json'
            file = open(full_path, 'a')
            file.write(msg)
            file.close()
        except Exception as e:
            print(e)
    def get_company_data(self):
        '''
        rs=mysqldb.query('SELECT t.business_id FROM bigdata.business_base_dts t')
        for i in rs:
            if self.rds_db_9.exists(i['business_id']) != 1:
                self.rds_db_9.set(i['business_id'], value='ok')
        print('初始化完成数据集成功')
        '''
        company_keys=self.rds_db7.keys()
        for company_key in company_keys:
            company_idx=company_key
            if self.rds_db_9.exists(company_key) != True:
                company_data_queue.put(company_idx)
            else:
                print('上批次已采集入库完成',company_key)

    def get_company_detail(self):
        while True:
            mysqldb = torndb.Connection(host=options.mysql_host, database=options.mysql_database,user=options.mysql_user, password=options.mysql_password)
            company_idx = company_data_queue.get().decode()
            print(self.rds_db_9.exists(company_idx),'||||||||',company_idx)
            if self.rds_db_9.exists(company_idx) != True:
                try:
                    '''
                    #with open("../../company_result/"+company_idx.decode()+".json", 'r') as load_f:
                    #    company_result = json.load(load_f)
                    #    print(company_result)
                    '''
                    company_result=self.rds_db7.get(company_idx).decode()
                    vcompany_result=json.loads(company_result)
                    #print(len(vcompany_result))
                    if len(vcompany_result.get('business_base',''))>0 and len(vcompany_result)==44:
                        #self.text_create(company_idx.decode(), company_result)
                        business_name = ''
                        business_id=''
                        business_base_l = vcompany_result['business_base']
                        #读取公司名称和生成公司ID
                        if business_base_l.get('business_name') is not None:
                            business_name = business_base_l['business_name']
                            business_id=hashlib.md5(business_name.encode(encoding='UTF-8')).hexdigest()
                        if dts_type=='business_base' or dts_type=='business_all':
                            business_legal_id = ''
                            business_cycle_time = ''
                            busines_tags = ''
                            business_score = ''
                            business_reg_Institute = ''
                            business_reg_state = ''
                            business_industry = ''
                            business_en_name = ''
                            business_reg_number = ''
                            business_organization_number = ''
                            business_search = ''
                            business_payment_number = ''
                            business_url = ''
                            business_reg_capital = ''
                            business_tyc_id = ''
                            business_addres = ''
                            business_reg_addres = ''
                            business_email = ''
                            business_update_time = ''
                            business_approved_time = ''
                            business_phone = ''
                            business_unite_number = ''
                            business_summary = ''
                            business_scope = ''
                            business_reg_time = ''
                            business_type = ''
                            business_logo=''
                            business_legal_name=''
                            business_plate=''
                            if business_base_l.get('business_legal_id') is not None:
                                business_legal_id = business_base_l['business_legal_id']
                            if business_base_l.get('business_cycle_time') is not None:
                                business_cycle_time = business_base_l['business_cycle_time']
                            if business_base_l.get('busines_tags') is not None:
                                busines_tags = business_base_l['busines_tags']
                            if business_base_l.get('business_score') is not None:
                                business_score = business_base_l['business_score']
                            if business_base_l.get('business_reg_Institute') is not None:
                                business_reg_Institute = business_base_l['business_reg_Institute']
                            if business_base_l.get('business_reg_state') is not None:
                                business_reg_state = business_base_l['business_reg_state']
                            if business_base_l.get('business_industry') is not None:
                                business_industry = business_base_l['business_industry']
                            if business_base_l.get('business_en_name') is not None:
                                business_en_name = business_base_l['business_en_name']
                            if business_base_l.get('business_reg_number') is not None:
                                business_reg_number = business_base_l['business_reg_number']
                            if business_base_l.get('business_organization_number') is not None:
                                business_organization_number = business_base_l['business_organization_number']
                            if business_base_l.get('business_search') is not None:
                                business_search = business_base_l['business_search']
                            if business_base_l.get('business_payment_number') is not None:
                                business_payment_number = business_base_l['business_payment_number']
                            if business_base_l.get('business_url') is not None:
                                business_url = business_base_l['business_url']
                            if business_base_l.get('business_name') is not None:
                                business_name = business_base_l['business_name']
                            if business_base_l.get('business_reg_capital') is not None:
                                business_reg_capital = business_base_l['business_reg_capital']
                            if business_base_l.get('business_tyc_id') is not None:
                                business_tyc_id = business_base_l['business_tyc_id']
                            if business_base_l.get('business_addres') is not None:
                                business_addres = business_base_l['business_addres']
                            if business_base_l.get('business_reg_addres') is not None:
                                business_reg_addres = business_base_l['business_reg_addres']
                            if business_base_l.get('business_email') is not None:
                                business_email = business_base_l['business_email']
                            if business_base_l.get('business_update_time') is not None:
                                business_update_time = business_base_l['business_update_time']
                            if business_base_l.get('business_approved_time') is not None:
                                business_approved_time = business_base_l['business_approved_time']
                            if business_base_l.get('business_phone') is not None:
                                business_phone = business_base_l['business_phone']
                            if business_base_l.get('business_unite_number') is not None:
                                business_unite_number = business_base_l['business_unite_number']

                            if business_base_l.get('business_summary') is not None:
                                business_summary = business_base_l['business_summary']
                            if business_base_l.get('business_scope') is not None:
                                business_scope = business_base_l['business_scope']
                            if business_base_l.get('business_reg_time'):
                                business_reg_time = business_base_l['business_reg_time']
                            if business_base_l.get('business_type'):
                                business_type = business_base_l['business_type']
                            if business_base_l.get('business_legal_name'):
                                business_legal_name = business_base_l['business_legal_name']
                            '''
                            print(business_legal_id, business_cycle_time, busines_tags, business_score,
                                  business_reg_Institute, business_reg_state, business_industry, business_en_name,
                                  business_reg_number, business_organization_number, business_search,
                                  business_payment_number, business_url, business_name, business_reg_capital,
                                  business_tyc_id, business_addres, business_reg_addres, business_email,
                                  business_update_time, business_approved_time, business_phone, business_unite_number,
                                  business_id, business_summary, business_scope, business_reg_time, business_type)
                            '''

                            try:

                                dbrs=mysqldb.get('select count(*) vcount from `bigdata`.`business_base` where bigdata.business_base.business_name=%s',business_name)
                                if dbrs['vcount']<1:
                                    delsql='DELETE FROM `bigdata`.`business_base` WHERE business_name=%s'
                                    delexec=mysqldb.execute(delsql,business_name)
                                    sql ="INSERT INTO `bigdata`.`business_base`   (`business_id`,   `business_name`,   `business_logo`,   `business_phone`,   `business_email`,   `business_url`,   `business_addres`,   `busines_tags`,   `business_summary`,   `business_update_time`,   `business_legal_id`,   `business_legal_name`,   `business_reg_capital`,   `business_reg_time`,   `business_reg_state`,   `business_reg_number`,   `business_organization_number`,   `business_unite_number`,   `business_type`,   `business_payment_number`,   `business_industry`,   `business_cycle_time`,   `business_approved_time`,   `business_reg_Institute`,   `business_reg_addres`,   `business_en_name`,   `business_scope`,   `business_score`,   `business_plate`)   VALUES   (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                                    s=mysqldb.insert(sql,business_id, business_name, business_logo, business_phone, business_email, business_url, business_addres, busines_tags, business_summary, business_update_time, business_legal_id, business_legal_name, business_reg_capital, business_reg_time, business_reg_state, business_reg_number, business_organization_number, business_unite_number, business_type, business_payment_number, business_industry, business_cycle_time, business_approved_time, business_reg_Institute, business_reg_addres, business_en_name, business_scope, business_score, business_plate)
                                    print(s)
                                    a = self.rds_db_9.set(business_id, value='ok')
                                    print('写入结果business_base状态',delexec,s,a,str(company_data_queue.queue.__len__()),'/',company_data_queue.unfinished_tasks,'未完成')
                                else:
                                    a = mysqldb.update(
                                        ' UPDATE `bigdata`.`business_base`  SET  `business_logo` =  %s,  `business_phone` =  %s,  `business_email` =  %s,  `business_url` =  %s,  `business_addres` =  %s,  `busines_tags` =  %s,  `business_summary` =  %s,  `business_update_time` =  %s,  `business_legal_id` =  %s,  `business_legal_name` =  %s,  `business_reg_capital` =  %s,  `business_reg_time` =  %s,  `business_reg_state` =  %s,  `business_reg_number` =  %s,  `business_organization_number` =  %s,  `business_unite_number` =  %s,  `business_type` =  %s,  `business_payment_number` =  %s,  `business_industry` =  %s,  `business_cycle_time` =  %s,  `business_approved_time` =  %s,  `business_reg_Institute` =  %s,  `business_reg_addres` =  %s,  `business_en_name` =  %s,  `business_scope` =  %s,  `business_score` =  %s,  `business_plate` =  %s  WHERE business_name=%s',
                                        business_logo, business_phone, business_email, business_url,
                                        business_addres, busines_tags, business_summary,
                                        business_update_time, business_legal_id, business_legal_name,
                                        business_reg_capital, business_reg_time, business_reg_state,
                                        business_reg_number, business_organization_number,
                                        business_unite_number, business_type, business_payment_number,
                                        business_industry, business_cycle_time, business_approved_time,
                                        business_reg_Institute, business_reg_addres, business_en_name,
                                        business_scope, business_score, business_plate, business_name, business_id)
                                    a = self.rds_db_9.set(business_id, value='ok')
                                print('写入更新结果business_base状态', business_name, a,'还有',str(company_data_queue.queue.__len__()),'/',company_data_queue.unfinished_tasks,'未完成')

                            except Exception as e:
                                print('--------------',business_id,'------------出错拉', e)
                        if dts_type=='business_holder' or dts_type=='business_all':
                            business_base_l=vcompany_result['business_holder']
                            if len(business_base_l)>0:
                                for holder in business_base_l:
                                    men_id=''
                                    men_name=''
                                    men_type=''
                                    holder_percent=''
                                    holder_amomon=''
                                    if holder.get('men_id') is not None:
                                        men_id = holder.get('men_id')
                                    if holder.get('men_name') is not None:
                                        men_name = holder.get('men_name')
                                    if holder.get('men_type') is not None:
                                        men_type = holder.get('men_type')
                                    if holder.get('holder_percent') is not None:
                                        holder_percent = holder.get('holder_percent')
                                    if holder.get('holder_amomon') is not None:
                                        holder_amomon = holder.get('holder_amomon')
                                    dbrs = mysqldb.get('select count(*) vcount from `bigdata`.`business_holder` where bigdata.business_holder.business_id=%s and bigdata.business_holder.men_name=%s',business_id,men_name)
                                    if dbrs['vcount'] < 1:
                                        a=mysqldb.insert('INSERT INTO `bigdata`.`business_holder` ( `business_id`, `men_id`, `men_name`,`men_type`, `holder_percent`, `holder_amomon`) VALUES (%s,%s,%s,%s,%s,%s)',
                                                     business_id,men_id,men_name,men_type,holder_percent,holder_amomon)

                                    print('写入结果business_holder状态', a)
                        if dts_type=='business_invest' or dts_type=='business_all' :
                            business_base_l=vcompany_result['business_invest']
                            if len(business_base_l)>0:
                                for i in business_base_l:
                                    invest_name = ''
                                    invest_id = ''
                                    legal_name = ''
                                    legal_id = ''
                                    legal_invest_count = ''
                                    invest_reg_capital = ''
                                    invest_amount = ''
                                    invest_amomon = ''
                                    invest_reg_time = ''
                                    invest_state = ''
                                    if i.get('invest_name') is not None:
                                        invest_name = i.get('invest_name')
                                    if i.get('invest_id') is not None:
                                        invest_id = i.get('invest_id')
                                    if i.get('legal_name') is not None:
                                        legal_name = i.get('legal_name')
                                    if i.get('legal_id') is not None:
                                        legal_id = i.get('legal_id')
                                    if i.get('legal_type') is not None:
                                        legal_type = i.get('legal_type')
                                    if i.get('invest_reg_capital') is not None:
                                        invest_reg_capital = i.get('invest_reg_capital')
                                    if i.get('invest_amount') is not None:
                                        invest_amount = i.get('invest_amount')
                                    if i.get('invest_amomon') is not None:
                                        invest_amomon = i.get('invest_amomon')
                                    if i.get('invest_reg_time') is not None:
                                        invest_reg_time = i.get('invest_reg_time')
                                    if i.get('invest_amomon') is not None:
                                        invest_state = i.get('invest_state')
                                    dbrs = mysqldb.get(
                                        'select count(*) vcount from `bigdata`.`business_invest` where bigdata.business_invest.business_id=%s and bigdata.business_invest.invest_name=%s',
                                        business_id, invest_name)
                                    if dbrs['vcount'] < 1:
                                        a=mysqldb.insert('INSERT INTO `bigdata`.`business_invest` (`business_id`, `invest_name`, `invest_id`, `legal_name`, `legal_id`,`legal_type`, `invest_reg_capital`, `invest_amount`, `invest_amomon`, `invest_reg_time`, `invest_state`) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                                                     business_id, invest_name, invest_id, legal_name, legal_id,legal_type,invest_reg_capital, invest_amount,invest_amomon, invest_reg_time, invest_state)
                                        print('business_invest状态insert', a)

                        if dts_type=='business_change' or dts_type=='business_all' :
                            business_base_l=vcompany_result['business_change']
                            if len(business_base_l)>0:
                                for i in business_base_l:
                                    change_time = ''
                                    change_name = ''
                                    change_before = ''
                                    change_after = ''
                                    if i.get('change_time') is not None:
                                        change_time = i.get('change_time')
                                    if i.get('change_name') is not None:
                                        change_name = i.get('change_name')
                                    if i.get('change_before') is not None:
                                        change_before = i.get('change_before')
                                    if i.get('change_after') is not None:
                                        change_after = i.get('change_after')
                                    dbrs = mysqldb.get(
                                        'select count(*) vcount from `bigdata`.`business_change` where bigdata.business_change.business_id=%s and bigdata.business_change.change_time=%s and bigdata.business_change.change_name=%s',
                                        business_id, change_time,change_name)
                                    if dbrs['vcount'] < 1:
                                        a=mysqldb.insert('INSERT INTO `bigdata`.`business_change` ( `business_id`, `change_time`, `change_name`, `change_before`, `change_after`) VALUES (%s,%s,%s,%s,%s)',
                                                     business_id, change_time, change_name, change_before, change_after)

                                    print('business_change状态', a)
                        if dts_type=='business_staff_men' or dts_type=='business_all':
                            business_base_l=vcompany_result['business_staff_men']
                            if len(business_base_l)>0:
                                for i in business_base_l:
                                    men_id = ''
                                    men_job = ''
                                    if i.get('men_id') is not None:
                                        men_id = i.get('men_id')
                                    if i.get('men_job') is not None:
                                        men_job = i.get('men_job')
                                    dbrs = mysqldb.get(
                                        'select count(*) vcount from `bigdata`.`business_staff_men` where bigdata.business_staff_men.business_id=%s and bigdata.business_staff_men.men_id=%s and bigdata.business_staff_men.men_job=%s',
                                        business_id, men_id, men_job)
                                    if dbrs['vcount'] < 1:
                                        a=mysqldb.insert('INSERT INTO `bigdata`.`business_staff_men` ( `business_id`, `men_id`, `men_job`) VALUES (%s,%s,%s)',
                                                     business_id, men_id, men_job)
                                        print('business_staff_men', a)
                        if dts_type=='business_men_base' or dts_type=='business_all':
                            business_base_l=vcompany_result['business_men_base']
                            if len(business_base_l)>0:
                                for i in business_base_l:
                                    men_id = ''
                                    men_name = ''
                                    men_photo = ''
                                    men_invest_count = ''
                                    if i.get('men_id') is not None:
                                        men_id = i.get('men_id')
                                    if i.get('men_name') is not None:
                                        men_name = i.get('men_name')
                                    if i.get('men_photo') is not None:
                                        men_photo = i.get('men_photo')
                                    if i.get('men_invest_count') is not None:
                                        men_invest_count = i.get('men_invest_count')
                                    dbrs = mysqldb.get(
                                        'select count(*) vcount from `bigdata`.`business_men_base` where  bigdata.business_men_base.men_id=%s and bigdata.business_men_base.men_name=%s',
                                        men_id, men_name)
                                    if dbrs['vcount'] < 1:
                                        a=mysqldb.insert('INSERT INTO `bigdata`.`business_men_base` ( `men_id`, `men_name`, `men_photo`, `men_invest_count`) VALUES (%s,%s,%s,%s)',
                                                     men_id, men_name, men_photo,men_invest_count)

                                        print('business_men_base', a)
                        if dts_type=='business_id_conv' or dts_type=='business_all':
                            business_base_l=vcompany_result['business_id_conv']
                            if len(business_base_l)>0:
                                for i in business_base_l:
                                    vbusiness_id = ''
                                    vbusiness_name = ''
                                    business_tyc_id = ''
                                    business_id_type = ''
                                    if i.get('business_id') is not None:
                                        vbusiness_id = i.get('business_id')
                                    if i.get('business_tyc_id') is not None:
                                        business_tyc_id = i.get('business_tyc_id')
                                    if i.get('business_name') is not None:
                                        vbusiness_name = i.get('business_name')
                                    if i.get('business_id_type') is not None:
                                        business_id_type = i.get('business_id_type')
                                    dbrs = mysqldb.get(
                                        'select count(*) vcount from `bigdata`.`business_id_conv` where  bigdata.business_id_conv.business_id=%s and bigdata.business_id_conv.business_tyc_id=%s',
                                        business_id, business_tyc_id)
                                    if dbrs['vcount'] < 1:
                                        a=mysqldb.insert('INSERT INTO `bigdata`.`business_id_conv` (`business_id`, `business_name`, `business_tyc_id`, `business_id_type`) VALUES (%s,%s,%s,%s)',
                                                        vbusiness_id, vbusiness_name, business_tyc_id,business_id_type)

                                        print('business_id_conv', a)

                    company_data_queue.task_done()
                except Exception as e:
                    #self.text_create('error/'+company_idx.decode()+'_error', str(e))
                    self.text_create('error/error', str(e))

                    #self.text_create('error/'+company_idx.decode(), company_result)
                    #print('入库失败',company_idx, e)

    def get_name(self):
        a = self.db.query("SELECT cer_num FROM bigdata.person_stock_info group by cer_num order by CER_NUM;")
        for i in a:
            company_data_queue.put(i)

if __name__ == "__main__":
    a = dts_stock()
    company_data_queue = queue.Queue()  # 公司名字队列
    a.get_company_data()
    dts_type='business_all'
    #写入股东信息表
    #dts_type='business_holder'
    #dts_type='business_all'
    thread_list = []
    for n in range(50):
        producer_thread = threading.Thread(target=a.get_company_detail)  # 多线程
        thread_list.append(producer_thread)
    for t in thread_list:
        #t.setDaemon(True)
        t.start()


