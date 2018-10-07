#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import bcrypt
import pymysql
import concurrent.futures

pymysql.install_as_MySQLdb()
import markdown
import os.path
import re
import subprocess
import torndb
import tornado.escape
from tornado import gen
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import unicodedata
import json
import requests
from bs4 import BeautifulSoup
import lxml
from tornado.options import define, options
from dbconfig import define

# A thread pool to be used for password hashing with bcrypt.
executor = concurrent.futures.ThreadPoolExecutor(2)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            # 首页页面
            (r"/index.html", HomeHandler),
            # 查询企业页面
            (r"/business_search.html", Business_search),
            # 列表显示企业
            (r"/business_list.html", Business_list),
            # 查询企业详情
            (r"/business_detail.html", Business_detail),
            # 查询私募机构
            (r"/pf_company.html", pf_company_search),
            # 列表显示企业
            (r"/pf_company_list.html", pf_company_list),
            # 查询私募地图
            (r"/pf_map.html", pf_map_list),
            # 查询私募详情
            (r"/pf_detail.html", pf_detail),
            # 查询私募管理人发行产品详情
            (r"/pf_product_detail.html", pf_product_base),
            # (r"/archive", ArchiveHandler),
            # (r"/feed", FeedHandler),
            # (r"/entry/([^/]+)", EntryHandler),
            # (r"/compose", ComposeHandler),
            (r"/auth/create", AuthCreateHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/router/rest", api_rest),

            # 查询金融人才证券人才
            # (r"/stock_personal.html", Stock_personal_Handler),
            (r"/person_stock.html", person_stock_Handler),
            # 查询金融人才证券人才详情
            (r"/stock_personal_info.html", Stock_personal_info_Handler),
            # 查询金融人才证券人才本地详情
            (r"/person_stock_detail.html", person_stock_detail_Handler),

            # 查询证券公司从业情况
            (r"/securities_company.html", Securities_company_Handler),
            # 查询基金行业从业情况
            (r"/person_fund.html", person_fund_Handler),
            # 查询基金从业人才详情
            (r"/person_fund_detail.html", person_fund_detail_Handler),
            # 查询证券公司信息
            (r"/stock_company.html", Stock_company_Handler),
            # 搜索证券公司列表
            (r"/stock_company_list.html", Stock_company_list_Handler),
            # 证券公司详细情况
            (r"/stock_company_detail.html", Stock_company_detail_Handler),

            # 上市公司查询
            (r"/public_company_search.html", Public_Company_search_Handler),

            # 新闻列表
            (r"/news_list.html", News_list_Handler),
            # 新闻详细信息
            (r"/news_detail.html", News_detail_Handler),
            # 研报列表
            (r"/stock_report_list.html", Stock_report_list_Handler),
            # 研究报告详细信息
            (r"/stock_report_detail.html", Stock_report_detail_Handler),
            # 个股新闻
            (r"/stock_news_list.html", Stock_news_list_Handler),
            # 个股新闻详细信息
            (r"/stock_news_detail.html", Stock_news_detail_Handler),

            # 无权限页面
            (r"/authdeny.html", authdeny),
        ]
        settings = dict(
            blog_title=u"辅投助手_企业信息查询_公司查询_提供证券、基金、银行、上市企业相关资讯及数据",
            description=u"辅投助手专注服务于个人与企业信息查询,为您提供证券、基金、银行、阳光私募公司、上市企业信息查询,工商信息查询,企业研究报告,企业新闻,企业信用信息查询等相关信息,帮您快速了解企业信息,企业工商信息,企业信用信息等企业经营和人员投资状况,查询更多信息请到辅助投资助手！",
            keywords=u"辅投助手，上市企业新闻,企业信息查询,公司查询,工商查询,企业研究报告,金融人才信息,企业信息监控,企业信用查询,企业信用信息查询系统",
            template_path=os.path.join(os.path.dirname(__file__), "template"),
            static_path=os.path.join(os.path.dirname(__file__), "statics"),
            ui_modules={"Entry": EntryModule},
            xsrf_cookies=True,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/auth/login",
            debug=False,
        )
        super(Application, self).__init__(handlers, **settings)
        # Have one global connection to the blog DB across all handlers
        self.db = torndb.Connection(
            host=options.mysql_host, database=options.mysql_database,
            user=options.mysql_user, password=options.mysql_password)

        self.maybe_create_tables()

    def maybe_create_tables(self):
        try:
            self.db.get("SELECT COUNT(*) from entries;")
        except pymysql.ProgrammingError:
            subprocess.check_call(['mysql',
                                   '--host=' + options.mysql_host,
                                   '--database=' + options.mysql_database,
                                   '--user=' + options.mysql_user,
                                   '--password=' + options.mysql_password],
                                  stdin=open('schema.sql'))


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db

    def get_current_user(self):
        # user_id = self.get_secure_cookie("login_user")
        user_id = 2
        if not user_id: return None
        return self.db.get("SELECT * FROM authors WHERE id = %s", int(user_id))

    def any_author_exists(self):
        return bool(self.db.get("select * from (SELECT COUNT(*) as cnt FROM bigdata.authors) s where s.cnt>1000 "))

    def create_log(self, operate_type='200', operate_event='', operate_detail=''):
        self.db.insert(
            "INSERT INTO `bigdata`.`system_user_log` (`system_operate_ip`,`system_operate_useagent`, `system_operate_type`, `system_operate_business_name`, `system_operate_detail`, `system_operate_user`) VALUES ( %s,%s,%s,%s,%s,%s)",
            self.request.remote_ip, self.request.headers["User-Agent"], operate_type, operate_event, operate_detail,
            self.current_user.id)


class HomeHandler(BaseHandler):
    def get(self):
        userinfo = self.current_user
        if self.current_user == None:
            self.redirect("/auth/login")
            return
        else:  # 登录成功后
            newslist = self.db.query(
                "SELECT `t_news`.`id`,     `t_news`.`title`,     `t_news`.`pubtime`,     `t_news`.`url`,     `t_news`.`tag`,     `t_news`.`refer`,     `t_news`.`body`,     `t_news`.`link_business_id` FROM `bigdata`.`t_news` order by  pub_time desc limit 6 ")
            newslist_finance = self.db.query(
                "SELECT `t_news`.`id`,     `t_news`.`title`,     `t_news`.`pubtime`,     `t_news`.`url`,     `t_news`.`tag`,     `t_news`.`refer`,     `t_news`.`body`,     `t_news`.`link_business_id`,`t_news`.`stkname` FROM `bigdata`.`t_news` where length(stkcode)>1 order by  pub_time desc limit 10 ")
            newslist_tech = self.db.query(
                "SELECT `t_news`.`id`,     `t_news`.`title`,     `t_news`.`pubtime`,     `t_news`.`url`,     `t_news`.`tag`,     `t_news`.`refer`,     `t_news`.`body`,     `t_news`.`link_business_id` FROM `bigdata`.`t_news` where tag='tech' order by  pub_time desc limit 10 ")
            newslist_ent = self.db.query(
                "SELECT `t_news`.`id`,     `t_news`.`title`,     `t_news`.`pubtime`,     `t_news`.`url`,     `t_news`.`tag`,     `t_news`.`refer`,     `t_news`.`body`,     `t_news`.`link_business_id` FROM `bigdata`.`t_news` where tag='ent' order by  pub_time desc limit 10 ")
            stock_report = self.db.query(
                "SELECT `stock_report`.`id`,`stock_report`.`reportname`,`stock_report`.`tag`,`stock_report`.`pubdate`,`stock_report`.`pubtime`,`stock_report`.`refer`,`stock_report`.`stkcode`,`stock_report`.`stkname`,`stock_report`.`body`,`stock_report`.`url`,`stock_report`.`ywpj`,`stock_report`.`pjbd`,`stock_report`.`pjjg`,`stock_report`.`ycsy1`,`stock_report`.`ycsyl1`,`stock_report`.`ycsy2`,`stock_report`.`ycsyl2`,`stock_report`.`instime` FROM `bigdata`.`stock_report` order by pubdate desc limit 10 ")

            business_newscount = self.db.get("select count(*) news_count from bigdata.t_news t ")
            business_count = self.db.get("select count(*) business_count from bigdata.business_base")
            business_list = self.db.query("""
                                    SELECT 
                                        t1.business_id,
                                        t1.business_name,
                                        t1.business_industry,
                                        t1.business_score
                                    FROM
                                        `bigdata`.`business_base` AS t1
                                            JOIN
                                        (SELECT 
                                            ROUND(RAND() * (SELECT 
                                                        MAX(id)
                                                    FROM
                                                        `bigdata`.`business_base`)) AS id
                                        ) AS t2
                                    WHERE
                                        t1.id >= t2.id
                                    ORDER BY t1.id ASC
                                    LIMIT 10

            """)
            business_public_list = self.db.query("""
                SELECT 
                    t1.business_id,
                    t1.business_name,
                    t1.business_industry,
                    t1.business_score
                FROM
                   (SELECT * FROM  `bigdata`.`business_base` where business_plate='A') AS t1
                        JOIN
                    (SELECT 
                        ROUND(RAND() * (SELECT 
                                    MAX(id)
                                FROM
                                    `bigdata`.`business_base` where business_plate='A')) AS id
                    ) AS t2
                WHERE
                    t1.id >= t2.id
                ORDER BY t1.id ASC
                LIMIT 10

            """)
            sql_vippersonal = "SELECT rpi_photo_path,aoi_id, RPI_NAME, sco_name, aoi_name, md5(aoi_name) vaoi_name, eco_name, pti_name, cer_num, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` s ) a WHERE vcer_num >= (( SELECT MAX(a.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a ) - ( SELECT MIN(a1.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a1 )) * RAND() * 2000 + ( SELECT MIN(a2.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a2 ) LIMIT 4"
            vippersonal_list = self.db.query(sql_vippersonal)
            sql_personal = "SELECT aoi_id, RPI_NAME, sco_name, aoi_name, md5(aoi_name) vaoi_name, eco_name, pti_name, cer_num, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` s ) a WHERE vcer_num >= (( SELECT MAX(a.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a ) - ( SELECT MIN(a1.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a1 )) * RAND() * 5000 + ( SELECT MIN(a2.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a2 ) LIMIT 10"
            stockpersonallist = self.db.query(sql_personal)
            sql_fundpersonal = "SELECT aoi_id, RPI_NAME, sco_name,md5(rpi_id) RPI_ID, aoi_name, md5(aoi_name) vaoi_name, eco_name, pti_name, cer_num, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` s ) a WHERE vcer_num >= (( SELECT MAX(a.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a ) - ( SELECT MIN(a1.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a1 )) * RAND() * 100 + ( SELECT MIN(a2.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a2 ) LIMIT 11"
            fundpersonallist = self.db.query(sql_fundpersonal)
            sql_banklist = "SELECT t1.business_id, t1.business_name, t1.business_industry, t1.business_score FROM `bigdata`.`business_base` AS t1 WHERE t1.business_name LIKE '%%银行%%' ORDER BY t1.id ASC LIMIT 10"
            banklist = self.db.query(sql_banklist)
            sql_stockcompanylist = "SELECT t1.business_id, t1.business_name, t1.business_industry, t1.business_score FROM `bigdata`.`business_base` AS t1 WHERE t1.business_name LIKE '%%证券%%' ORDER BY t1.id ASC LIMIT 10"
            stockcompanylist = self.db.query(sql_stockcompanylist)
            sql_fundcompanylist = "SELECT t1.business_id, t1.business_name, t1.business_industry, t1.business_score FROM `bigdata`.`business_base` AS t1 WHERE t1.business_name LIKE '%%基金%%' ORDER BY t1.id ASC LIMIT 10"
            fundcompanylist = self.db.query(sql_fundcompanylist)
            sql_vipfundpersonal = "SELECT rpi_photo_path,md5(aoi_id) AOI_ID,md5(rpi_id) RPI_ID, RPI_NAME, sco_name, aoi_name, md5(aoi_name) vaoi_name, eco_name, pti_name, cer_num, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` s ) a WHERE vcer_num >= (( SELECT MAX(a.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a ) - ( SELECT MIN(a1.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a1 )) * RAND() * 2000 + ( SELECT MIN(a2.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a2 ) LIMIT 4"
            vipfundpersonal_list = self.db.query(sql_vipfundpersonal)
            self.render("index.html", userinfo=userinfo,
                        business_count=business_count,
                        newslists=newslist,
                        newslist_finances=newslist_finance,
                        newslist_techs=newslist_tech,
                        newslist_ents=newslist_ent,
                        business_lists=business_list,
                        business_public_lists=business_public_list,
                        business_newscount=business_newscount,
                        stock_reports=stock_report,
                        stockpersonallists=stockpersonallist,
                        banklists=banklist,
                        stockcompanylists=stockcompanylist,
                        fundcompanylists=fundcompanylist,
                        vipfundpersonal_lists=vipfundpersonal_list,
                        fundpersonallists=fundpersonallist,
                        vippersonallists=vippersonal_list
                        )


# 企业搜索查询
class Business_search(BaseHandler):

    def get(self):
        userinfo = self.current_user
        business_search_hiss = self.db.query(
            """
                        SELECT 
                  system_operate_business_name
                FROM
                    bigdata.system_user_log
                WHERE
                    system_operate_type = 200
                    and system_operate_user=%s
            ORDER BY system_operate_time DESC
            LIMIT 20
            """,
            self.current_user.id)
        business_search_hots = self.db.query(
            """SELECT 
                  system_operate_business_name
                FROM
                    bigdata.system_user_log
                WHERE
                    system_operate_type = 200
            ORDER BY system_operate_time DESC
            LIMIT 20    
            """
        )

        self.render("business_search.html", userinfo=userinfo, business_search_hiss=business_search_hiss,
                    business_search_hots=business_search_hots)


# 企业列表查询
class Business_list(BaseHandler):
    def get(self):
        # business_name = '*'+self.get_argument("business_name", None)+'*'
        business_name = self.get_argument("business_name", None)
        # business_list=self.db.query("select  business_id,business_name,business_legal_name,business_reg_capital,business_reg_time,business_industry,business_scope  from `bigdata`.`business_base` where match(business_name,business_legal_name) against (%s IN BOOLEAN MODE) limit 10",business_name)
        business_list = self.db.query(
            """SELECT 
                    s.business_id,
                    s.business_name,
                    CASE
                        WHEN LENGTH(s.business_legal_name) < 1 THEN t.men_name
                        ELSE business_legal_name
                    END business_legal_name,
                    s.business_reg_capital,
                    s.business_reg_time,
                    s.business_industry,
                    s.business_scope,
                    s.business_score
                FROM
                    `bigdata`.`business_base` s
                        LEFT JOIN
                    `bigdata`.`business_men_base` t ON s.business_legal_id = t.men_id
                    where match(business_name) against(%s)
                LIMIT 50""",
            business_name)
        if len(business_list) > 0:
            self.create_log(operate_type='200', operate_event=self.get_argument("business_name", None))
        self.render("business_list.html", userinfo=self.current_user, business_list=business_list,
                    business_name=business_name)


# 企业详情查询
class Business_detail(BaseHandler):
    def get(self):
        business_id = self.get_argument("id", None)
        business_detail_base = self.db.get(
            "SELECT s.business_id, s.business_name, s.business_logo, s.business_phone, s.business_email, s.business_url, s.business_addres, s.busines_tags, s.business_summary, s.business_update_time, s.business_legal_id, case when length(s.business_legal_name)<1 then t.men_name else business_legal_name end business_legal_name , s.business_reg_capital, s.business_reg_time, s.business_reg_state, s.business_reg_number, s.business_organization_number, s.business_unite_number, s.business_type, s.business_payment_number, s.business_industry, s.business_cycle_time, s.business_approved_time, s.business_reg_Institute, s.business_reg_addres, s.business_en_name, s.business_scope, s.business_score, s.business_plate FROM bigdata.business_base s  left join `bigdata`.`business_men_base` t on s.business_legal_id=t.men_id where s.business_id=%s LIMIT 1",
            business_id)
        business_detail_holdes = self.db.query(
            "SELECT     s.business_id,     s.men_id,     s.men_name,     md5(t.business_name) vmen_name,     s.holder_percent,     s.holder_amomon FROM     `bigdata`.`business_holder` s left join bigdata.business_base t on s.men_name=t.business_name where s.business_id=%s GROUP BY s.business_id , s.men_id , s.men_name , s.holder_percent , s.holder_amomon,t.business_name",
            business_id)
        business_detail_invests = self.db.query(
            "SELECT     s.`business_id`,     s.`invest_name`,     md5(t.business_name) vbusiness_name,     s.`invest_id`,     s.`legal_name`,     s.`legal_id`,     s.`invest_reg_capital`,     s.`invest_amount`,     s.`invest_amomon`,     case when length(s.invest_reg_time)>0 then substr(s.invest_reg_time, 1,10) else s.invest_reg_time end `invest_reg_time`,     s.`invest_state` FROM     `bigdata`.`business_invest` s left join bigdata.business_base t on s.invest_name=t.business_name where s.business_id=%s",
            business_id)
        business_detail_changes = self.db.query(
            "SELECT `business_change`.`id`,     `business_change`.`business_id`,     `business_change`.`change_time`,     `business_change`.`change_name`,     `business_change`.`change_before`,     `business_change`.`change_after`,     `business_change`.`change_ins_time` FROM `bigdata`.`business_change` where business_id=%s",
            business_id)
        sqlreportlist = """
            SELECT
                t1.`id`,
                t1.`reportname`,
                t1.`tag`,
                t1.`pubdate`,
                t1.`pubtime`,
                t1.`refer`,
                t1.`stkcode`,
                t1.`stkname`,
                t1.`body`,
                t1.`url`,
                t1.`ywpj`,
                t1.`pjbd`,
                t1.`pjjg`,
                t1.`ycsy1`,
                t1.`ycsyl1`,
                t1.`ycsy2`,
                t1.`ycsyl2`,
                t1.`instime`
            FROM
                `bigdata`.`stock_report` t1
            INNER JOIN bigdata.public_company_base_info t ON t.stkcode = t1.stkcode
            INNER JOIN bigdata.business_base t2 ON t2.business_name = t.companyname
            WHERE
                t2.business_id =%s         
        """
        reportlist = self.db.query(sqlreportlist, business_id)
        # 上市企业相关新闻列表
        sql = """
            SELECT
                t1.id,
                t1.`title`,
                t1.`pubtime`,
                t1.`url`,
                t1.`tag`,
                t1.`refer`,
                t1.`body`,
                t1.stkcode,
                t1.stkindustry,
                t1.stkname,
                t1.`link_business_id`
            FROM
                `bigdata`.`t_news` t1 INNER JOIN bigdata.public_company_base_info t on t1.stkcode=t.stkcode INNER JOIN bigdata.business_base t2 on t.companyname=t2.business_name
            WHERE
                t2.business_id = %s
            ORDER BY
                pub_time DESC
            LIMIT 50
        """
        newslist = self.db.query(sql, business_id)
        sql_sbzfgjj = """
        SELECT
            c.si_num,
            c.si_begindate,
            c.si_status,
            c.si_all_user,
            c.si_yanglao_user,
            c.si_yiliao_user,
            c.si_gongshang_user,
            c.si_shiye_user,
            b.gjj_num,
            b.gjj_status,
            b.gjj_begindate,
            b.gjj_enddate,
            b.business_ins_time
        FROM
            bigdata.business_base a
        LEFT JOIN bigdata.business_zfgjj b ON a.business_id = b.business_id
        LEFT JOIN bigdata.business_social c ON c.business_id = a.business_id
        where a.business_id=%s
        """
        sbzfgjjlist = self.db.get(sql_sbzfgjj, business_id)
        sql_men = """
        SELECT
            a.men_id,a.men_name,b.men_job
        FROM
            bigdata.business_men_base a INNER JOIN
        bigdata.business_staff_men b on a.men_id=b.men_id
        where b.business_id=%s 
        group by a.men_id,a.men_name,b.men_job

        """
        menlist = self.db.query(sql_men, business_id)
        if business_detail_base is not None:
            if len(business_detail_base) > 0:
                self.create_log(operate_type='200', operate_event=business_detail_base['business_name'])
            self.render("business_detail.html", userinfo=self.current_user, business_detail_base=business_detail_base,
                        business_detail_holdes=business_detail_holdes, business_detail_invests=business_detail_invests,
                        business_detail_changes=business_detail_changes, reportlists=reportlist, newslists=newslist,
                        sbzfgjjlist=sbzfgjjlist, menlists=menlist)


# 证券公司查询
class Stock_company_Handler(BaseHandler):
    def get(self):
        v_business_name = self.get_argument("business_name", None)
        userinfo = self.current_user
        stock_company_provinces = self.db.query(
            "SELECT b.registerProvince,b.registerCity,  COUNT(b.registerCity) AS vcount FROM  pf_base_info a   right JOIN  pf_base b ON  a.djbm=b.registerNo WHERE  b.registerCity <>'' GROUP BY b.registerProvince,b.registerCity order by vcount desc limit 60")
        stock_company_office_provinces = self.db.query(
            "SELECT b.officeProvince,b.officeCity,  COUNT(b.officeCity) AS vcount FROM  pf_base_info a   right JOIN  pf_base b ON  a.djbm=b.registerNo WHERE  b.registerCity <>'' GROUP BY b.officeProvince,b.officeCity order by vcount desc limit 60")

        business_search_hiss = self.db.query(
            "SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_user=%s and system_operate_type=400  group by system_operate_business_name order by  sort desc",
            self.current_user.id)
        business_search_hots = self.db.query(
            "SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_type=400  group by system_operate_business_name order by  sort desc ")
        self.render("stock_company.html", userinfo=userinfo, business_search_hiss=business_search_hiss,
                    business_search_hots=business_search_hots, pf_company_provinces=stock_company_provinces,
                    pf_company_office_provinces=stock_company_office_provinces)


class Stock_company_list_Handler(BaseHandler):
    def get(self):
        v_business_name = self.get_argument("business_name", None)
        if v_business_name is not None:
            business_name = '*' + v_business_name + '*'
        business_city = self.get_argument("business_city", None)
        if v_business_name is not None:
            business_list = self.db.query(
                "SELECT     s.business_id,     s.business_name,     case when length(s.business_legal_name)<1 then t.men_name else business_legal_name end business_legal_name ,     s.business_reg_capital,     s.business_reg_time,     s.business_industry,     s.business_scope FROM     `bigdata`.`business_base` s left join `bigdata`.`business_men_base` t on s.business_legal_id=t.men_id where s.business_name like %s limit 50",
                business_name)
            if len(business_list) > 0:
                self.create_log(operate_type='400', operate_event=self.get_argument("business_name", None))
            self.render("stock_company_list.html", userinfo=self.current_user, business_list=business_list,
                        business_citys=business_city, business_names=v_business_name)
        else:
            business_list = self.db.query(
                "SELECT     a.business_id,     a.business_name, 	case when LENGTH(a.business_legal_name)<1 then t.men_name else a.business_legal_name end business_legal_name ,     a.business_reg_capital,     a.business_reg_time,     a.business_industry,     a.business_scope FROM     `bigdata`.`business_base` a         INNER JOIN     bigdata.company_stock b ON a.business_name = b.AOI_NAME         INNER JOIN     bigdata.company_stock_base c ON c.AOI_ID = b.AOI_ID left join `bigdata`.`business_men_base` t on a.business_legal_id=t.men_id  ORDER BY c.MRI_REG_CAPITAL DESC")
            business_count = len(business_list)
            self.render("stock_company_list.html", userinfo=self.current_user, business_list=business_list,
                        business_names=v_business_name, business_count=business_count)


# 证券公司详细信息
class Stock_company_detail_Handler(BaseHandler):
    def get(self):
        business_id = self.get_argument("id", None)
        business_detail_base = self.db.get(
            "SELECT `business_id`, `business_name`, `business_logo`, `business_phone`, `business_email`, `business_url`, `business_addres`, `busines_tags`, `business_summary`, `business_update_time`, `business_legal_id`, case when LENGTH(business_legal_name)<1 then t.men_name else business_legal_name end business_legal_name , `business_reg_capital`, `business_reg_time`, `business_reg_state`, `business_reg_number`, `business_organization_number`, `business_unite_number`, `business_type`, `business_payment_number`, `business_industry`, `business_cycle_time`, `business_approved_time`, `business_reg_Institute`, `business_reg_addres`, `business_en_name`, `business_scope`, `business_score`, `business_plate` FROM `bigdata`.`business_base`s left join `bigdata`.`business_men_base` t on s.business_legal_id=t.men_id where s.business_id=%s LIMIT 1",
            business_id)
        business_detail_holdes = self.db.query(
            "SELECT business_id,men_id,men_name,md5(men_name) vmen_name,holder_percent,holder_amomon FROM `bigdata`.`business_holder` where business_id=%s group by business_id,men_id,men_name,holder_percent,holder_amomon",
            business_id)
        business_detail_invests = self.db.query(
            "SELECT `business_id`, `invest_name`, `invest_id`, `legal_name`, `legal_id`, `invest_reg_capital`, `invest_amount`, `invest_amomon`, DATE_FORMAT(invest_reg_time,'%%Y-%%m') `invest_reg_time`, `invest_state` FROM `bigdata`.`business_invest` where business_id=%s",
            business_id)
        stk_sub_base = self.db.query(
            "SELECT a.AOI_ID,a.MBOI_BRANCH_FULL_NAME,a.MBOI_BUSINESS_SCOPE,a.MBOI_OFF_ADDRESS,a.MBOI_CS_TEL,a.MBOI_PERSON_IN_CHARGE FROM `bigdata`.`company_stock_sub_base` a INNER JOIN `bigdata`.`company_stock` b ON a.AOI_ID = b.AOI_ID inner join `bigdata`.`business_base` c on c.business_name=b.AOI_NAME   where c.business_id=%s",
            business_id)
        stk_branch_base = self.db.query(
            "SELECT a.AOI_ID,a.MSDI_ZJJ_COMPLAINTS_TEL as MSDI_ZJJ_COMPLAINTS_TEL ,a.MSDI_NAME,a.MSDI_REG_PCC,a.MSDI_SALES_MANAGER,a.MSDI_REG_ADDRESS,a.MSDI_CS_TEL FROM `bigdata`.`company_stock_branch_base` a INNER JOIN `bigdata`.`company_stock` b ON a.AOI_ID = b.AOI_ID inner join `bigdata`.`business_base` c on c.business_name=b.AOI_NAME   where c.business_id=%s",
            business_id)
        stk_person_info = self.db.query(
            "SELECT `person_stock_info`.`AOI_ID`,     `person_stock_info`.`PPP_ID`,     `person_stock_info`.`RPI_NAME`,     `person_stock_info`.`SCO_NAME`,     `person_stock_info`.`ECO_NAME`,     `person_stock_info`.`AOI_NAME`,     `person_stock_info`.`PTI_NAME`,     `person_stock_info`.`CTI_NAME`,     `person_stock_info`.`CER_NUM`,     `person_stock_info`.`PPP_GET_DATE`,     `person_stock_info`.`PPP_END_DATE`,     `person_stock_info`.`COUNTCER`,     `person_stock_info`.`COUNTCX`,     `person_stock_info`.`RPI_ID`,     `person_stock_info`.`RPI_PHOTO_PATH`,     `person_stock_info`.`ADI_ID`,     `person_stock_info`.`ADI_NAME` FROM `bigdata`.`person_stock_info` where `bigdata`.`person_stock_info`.AOI_NAME=%s limit 20",
            business_detail_base['business_name'])
        if len(business_detail_base) > 0:
            self.create_log(operate_type='400', operate_event=business_detail_base['business_name'])
        self.render("stock_company_detail.html", stk_sub_bases=stk_sub_base, stk_branch_bases=stk_branch_base,
                    userinfo=self.current_user, business_detail_base=business_detail_base,
                    business_detail_holdes=business_detail_holdes, business_detail_invests=business_detail_invests,
                    stk_person_infos=stk_person_info)


# 私募基金公司查询
class pf_company_search(BaseHandler):

    def get(self):
        userinfo = self.current_user
        pf_company_provinces = self.db.query(
            "SELECT b.registerProvince,b.registerCity,  COUNT(b.registerCity) AS vcount FROM  pf_base_info a   right JOIN  pf_base b ON  a.djbm=b.registerNo WHERE  b.registerCity <>'' GROUP BY b.registerProvince,b.registerCity order by vcount desc limit 60")
        pf_company_office_provinces = self.db.query(
            "SELECT b.officeProvince,b.officeCity,  COUNT(b.officeCity) AS vcount FROM  pf_base_info a   right JOIN  pf_base b ON  a.djbm=b.registerNo WHERE  b.registerCity <>'' GROUP BY b.officeProvince,b.officeCity order by vcount desc limit 60")

        business_search_hiss = self.db.query(
            "SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_user=%s and system_operate_type=300  group by system_operate_business_name order by  sort desc limit 20",
            self.current_user.id)
        business_search_hots = self.db.query(
            "SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_type=300  group by system_operate_business_name order by  sort desc limit 20 ")
        self.render("pf_company_search.html", userinfo=userinfo, business_search_hiss=business_search_hiss,
                    business_search_hots=business_search_hots, pf_company_provinces=pf_company_provinces,
                    pf_company_office_provinces=pf_company_office_provinces)


# 私募基金列表查询
class pf_company_list(BaseHandler):
    def get(self):
        # business_name = '*'+self.get_argument("business_name", None)+'*'
        # business_list=self.db.query("select  pf_id,jjglrqc,jjglrqcyw,djbm,zzjgdm,djsj,zcdz,bgdz,zczb,sjzb,sjbl,qyxz,jglx,ygrs,clsj,frdb  from `bigdata`.`pf_base_info` where match(jjglrqc,frdb) against (%s IN BOOLEAN MODE)",business_name)
        # if len(business_list)>0:
        # self.create_log(operate_type='201',operate_event=self.get_argument("business_name", None))
        v_business_name = self.get_argument("business_name", None)
        if v_business_name is not None:
            business_name = '%' + v_business_name + '%'
        business_city = self.get_argument("business_city", None)
        search_type = self.get_argument("search_type", None)
        if business_city is not None:
            if search_type == "reg":
                business_list = self.db.query(
                    "SELECT c.registerNo, a.business_id, a.business_name, case when length(a.business_legal_name)<1 then t.men_name else a.business_legal_name end business_legal_name, a.business_reg_capital, a.business_reg_time, a.business_industry, a.business_scope, a.business_phone, b.jglx FROM `business_base` a INNER JOIN pf_base_info  b ON a.business_reg_number = b.gszch INNER JOIN pf_base c ON c.registerNo = b.djbm left join `bigdata`.`business_men_base` t on a.business_legal_id=t.men_id WHERE c.registerCity = %s limit 200",
                    business_city)
            else:
                business_list = self.db.query(
                    "SELECT c.registerNo, a.business_id, a.business_name,case when length(a.business_legal_name)<1 then t.men_name else business_legal_name end business_legal_name ,a.business_reg_capital, a.business_reg_time, a.business_industry, a.business_scope, a.business_phone, b.jglx FROM `business_base` a INNER JOIN pf_base_info  b ON a.business_reg_number = b.gszch INNER JOIN pf_base c ON c.registerNo = b.djbm left join `bigdata`.`business_men_base` t on a.business_legal_id=t.men_id WHERE c.officecity = %s limit 200",
                    business_city)
            self.render("pf_company_list.html", userinfo=self.current_user, business_list=business_list,
                        business_citys=business_city, business_names=v_business_name)
        if v_business_name is not None:
            business_list = self.db.query(
                "SELECT     b.djbm registerNo,     b.jglx,     a.business_id,     a.business_name,     CASE         WHEN length(a.business_legal_name)<1 then t.men_name         ELSE a.business_legal_name     END business_legal_name,     a.business_reg_capital,     a.business_reg_time,     a.business_industry,     a.business_scope,     a.business_score FROM     `bigdata`.`business_base` a         left JOIN 	bigdata.pf_base_info b ON b.gszch = a.business_id         LEFT JOIN     `bigdata`.`business_men_base` t ON a.business_legal_id = t.men_id WHERE     a.business_name LIKE %s  limit 10",
                business_name)
            if len(business_list) > 0:
                self.create_log(operate_type='300', operate_event=self.get_argument("business_name", None))
            self.render("pf_company_list.html", userinfo=self.current_user, business_list=business_list,
                        business_citys=business_city, business_names=v_business_name)


# 私募基金详情
class pf_detail(BaseHandler):
    def get(self):
        business_id = self.get_argument("id", None)
        business_detail_base = self.db.get(
            "SELECT `business_id`, `business_name`, `business_logo`, `business_phone`, `business_email`, `business_url`, `business_addres`, `busines_tags`, `business_summary`, `business_update_time`, `business_legal_id`, case when length(business_legal_name)<1 then t.men_name else business_legal_name end business_legal_name, `business_reg_capital`, `business_reg_time`, `business_reg_state`, `business_reg_number`, `business_organization_number`, `business_unite_number`, `business_type`, `business_payment_number`, `business_industry`, `business_cycle_time`, `business_approved_time`, `business_reg_Institute`, `business_reg_addres`, `business_en_name`, `business_scope`, `business_score`, `business_plate` FROM `bigdata`.`business_base` left join `bigdata`.`business_men_base` t on business_legal_id=t.men_id where business_id=%s LIMIT 1",
            business_id)
        business_detail_holdes = self.db.query(
            "SELECT business_id,men_id,men_name,holder_percent,holder_amomon FROM `bigdata`.`business_holder` where business_id=%s group by business_id,men_id,men_name,holder_percent,holder_amomon",
            business_id)
        business_detail_invests = self.db.query(
            "SELECT `business_id`, `invest_name`, `invest_id`, `legal_name`, `legal_id`, `invest_reg_capital`, `invest_amount`, `invest_amomon`, DATE_FORMAT(invest_reg_time,'%%Y-%%m') `invest_reg_time`, `invest_state` FROM `bigdata`.`business_invest` where business_id=%s",
            business_id)
        pf_detail_product = self.db.query(
            "SELECT a.pf_id,a.cpmc,a.cpid,a.cpfl,c.pf_gllx,c.pf_jjlx,c.pf_clsj,c.pf_yzzt,c.pf_basj FROM bigdata.pf_product_info  a left join bigdata.pf_base_info b on a.pf_id=b.pf_id left join pf_product_base c on c.pf_cpid=a.cpid where b.gszch=%s order by c.pf_clsj desc",
            business_id)
        if len(business_detail_base) > 0:
            self.create_log(operate_type='300', operate_event=business_detail_base['business_name'])
        self.render("pf_detail.html", pf_detail_products=pf_detail_product, userinfo=self.current_user,
                    business_detail_base=business_detail_base, business_detail_holdes=business_detail_holdes,
                    business_detail_invests=business_detail_invests)


# 私募管理人发行产品详情
class pf_product_base(BaseHandler):
    def get(self):
        pf_cpid = self.get_argument("id", None)
        pf_product_bases = self.db.get(
            "SELECT `pf_id`,    `pf_cpid`,    `pf_cpmc`,    `pf_jjbm`,    `pf_clsj`,    `pf_basj`,    `pf_bajd`,    `pf_jjlx`,    `pf_bz`,    `pf_jjglrmc`,    `pf_jjglrid`,    `pf_gllx`,    `pf_tgrmc`,    `pf_yzzt`,    `pf_gxsj`,    `pf_tbts`,    `pf_bbyb`,    `pf_bbbnb`,    `pf_bbnb`,    `pf_bbjb`FROM `bigdata`.`pf_product_base` where pf_cpid=%s",
            pf_cpid)
        self.render("pf_product_detail.html", pf_product_bases=pf_product_bases, userinfo=self.current_user)


# 私募地图
class pf_map_list(BaseHandler):
    def get(self):
        # pf_map_list = self.db.query("SELECT c.registerNo, a.business_id, a.business_name, a.business_legal_name, a.business_reg_capital, a.business_reg_time, a.business_industry, a.business_scope, a.business_phone, b.jglx FROM `business_base` a INNER JOIN pf_base_info  b ON a.business_reg_number = b.gszch INNER JOIN pf_base c ON c.registerNo = b.djbm WHERE c.officecity = %s limit 10")
        # print(pf_map_list)
        self.render("pf_map.html", userinfo=self.current_user)


# 上市公司查询
class Public_Company_search_Handler(BaseHandler):

    def get(self):
        userinfo = self.current_user
        public_company_list = self.db.query(
            "SELECT a.`business_id`, a.`business_name`,b.stkcode,b.stkname FROM `bigdata`.`business_base`  a INNER JOIN bigdata.public_company_base_info b on a.business_name=b.companyname WHERE business_plate = 'A' limit 100")
        public_company_list_xsb = self.db.query(
            "SELECT  `business_base`.`business_id`, `business_base`.`business_name` FROM `bigdata`.`business_base`  where business_plate='C' limit 200")

        # business_search_hots = self.db.query(
        #    "SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_type=200  group by system_operate_business_name order by  sort desc limit 20 ")

        self.render("public_company_search.html", userinfo=userinfo,
                    public_company_lists=public_company_list, public_company_lists_xsb=public_company_list_xsb)


class api_rest(BaseHandler):
    def get(self):
        api_name = self.get_argument("api_name", None)
        if api_name is not None:
            api_name = api_name
            resultapi = self.db.query(
                "SELECT  a.registerProvince,  COUNT(a.registerProvince) as vcount, a.officeProvince FROM bigdata.pf_base a WHERE a.registerProvince <> a.officeProvince and a.registerProvince!='' GROUP BY a.registerProvince , a.officeProvince")
            # print(resultapi)
            resultapi = json.dumps(resultapi)

        else:
            api_name = 'TEST_API'
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        # self.write(json.dumps({'message': 'ok','data':'+resultapi+''}))
        self.write(resultapi)
        self.finish()


# 金融人才证券从业查询
class Stock_personal_Handler(BaseHandler):

    def get(self):
        personal_name = self.get_argument("personal_name", None)
        aoid = self.get_argument("aoid", None)
        userinfo = self.current_user
        if aoid is None:

            url = 'http://person.sac.net.cn/pages/registration/train-line-register!gsUDDIsearch.action'
            data = {'filter_EQS_PPP_NAME': personal_name, 'sqlkey': 'registration', 'sqlval': 'SEARCH_FINISH_NAME'}
            headers = [
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36"}
            ]
            response = requests.post(url=url, data=data, headers=headers[0], timeout=5)
            res = response.json()
        else:
            vtype = self.get_argument("type", None)
            url = 'http://person.sac.net.cn/pages/registration/train-line-register!gsUDDIsearch.action'
            data = {'filter_LES_ROWNUM': '100', 'filter_GTS_RNUM': '0', 'filter_EQS_PTI_ID': vtype,
                    'filter_EQS_AOI_ID': aoid, 'ORDERNAME': 'PP#PTI_ID,PP#PPP_NAME', 'ORDER': 'ASC',
                    'sqlkey': 'registration', 'sqlval': 'SEARCH_FINISH_PUBLICITY'}
            headers = [
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36"}
            ]
            response = requests.post(url=url, data=data, headers=headers[0], timeout=5)
            res = response.json()
        self.render("stock_personal.html", userinfo=userinfo, personal_list=res)


# 金融人才证券从业本地查询
class Stock_personal_local_Handler(BaseHandler):

    def get(self):
        personal_name = self.get_argument("personal_name", None)
        userinfo = self.current_user
        if personal_name is not None:
            personal_list = self.db.query(
                "SELECT `person_stock_info`.`AOI_ID`,  md5( `person_stock_info`.`cer_num`)  vcer_num,   `person_stock_info`.`PPP_ID`,     `person_stock_info`.`RPI_NAME`,     `person_stock_info`.`SCO_NAME`,     `person_stock_info`.`ECO_NAME`,     `person_stock_info`.`AOI_NAME`,     `person_stock_info`.`PTI_NAME`,     `person_stock_info`.`CTI_NAME`,     `person_stock_info`.`CER_NUM`,     `person_stock_info`.`PPP_GET_DATE`,     `person_stock_info`.`PPP_END_DATE`,     `person_stock_info`.`COUNTCER`,     `person_stock_info`.`COUNTCX`,     `person_stock_info`.`RPI_ID`,     `person_stock_info`.`RPI_PHOTO_PATH`,     `person_stock_info`.`ADI_ID`,     `person_stock_info`.`ADI_NAME` FROM `bigdata`.`person_stock_info` where `bigdata`.`person_stock_info`.`RPI_NAME`=%s",
                personal_name)
        else:
            personal_list = self.db.query(
                "SELECT `person_stock_info`.`AOI_ID`,  md5( `person_stock_info`.`cer_num`)  vcer_num,   `person_stock_info`.`PPP_ID`,     `person_stock_info`.`RPI_NAME`,     `person_stock_info`.`SCO_NAME`,     `person_stock_info`.`ECO_NAME`,     `person_stock_info`.`AOI_NAME`,     `person_stock_info`.`PTI_NAME`,     `person_stock_info`.`CTI_NAME`,     `person_stock_info`.`CER_NUM`,     `person_stock_info`.`PPP_GET_DATE`,     `person_stock_info`.`PPP_END_DATE`,     `person_stock_info`.`COUNTCER`,     `person_stock_info`.`COUNTCX`,     `person_stock_info`.`RPI_ID`,     `person_stock_info`.`RPI_PHOTO_PATH`,     `person_stock_info`.`ADI_ID`,     `person_stock_info`.`ADI_NAME` FROM `bigdata`.`person_stock_info` limit 30")
        self.render("stock_personal.html", userinfo=userinfo, personal_lists=personal_list)


# 金融人才证券从业人员详情
class Stock_personal_info_Handler(BaseHandler):
    def get(self):
        id = self.get_argument("id", None)
        userinfo = self.current_user
        url = 'http://person.sac.net.cn/pages/registration/train-line-register!gsUDDIsearch.action'
        data = {'filter_EQS_PPP_ID': id, 'sqlkey': 'registration', 'sqlval': 'SD_A02Leiirkmuexe_b9ID'}
        headers = [
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36"}
        ]
        response = requests.post(url=url, data=data, headers=headers[0], timeout=5)

        if response.status_code == 200:
            res = response.json()
            print(res)
            filter_EQS_RPI_ID = res[0]['RPI_ID']
            surl = 'http://person.sac.net.cn/pages/registration/train-line-register!gsUDDIsearch.action'
            sdata = {'filter_EQS_RH#RPI_ID': filter_EQS_RPI_ID, 'sqlkey': 'registration',
                     'sqlval': 'SEARCH_LIST_BY_PERSON'}
            sresponse = requests.post(url=surl, data=sdata, headers=headers[0], timeout=5)
            if sresponse.status_code == 200:
                personal_info_chg = sresponse.json()

            vurl = 'http://person.sac.net.cn/pages/registration/train-line-register!gsUDDIsearch.action'
            data = {'filter_EQS_RPI_ID': filter_EQS_RPI_ID, 'sqlkey': 'registration', 'sqlval': 'SELECT_PERSON_INFO'}
            vresponse = requests.post(url=vurl, data=data, headers=headers[0], timeout=5)
            if vresponse.status_code == 200:
                vres = vresponse.json()
                self.render("stock_personal_info.html", userinfo=userinfo, personal_info=vres,
                            personal_info_chg=personal_info_chg)


# 金融人才证券从业人员详情

# 基金行业从业人员信息
class person_fund_Handler(BaseHandler):
    def get(self):
        searchname = self.get_argument("searchname", None)
        searchorgid = self.get_argument("searchorgid", None)
        userinfo = self.current_user
        if searchname is not None:
            res = self.db.query(
                "SELECT	md5(`person_fund_base_info`.`AOI_ID`) AOI_ID,	`person_fund_base_info`.`AOI_NAME`,	`person_fund_base_info`.`OTC_ID`,	`person_fund_base_info`.`OTC_NAME`,	MD5(`person_fund_base_info`.`RPI_ID`) RPI_ID,	`person_fund_base_info`.`RPI_NAME`,	`person_fund_base_info`.`ADI_ID`,	`person_fund_base_info`.`ADI_NAME`,	`person_fund_base_info`.`SCO_NAME`,	`person_fund_base_info`.`PTI_NAME`,	`person_fund_base_info`.`ECO_NAME`,	`person_fund_base_info`.`CER_NUM`,	`person_fund_base_info`.`OBTAIN_DATE`,	`person_fund_base_info`.`ARRIVE_DATE`FROM	`bigdata`.`person_fund_base_info` where MATCH(AOI_NAME,RPI_NAME,CER_NUM) AGAINST(%s)",
                searchname)
        else:
            if searchorgid is not None:
                res = self.db.query(
                    "SELECT	md5(`person_fund_base_info`.`AOI_ID`) AOI_ID,	`person_fund_base_info`.`AOI_NAME`,	`person_fund_base_info`.`OTC_ID`,	`person_fund_base_info`.`OTC_NAME`,	md5(`person_fund_base_info`.`RPI_ID`) RPI_ID,	`person_fund_base_info`.`RPI_NAME`,	`person_fund_base_info`.`ADI_ID`,	`person_fund_base_info`.`ADI_NAME`,	`person_fund_base_info`.`SCO_NAME`,	`person_fund_base_info`.`PTI_NAME`,	`person_fund_base_info`.`ECO_NAME`,	`person_fund_base_info`.`CER_NUM`,	`person_fund_base_info`.`OBTAIN_DATE`,	`person_fund_base_info`.`ARRIVE_DATE`FROM	`bigdata`.`person_fund_base_info` where md5(aoi_id)=%s",
                    searchorgid)
                searchname = None
            else:
                res = self.db.query(
                    "SELECT md5(`AOI_ID`) AOI_ID,	`AOI_NAME`,	`OTC_ID`,	`OTC_NAME`,	md5(`RPI_ID`) RPI_ID,	`RPI_NAME`,	`ADI_ID`,	`ADI_NAME`,	`SCO_NAME`,	`PTI_NAME`,	`ECO_NAME`,	`CER_NUM`,	`OBTAIN_DATE`,	`ARRIVE_DATE`, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` s ) a WHERE vcer_num >= (( SELECT MAX(a.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a ) - ( SELECT MIN(a1.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a1 )) * RAND() * 2000 + ( SELECT MIN(a2.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a2 ) LIMIT 20")

        vippersonal_sql = "SELECT RPI_PHOTO_PATH,aoi_id, RPI_NAME, md5(RPI_ID) RPI_ID,sco_name, aoi_name, md5(aoi_name) vaoi_name, eco_name, pti_name, cer_num, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` s ) a WHERE vcer_num >= (( SELECT MAX(a.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a ) - ( SELECT MIN(a1.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a1 )) * RAND() * 2000 + ( SELECT MIN(a2.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` ) a2 ) LIMIT 4"
        vippersonal_list = self.db.query(vippersonal_sql)
        if len(res) > 0:
            # self.create_log(operate_type='500', operate_event=res['AOI_NAME'] + res['RPI_NAME'])
            pass
        self.render("person_fund.html", userinfo=userinfo,
                    vippersonallists=vippersonal_list,
                    personal_lists=res,
                    searchname=searchname)


class person_fund_detail_Handler(BaseHandler):
    def get(self):
        rpi_id = self.get_argument("rpi_id", None)
        userinfo = self.current_user
        sql_personal_info_chg = "SELECT `person_fund_changelist`.`CER_NUM`, `person_fund_changelist`.`AOI_NAME`, `person_fund_changelist`.`CERTC_NAME`, `person_fund_changelist`.`OBTAIN_DATE`, `person_fund_changelist`.`PTI_NAME`, `person_fund_changelist`.`RPI_ID` FROM `bigdata`.`person_fund_changelist` WHERE MD5(RPI_ID) =%s"
        personal_info_chg = self.db.query(sql_personal_info_chg, rpi_id)
        res = self.db.get(
            "SELECT * FROM bigdata.person_fund_base_info where MD5(RPI_ID)=%s",
            rpi_id)
        vippersonal_sql = "SELECT RPI_PHOTO_PATH, aoi_id, RPI_NAME, md5(RPI_ID) RPI_ID, sco_name, aoi_name, md5(aoi_name) vaoi_name, eco_name, pti_name, cer_num, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_fund_base_info` s WHERE s.aoi_id IN ( SELECT aoi_id FROM `bigdata`.`person_fund_base_info` WHERE md5(rpi_id) =% s )) a ORDER BY RAND() LIMIT 4"
        vippersonal_list = self.db.query(vippersonal_sql, rpi_id)
        if len(res) > 0:
            self.create_log(operate_type='500', operate_event=res['AOI_NAME'] + res['RPI_NAME'])
        self.render("person_fund_detail.html", userinfo=userinfo, personal_info=res,
                    personal_info_chg=personal_info_chg, vippersonallists=vippersonal_list)


# 证券行业从业人员信息
class person_stock_Handler(BaseHandler):
    def get(self):
        searchname = self.get_argument("searchname", None)
        searchorgid = self.get_argument("searchorgid", None)
        userinfo = self.current_user
        if searchname is not None:
            res = self.db.query(
                "SELECT md5( `person_stock_info`.`AOI_ID` ) AOI_ID, `person_stock_info`.`AOI_NAME`, MD5( `person_stock_info`.`RPI_ID` ) RPI_ID, `person_stock_info`.`RPI_NAME`, `person_stock_info`.`ADI_ID`, `person_stock_info`.`ADI_NAME`, `person_stock_info`.`SCO_NAME`, `person_stock_info`.`PTI_NAME`, `person_stock_info`.`ECO_NAME`, `person_stock_info`.`CER_NUM`, md5(`person_stock_info`.`CER_NUM`) VCER_NUM,`person_stock_info`.`PPP_GET_DATE`, `person_stock_info`.`PPP_END_DATE` FROM `bigdata`.`person_stock_info` WHERE MATCH (RPI_NAME, CER_NUM) AGAINST (% s) limit 100",
                searchname)
        else:
            if searchorgid is not None:
                res = self.db.query(
                    "SELECT md5( `person_stock_info`.`AOI_ID` ) AOI_ID, `person_stock_info`.`AOI_NAME`, md5( `person_stock_info`.`RPI_ID` ) RPI_ID, `person_stock_info`.`RPI_NAME`, `person_stock_info`.`ADI_ID`, `person_stock_info`.`ADI_NAME`, `person_stock_info`.`SCO_NAME`, `person_stock_info`.`PTI_NAME`, `person_stock_info`.`ECO_NAME`, `person_stock_info`.`CER_NUM`,md5(`person_stock_info`.`CER_NUM`) VCER_NUM, `person_stock_info`.`PPP_GET_DATE`, `person_stock_info`.`PPP_END_DATE` FROM `bigdata`.`person_stock_info` WHERE md5(aoi_id) =%s limit 200",
                    searchorgid)
                searchname = None
            else:
                res = self.db.query(
                    "SELECT md5(`AOI_ID`) AOI_ID, `AOI_NAME`, md5(`RPI_ID`) RPI_ID, `RPI_NAME`, `ADI_ID`, `ADI_NAME`, `SCO_NAME`, `PTI_NAME`, `ECO_NAME`, `CER_NUM`, `PPP_GET_DATE`, `PPP_END_DATE`, md5(cer_num) AS VCER_NUM FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` s ) a WHERE vcer_num >= (( SELECT MAX(a.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) VCER_NUM FROM `bigdata`.`person_stock_info` ) a ) - ( SELECT MIN(a1.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a1 )) * RAND() * 2000 + ( SELECT MIN(a2.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a2 ) LIMIT 20")

        vippersonal_sql = "SELECT RPI_PHOTO_PATH,aoi_id, RPI_NAME, md5(RPI_ID) RPI_ID,sco_name, aoi_name, md5(aoi_name) vaoi_name, eco_name, pti_name, cer_num, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` s ) a WHERE vcer_num >= (( SELECT MAX(a.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a ) - ( SELECT MIN(a1.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a1 )) * RAND() * 2000 + ( SELECT MIN(a2.vcer_num) FROM ( SELECT *, RIGHT (CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` ) a2 ) LIMIT 4"
        vippersonal_list = self.db.query(vippersonal_sql)
        if len(res) > 0:
            # self.create_log(operate_type='500', operate_event=res['AOI_NAME'] + res['RPI_NAME'])
            pass
        self.render("person_stock.html", userinfo=userinfo,
                    vippersonallists=vippersonal_list,
                    personal_lists=res,
                    searchname=searchname)


class person_stock_detail_Handler(BaseHandler):
    def get(self):
        cer_id = self.get_argument("cer_id", None)
        userinfo = self.current_user
        # sql_personal_info_chg="SELECT `person_fund_changelist`.`CER_NUM`, `person_fund_changelist`.`AOI_NAME`, `person_fund_changelist`.`CERTC_NAME`, `person_fund_changelist`.`OBTAIN_DATE`, `person_fund_changelist`.`PTI_NAME`, `person_fund_changelist`.`RPI_ID` FROM `bigdata`.`person_fund_changelist` WHERE MD5(RPI_ID) =%s"
        personal_info_chg = {}
        res = self.db.get(
            "SELECT * FROM bigdata.`person_stock_info` where MD5(cer_num)=%s",
            cer_id)
        vippersonal_sql = "SELECT RPI_PHOTO_PATH, aoi_id, RPI_NAME, md5(RPI_ID) RPI_ID, sco_name, aoi_name, md5(aoi_name) vaoi_name, eco_name, pti_name, cer_num, md5(cer_num) AS vcer_num FROM ( SELECT s.*, RIGHT (s.CER_NUM, 11) vcer_num FROM `bigdata`.`person_stock_info` s WHERE s.AOI_ID IN ( SELECT AOI_ID FROM `bigdata`.`person_stock_info` WHERE md5(CER_NUM) =%s )) a ORDER BY RAND() LIMIT 4"
        vippersonal_list = self.db.query(vippersonal_sql, cer_id)
        if len(res) > 0:
            self.create_log(operate_type='500', operate_event=res['AOI_NAME'] + res['RPI_NAME'])
        self.render("person_stock_detail.html", userinfo=userinfo, personal_info=res,
                    personal_info_chg=personal_info_chg, vippersonallists=vippersonal_list)


# 证券公司从业人员详情
class Securities_company_Handler(BaseHandler):
    def get(self):
        personal_name = self.get_argument("personal_name", None)
        userinfo = self.current_user
        url = 'http://person.sac.net.cn/pages/registration/train-line-register!orderSearch.action'
        data = {'filter_EQS_OTC_ID': '10', 'ORDERNAME': 'AOI#AOI_NAME', 'ORDER': 'ASC', 'sqlkey': 'registration',
                'sqlval': 'SELECT_LINE_PERSON'}
        headers = [
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36",
                'X-Requested-With': 'XMLHttpRequest'}
        ]
        response = requests.post(url=url, data=data, headers=headers[0], timeout=15)
        if response.status_code == 200:
            res = response.json()
            self.render("securities_company.html", userinfo=userinfo, securities_company_list=res)


# 新闻详情页面
class News_detail_Handler(BaseHandler):
    def get(self):
        id = self.get_argument("id", None)
        newsdetail = self.db.get(
            "SELECT `t_news`.`id`, `t_news`.`title`, `t_news`.`pubtime`, `t_news`.`url`, `t_news`.`tag`, `t_news`.`refer`, `t_news`.`body`, `t_news`.`link_business_id` FROM `bigdata`.`t_news` where id=%s",
            id)
        self.render("news_detail.html", userinfo=self.current_user, newsdetail=newsdetail)


# 新闻列表
class News_list_Handler(BaseHandler):
    def get(self):
        news_type = self.get_argument("type", None)
        vnews_page = self.get_argument("page", 0)
        page_count = 20
        news_page = int(vnews_page) * page_count
        if news_type == 'all':
            sql = "SELECT `t_news`.`id`, `t_news`.`title`, `t_news`.`pubtime`, `t_news`.`url`, `t_news`.`tag`,`t_news_tag_dict`.`tag_dict_name`, `t_news`.`refer`, `t_news`.`body`, `t_news`.`link_business_id` FROM `bigdata`.`t_news` left join `bigdata`.`t_news_tag_dict` on `t_news`.`tag`=`t_news_tag_dict`.`tag_dictid` where `t_news`.`tag`!='finance' and stkcode is null order by pub_time desc limit {}, 20".format(
                news_page)
            newslist = self.db.query(sql)
        else:
            sql = "SELECT `t_news`.`id`, `t_news`.`title`, `t_news`.`pubtime`, `t_news`.`url`, `t_news`.`tag`,`t_news_tag_dict`.`tag_dict_name`, `t_news`.`refer`, `t_news`.`body`, `t_news`.`link_business_id` FROM `bigdata`.`t_news` left join `bigdata`.`t_news_tag_dict` on `t_news`.`tag`=`t_news_tag_dict`.`tag_dictid`   where `t_news`.`tag`=%s   order by  pub_time desc limit {}, 20".format(
                news_page)
            newslist = self.db.query(sql, news_type)
        self.render("news_list.html", userinfo=self.current_user, newslists=newslist, page_count=page_count,
                    news_page=int(vnews_page), news_search='')

    def post(self):
        vnews_search = self.get_argument("news_search", None)
        if vnews_search != None:
            news_search = '%' + vnews_search + '%'
            page_count = 0
            news_page = 20
            # sql = "SELECT `t_news`.`id`, `t_news`.`title`, `t_news`.`pubtime`, `t_news`.`url`, `t_news`.`tag`, `t_news`.`refer`, `t_news`.`body`, `t_news`.`link_business_id` FROM `bigdata`.`t_news` where title like {} or content {} order by newsid limit 0, 200"%(news_search,news_search)
            sql = "SELECT `t_news`.`id`, `t_news`.`title`, `t_news`.`pubtime`, `t_news`.`url`, `t_news`.`tag`, `t_news`.`refer`, `t_news`.`body`, `t_news`.`link_business_id` FROM `bigdata`.`t_news` where title like %s or body like %s order by newsid limit 0, 200"
            newslist = self.db.query(sql, news_search, news_search)
            self.render("news_list.html", userinfo=self.current_user, newslists=newslist, page_count=page_count,
                        news_page=int(news_page), news_search=vnews_search)


# 研报详情页面
class Stock_report_detail_Handler(BaseHandler):
    def get(self):
        id = self.get_argument("id", None)
        stock_report_detail = self.db.get(
            "SELECT `stock_report`.`id`,`stock_report`.`reportname`,`stock_report`.`tag`,`stock_report`.`pubdate`,`stock_report`.`pubtime`,`stock_report`.`refer`,`stock_report`.`stkcode`,`stock_report`.`stkname`,replace(replace(replace(body,'[',''),']',''),'}','') body,`stock_report`.`url`,`stock_report`.`ywpj`,`stock_report`.`pjbd`,`stock_report`.`pjjg`,`stock_report`.`ycsy1`,`stock_report`.`ycsyl1`,`stock_report`.`ycsy2`,`stock_report`.`ycsyl2`,`stock_report`.`instime` FROM `bigdata`.`stock_report`  where id=%s",
            id)
        self.render("stock_report_detail.html", userinfo=self.current_user, stock_report_detail=stock_report_detail)


# 研报列表
class Stock_report_list_Handler(BaseHandler):
    def get(self):
        vreport_search = self.get_argument("report_search", '')
        news_type = self.get_argument("type", '')
        vnews_page = self.get_argument("page", 0)
        page_count = 20
        news_page = int(vnews_page) * page_count
        if news_type == 'all':
            if vreport_search != None:
                report_search = '%' + vreport_search + '%'
                sql = "SELECT `stock_report`.`id`,`stock_report`.`reportname`,`stock_report`.`tag`,`stock_report`.`pubdate`,`stock_report`.`pubtime`,`stock_report`.`refer`,`stock_report`.`stkcode`,`stock_report`.`stkname`,`stock_report`.`body`,`stock_report`.`url`,`stock_report`.`ywpj`,`stock_report`.`pjbd`,`stock_report`.`pjjg`,`stock_report`.`ycsy1`,`stock_report`.`ycsyl1`,`stock_report`.`ycsy2`,`stock_report`.`ycsyl2`,`stock_report`.`instime` FROM `bigdata`.`stock_report` where stkname like %s  or pjjg like %s  or stkcode like %s or pubdate like %s order by pubdate desc limit {news_page}, 20".format(
                    news_page=news_page)
                reportlist = self.db.query(sql, report_search, report_search, report_search, report_search)
            else:
                sql = "SELECT `stock_report`.`id`,`stock_report`.`reportname`,`stock_report`.`tag`,`stock_report`.`pubdate`,`stock_report`.`pubtime`,`stock_report`.`refer`,`stock_report`.`stkcode`,`stock_report`.`stkname`,`stock_report`.`body`,`stock_report`.`url`,`stock_report`.`ywpj`,`stock_report`.`pjbd`,`stock_report`.`pjjg`,`stock_report`.`ycsy1`,`stock_report`.`ycsyl1`,`stock_report`.`ycsy2`,`stock_report`.`ycsyl2`,`stock_report`.`instime` FROM `bigdata`.`stock_report` order by pubdate desc limit {}, 20".format(
                    news_page)
                reportlist = self.db.query(sql)
        else:
            sql = "SELECT `stock_report`.`id`,`stock_report`.`reportname`,`stock_report`.`tag`,`stock_report`.`pubdate`,`stock_report`.`pubtime`,`stock_report`.`refer`,`stock_report`.`stkcode`,`stock_report`.`stkname`,`stock_report`.`body`,`stock_report`.`url`,`stock_report`.`ywpj`,`stock_report`.`pjbd`,`stock_report`.`pjjg`,`stock_report`.`ycsy1`,`stock_report`.`ycsyl1`,`stock_report`.`ycsy2`,`stock_report`.`ycsyl2`,`stock_report`.`instime` FROM `bigdata`.`stock_report` where tag=%s  order by pubdate desc limit {}, 20".format(
                news_page)
            reportlist = self.db.query(sql, news_type)
        self.render("stock_report_list.html", userinfo=self.current_user, reportlists=reportlist, page_count=page_count,
                    news_page=int(vnews_page), report_search=vreport_search)

    def post(self):
        vreport_search = self.get_argument("report_search", '')
        news_type = self.get_argument("type", '')
        vnews_page = self.get_argument("page", 0)
        page_count = 20
        news_page = int(vnews_page) * page_count
        if vreport_search != None:
            report_search = '%' + vreport_search + '%'
            # sql = "SELECT `t_news`.`id`, `t_news`.`title`, `t_news`.`pubtime`, `t_news`.`url`, `t_news`.`tag`, `t_news`.`refer`, `t_news`.`body`, `t_news`.`link_business_id` FROM `bigdata`.`t_news` where title like {} or content {} order by newsid limit 0, 200"%(news_search,news_search)
            sql = "SELECT `stock_report`.`id`,`stock_report`.`reportname`,`stock_report`.`tag`,`stock_report`.`pubdate`,`stock_report`.`pubtime`,`stock_report`.`refer`,`stock_report`.`stkcode`,`stock_report`.`stkname`,`stock_report`.`body`,`stock_report`.`url`,`stock_report`.`ywpj`,`stock_report`.`pjbd`,`stock_report`.`pjjg`,`stock_report`.`ycsy1`,`stock_report`.`ycsyl1`,`stock_report`.`ycsy2`,`stock_report`.`ycsyl2`,`stock_report`.`instime` FROM `bigdata`.`stock_report`  where reportname like %s or body like %s order by pubtime limit {}, 200".format(
                news_page)
            reportlist = self.db.query(sql, report_search, report_search)
            self.render("stock_report_list.html", userinfo=self.current_user, reportlists=reportlist,
                        page_count=page_count,
                        news_page=int(vnews_page), report_search=vreport_search)


# 个股新闻详情页面
class Stock_news_detail_Handler(BaseHandler):
    def get(self):
        id = self.get_argument("id", None)
        stock_news_detail = self.db.get(
            "SELECT `t_news`.`id`,`t_news`.`title`,`t_news`.`pubtime`,`t_news`.`url`,`t_news`.`tag`,`t_news`.`refer`,`t_news`.`abstract`,`t_news`.`body`,`t_news`.`link_business_id`,`t_news`.`newsid`,`t_news`.`stkcode`,`t_news`.`stkname`,`t_news`.`stkindustry`,`t_news`.`instime` FROM `bigdata`.`t_news` where id=%s",
            id)
        self.render("stock_news_detail.html", userinfo=self.current_user, stock_news_detail=stock_news_detail)


# 个股新闻列表
class Stock_news_list_Handler(BaseHandler):
    def get(self):
        vreport_search = self.get_argument("report_search", '')
        news_type = self.get_argument("type", '')
        vnews_page = self.get_argument("page", 0)
        page_count = 100
        news_page = (int(vnews_page)) * page_count
        if news_type == 'all':
            if vreport_search != '':
                # report_search = '%' + vreport_search + '%'
                report_search = vreport_search
                sql = "SELECT `t_news`.`id`,`t_news`.`title`,`t_news`.`pubtime`,`t_news`.`url`,`t_news`.`tag`,`t_news`.`refer`,`t_news`.`abstract`,`t_news`.`body`,`t_news`.`link_business_id`,`t_news`.`newsid`,`t_news`.`stkcode`,`t_news`.`stkname`,`t_news`.`stkindustry`,`t_news`.`instime` FROM `bigdata`.`t_news` where  length(stkcode)>1 and (stkname = %s or stkcode = %s or stkindustry = %s or pubtime = %s)  order by pub_time desc limit {news_page}, 100".format(
                    news_page=news_page)
                newslist = self.db.query(sql, report_search, report_search, report_search, report_search)
            else:
                sql = "SELECT `t_news`.`id`,`t_news`.`title`,`t_news`.`pubtime`,`t_news`.`url`,`t_news`.`tag`,`t_news`.`refer`,`t_news`.`abstract`,`t_news`.`body`,`t_news`.`link_business_id`,`t_news`.`newsid`,`t_news`.`stkcode`,`t_news`.`stkname`,`t_news`.`stkindustry`,`t_news`.`instime` FROM `bigdata`.`t_news` where  length(stkcode)>1 order by pub_time desc limit {}, 100".format(
                    news_page)
                newslist = self.db.query(sql)
        else:
            sql = "SELECT `t_news`.`id`,`t_news`.`title`,`t_news`.`pubtime`,`t_news`.`url`,`t_news`.`tag`,`t_news`.`refer`,`t_news`.`abstract`,`t_news`.`body`,`t_news`.`link_business_id`,`t_news`.`newsid`,`t_news`.`stkcode`,`t_news`.`stkname`,`t_news`.`stkindustry`,`t_news`.`instime` FROM `bigdata`.`t_news` where  length(stkcode)>1 and tag=%s order by pub_time desc limit {}, 100".format(
                news_page)
            newslist = self.db.query(sql, news_type)
        self.render("stock_news_list.html", userinfo=self.current_user, newslists=newslist, page_count=page_count,
                    news_page=int(news_page), report_search=vreport_search)


# 无权限页面
class authdeny(BaseHandler):
    def get(self):
        self.render("authdeny.html", userinfo=self.current_user)


class EntryHandler(BaseHandler):
    def get(self, slug):
        entry = self.db.get("SELECT * FROM entries WHERE slug = %s", slug)
        if not entry: raise tornado.web.HTTPError(404)
        self.render("entry.html", entry=entry)


class ArchiveHandler(BaseHandler):
    def get(self):
        entries = self.db.query("SELECT * FROM entries ORDER BY published "
                                "DESC")
        self.render("archive.html", entries=entries)


class FeedHandler(BaseHandler):
    def get(self):
        entries = self.db.query("SELECT * FROM entries ORDER BY published "
                                "DESC LIMIT 10")
        self.set_header("Content-Type", "application/atom+xml")
        self.render("feed.xml", entries=entries)


class ComposeHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        id = self.get_argument("id", None)
        entry = None
        if id:
            entry = self.db.get("SELECT * FROM entries WHERE id = %s", int(id))
        self.render("compose.html", entry=entry)

    @tornado.web.authenticated
    def post(self):
        id = self.get_argument("id", None)
        title = self.get_argument("title")
        text = self.get_argument("markdown")
        html = markdown.markdown(text)
        if id:
            entry = self.db.get("SELECT * FROM entries WHERE id = %s", int(id))
            if not entry: raise tornado.web.HTTPError(404)
            slug = entry.slug
            self.db.execute(
                "UPDATE entries SET title = %s, markdown = %s, html = %s "
                "WHERE id = %s", title, text, html, int(id))
        else:
            slug = unicodedata.normalize("NFKD", title).encode(
                "ascii", "ignore")
            slug = re.sub(r"[^\w]+", " ", slug)
            slug = "-".join(slug.lower().strip().split())
            if not slug: slug = "entry"
            while True:
                e = self.db.get("SELECT * FROM entries WHERE slug = %s", slug)
                if not e: break
                slug += "-2"
            self.db.execute(
                "INSERT INTO entries (author_id,title,slug,markdown,html,"
                "published) VALUES (%s,%s,%s,%s,%s,UTC_TIMESTAMP())",
                self.current_user.id, title, slug, text, html)
        self.redirect("/entry/" + slug)


class AuthCreateHandler(BaseHandler):
    def get(self):
        self.render("create_author.html")

    @gen.coroutine
    def post(self):
        if self.any_author_exists():
            raise tornado.web.HTTPError(400, "author already created")
        hashed_password = yield executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            bcrypt.gensalt())
        author_id = self.db.execute(
            "INSERT INTO authors (email, name, hashed_password) "
            "VALUES (%s, %s, %s)",
            self.get_argument("email"), self.get_argument("name"),
            hashed_password)
        self.set_secure_cookie("login_user", str(author_id))
        self.redirect(self.get_argument("next", "/"))


class AuthLoginHandler(BaseHandler):
    def post(self):
        # If there are no authors, redirect to the account creation page.
        if not self.any_author_exists():
            self.redirect("/auth/create")
        else:
            self.render("login.html", error=None)

    @gen.coroutine
    def get(self):
        self.email = 'guest@futouzs.com'
        self.password = '1'
        # author = self.db.get("SELECT * FROM authors WHERE email = %s",self.get_argument("email"))
        author = self.db.get("SELECT * FROM authors WHERE email = %s", self.email)
        if not author:
            self.render("login.html", error="邮箱或密码不正确")
            return
        hashed_password = yield executor.submit(
            # bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),tornado.escape.utf8(author.hashed_password))
            bcrypt.hashpw, tornado.escape.utf8(self.password), tornado.escape.utf8(author.hashed_password))
        if str(hashed_password, encoding="utf-8") == author.hashed_password:
            self.set_secure_cookie("login_user", str(author.id))
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("login.html", error="密码错误")


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("login_user")
        self.redirect(self.get_argument("next", "/"))


class EntryModule(tornado.web.UIModule):
    def render(self, entry):
        return self.render_string("index.html", entry=entry)


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application(), xheaders=True)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
