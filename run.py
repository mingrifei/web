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

from tornado.options import define, options

define("port", default=8080, help="run on the given port", type=int)
define("mysql_host", default="192.168.0.34:8635", help="blog database host")
define("mysql_database", default="bigdata", help="blog database name")
define("mysql_user", default="root", help="blog database user")
define("mysql_password", default="", help="blog database password")


# A thread pool to be used for password hashing with bcrypt.
executor = concurrent.futures.ThreadPoolExecutor(2)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            #首页页面
            (r"/index.html", HomeHandler),
            #查询企业页面
            (r"/business_search.html", Business_search),
            #列表显示企业
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
            #(r"/archive", ArchiveHandler),
            #(r"/feed", FeedHandler),
            #(r"/entry/([^/]+)", EntryHandler),
            #(r"/compose", ComposeHandler),
            (r"/auth/create", AuthCreateHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/router/rest", api_rest),
        ]
        settings = dict(
            blog_title=u"企业信息服务平台",
            template_path=os.path.join(os.path.dirname(__file__), "template"),
            static_path=os.path.join(os.path.dirname(__file__), "statics"),
            ui_modules={"Entry": EntryModule},
            xsrf_cookies=True,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/auth/login",
            debug=True,
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
        user_id = self.get_secure_cookie("login_user")
        if not user_id: return None
        return self.db.get("SELECT * FROM authors WHERE id = %s", int(user_id))

    def any_author_exists(self):
        return bool(self.db.get("SELECT * FROM bigdata.authors LIMIT 1"))

    def create_log(self,operate_type='200',operate_event='',operate_detail=''):
        self.db.execute(
            "INSERT INTO `bigdata`.`system_user_log` (`system_operate_ip`,`system_operate_useagent`, `system_operate_type`, `system_operate_business_name`, `system_operate_detail`, `system_operate_user`) VALUES ( %s,%s,%s,%s,%s,%s)",
            self.request.remote_ip, self.request.headers["User-Agent"], operate_type, operate_event,operate_detail,self.current_user.id)


class HomeHandler(BaseHandler):
    def get(self):
        userinfo=self.current_user
        if self.current_user==None:
            self.redirect("/auth/login")
            return
        else:#登录成功后
            business_count = self.db.get("SELECT FORMAT(sum(case when business_reg_capital like '%%万元人民币%%' "
                                           "then replace(business_reg_capital,'万元人民币','')*10000 "
                                            "when business_reg_capital like '%%未公开%%' "
                                            "then 0 "
                                            "when business_reg_capital like '%%万美元%%' "
                                            "then replace(business_reg_capital,'万美元','')*60000 "
                                             "when business_reg_capital like '%%万人民币%%' "
                                            "then replace(business_reg_capital,'万人民币','')*10000 "
                                              "when business_reg_capital like '%%万%%' "
                                            "then replace(business_reg_capital,'万','')*10000 "
                                           "else business_reg_capital end)/100000000,2) `business_reg_capital`, "
                                           "format(count(*),0) `business_count` FROM business_base LIMIT 5")
            self.render("index.html", userinfo=userinfo,business_count=business_count)
#企业搜索查询
class Business_search(BaseHandler):

    def get(self):
        userinfo = self.current_user
        business_search_hiss=self.db.query("SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_user=%s and system_operate_type=200  group by system_operate_business_name order by  sort desc",self.current_user.id)
        business_search_hots=self.db.query("SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_type=200 group by system_operate_business_name order by  sort desc ")

        self.render("business_search.html", userinfo=userinfo,business_search_hiss=business_search_hiss,business_search_hots=business_search_hots)
#企业列表查询
class Business_list(BaseHandler):
    def get(self):
        business_name = '*'+self.get_argument("business_name", None)+'*'
        business_list=self.db.query("select  business_id,business_name,business_legal_name,business_reg_capital,business_reg_time,business_industry,business_scope  from `bigdata`.`business_base` where match(business_name,business_legal_name) against (%s IN BOOLEAN MODE) limit 10",business_name)
        if len(business_list)>0:
            self.create_log(operate_type='200',operate_event=self.get_argument("business_name", None))
        self.render("business_list.html", userinfo=self.current_user,business_list=business_list)

#企业详情查询
class Business_detail(BaseHandler):
    def get(self):
        business_id =self.get_argument("id", None)
        business_detail_base=self.db.get("SELECT `business_id`, `business_name`, `business_logo`, `business_phone`, `business_email`, `business_url`, `business_addres`, `busines_tags`, `business_summary`, `business_update_time`, `business_legal_id`, `business_legal_name`, `business_reg_capital`, `business_reg_time`, `business_reg_state`, `business_reg_number`, `business_organization_number`, `business_unite_number`, `business_type`, `business_payment_number`, `business_industry`, `business_cycle_time`, `business_approved_time`, `business_reg_Institute`, `business_reg_addres`, `business_en_name`, `business_scope`, `business_score`, `business_plate` FROM `bigdata`.`business_base` where business_id=%s LIMIT 1",business_id)
        business_detail_holdes=self.db.query("SELECT business_id,men_id,men_name,holder_percent,holder_amomon FROM `bigdata`.`business_holder` where business_id=%s group by business_id,men_id,men_name,holder_percent,holder_amomon",business_id)
        business_detail_invests=self.db.query("SELECT `business_id`, `invest_name`, `invest_id`, `legal_name`, `legal_id`, `invest_reg_capital`, `invest_amount`, `invest_amomon`, DATE_FORMAT(invest_reg_time,'%%Y-%%m') `invest_reg_time`, `invest_state` FROM `bigdata`.`business_invest` where business_id=%s",business_id)
        if len(business_detail_base)>0:
            self.create_log(operate_type='200', operate_event=business_detail_base['business_name'])
        self.render("business_detail.html", userinfo=self.current_user,business_detail_base=business_detail_base,business_detail_holdes=business_detail_holdes,business_detail_invests=business_detail_invests)
#私募基金公司查询
class pf_company_search(BaseHandler):

    def get(self):
        userinfo = self.current_user
        pf_company_provinces=self.db.query("SELECT b.registerProvince,b.registerCity,  COUNT(b.registerCity) AS vcount FROM  pf_base_info a   right JOIN  pf_base b ON  a.djbm=b.registerNo WHERE  b.registerCity <>'' GROUP BY b.registerProvince,b.registerCity order by vcount desc limit 60")
        pf_company_office_provinces=self.db.query("SELECT b.officeProvince,b.officeCity,  COUNT(b.officeCity) AS vcount FROM  pf_base_info a   right JOIN  pf_base b ON  a.djbm=b.registerNo WHERE  b.registerCity <>'' GROUP BY b.officeProvince,b.officeCity order by vcount desc limit 60")

        business_search_hiss=self.db.query("SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_user=%s and system_operate_type=300  group by system_operate_business_name order by  sort desc",self.current_user.id)
        business_search_hots=self.db.query("SELECT SUBSTRING_INDEX(GROUP_CONCAT(system_operate_time ORDER BY system_operate_time DESC), ',',1)  as sort,   system_operate_business_name FROM bigdata.system_user_log where system_operate_type=300  group by system_operate_business_name order by  sort desc ")
        self.render("pf_company_search.html", userinfo=userinfo, business_search_hiss=business_search_hiss,business_search_hots=business_search_hots,pf_company_provinces=pf_company_provinces,pf_company_office_provinces=pf_company_office_provinces)
#私募基金列表查询
class pf_company_list(BaseHandler):
    def get(self):
        #business_name = '*'+self.get_argument("business_name", None)+'*'
        #business_list=self.db.query("select  pf_id,jjglrqc,jjglrqcyw,djbm,zzjgdm,djsj,zcdz,bgdz,zczb,sjzb,sjbl,qyxz,jglx,ygrs,clsj,frdb  from `bigdata`.`pf_base_info` where match(jjglrqc,frdb) against (%s IN BOOLEAN MODE)",business_name)
        #if len(business_list)>0:
            #self.create_log(operate_type='201',operate_event=self.get_argument("business_name", None))
        v_business_name=self.get_argument("business_name", None)
        if v_business_name is not None:
            business_name = '*' + v_business_name + '*'
        business_city = self.get_argument("business_city", None)
        search_type = self.get_argument("search_type", None)
        if business_city is not None:
            if search_type=="reg":
                business_list=self.db.query("SELECT c.registerNo, a.business_id, a.business_name, a.business_legal_name, a.business_reg_capital, a.business_reg_time, a.business_industry, a.business_scope, a.business_phone, b.jglx FROM `business_base` a INNER JOIN pf_base_info  b ON a.business_reg_number = b.gszch INNER JOIN pf_base c ON c.registerNo = b.djbm WHERE c.registerCity = %s limit 10",business_city)
            else:
                business_list=self.db.query("SELECT c.registerNo, a.business_id, a.business_name, a.business_legal_name, a.business_reg_capital, a.business_reg_time, a.business_industry, a.business_scope, a.business_phone, b.jglx FROM `business_base` a INNER JOIN pf_base_info  b ON a.business_reg_number = b.gszch INNER JOIN pf_base c ON c.registerNo = b.djbm WHERE c.officecity = %s limit 10",business_city)
            self.render("pf_company_list.html", userinfo=self.current_user, business_list=business_list)
        if v_business_name is not None:
            business_list = self.db.query("select b.djbm registerNo,b.jglx, business_id,business_name,business_legal_name,business_reg_capital,business_reg_time,business_industry,business_scope  from `bigdata`.`business_base` inner join pf_base_info b on b.gszch=business_base.business_id where match(business_name,business_legal_name) against (%s IN BOOLEAN MODE) limit 10",business_name)
            if len(business_list) > 0:
                self.create_log(operate_type='300', operate_event=self.get_argument("business_name", None))
            self.render("pf_company_list.html", userinfo=self.current_user,business_list=business_list)
#私募基金详情
class pf_detail(BaseHandler):
    def get(self):
        business_id =self.get_argument("id", None)
        business_detail_base=self.db.get("SELECT `business_id`, `business_name`, `business_logo`, `business_phone`, `business_email`, `business_url`, `business_addres`, `busines_tags`, `business_summary`, `business_update_time`, `business_legal_id`, `business_legal_name`, `business_reg_capital`, `business_reg_time`, `business_reg_state`, `business_reg_number`, `business_organization_number`, `business_unite_number`, `business_type`, `business_payment_number`, `business_industry`, `business_cycle_time`, `business_approved_time`, `business_reg_Institute`, `business_reg_addres`, `business_en_name`, `business_scope`, `business_score`, `business_plate` FROM `bigdata`.`business_base` where business_id=%s LIMIT 1",business_id)
        business_detail_holdes=self.db.query("SELECT business_id,men_id,men_name,holder_percent,holder_amomon FROM `bigdata`.`business_holder` where business_id=%s group by business_id,men_id,men_name,holder_percent,holder_amomon",business_id)
        business_detail_invests=self.db.query("SELECT `business_id`, `invest_name`, `invest_id`, `legal_name`, `legal_id`, `invest_reg_capital`, `invest_amount`, `invest_amomon`, DATE_FORMAT(invest_reg_time,'%%Y-%%m') `invest_reg_time`, `invest_state` FROM `bigdata`.`business_invest` where business_id=%s",business_id)
        pf_detail_product=self.db.query("SELECT a.pf_id,a.cpmc,a.cpid,a.cpfl,c.pf_gllx,c.pf_jjlx,c.pf_clsj,c.pf_yzzt,c.pf_basj FROM bigdata.pf_product_info  a left join bigdata.pf_base_info b on a.pf_id=b.pf_id left join pf_product_base c on c.pf_cpid=a.cpid where b.gszch=%s order by c.pf_clsj desc",business_id)
        if len(business_detail_base)>0:
            self.create_log(operate_type='300', operate_event=business_detail_base['business_name'])
        self.render("pf_detail.html",pf_detail_products=pf_detail_product,userinfo=self.current_user,business_detail_base=business_detail_base,business_detail_holdes=business_detail_holdes,business_detail_invests=business_detail_invests)
#私募管理人发行产品详情
class pf_product_base(BaseHandler):
    def get(self):
        pf_cpid = self.get_argument("id", None)
        pf_product_bases = self.db.get(
            "SELECT `pf_id`,    `pf_cpid`,    `pf_cpmc`,    `pf_jjbm`,    `pf_clsj`,    `pf_basj`,    `pf_bajd`,    `pf_jjlx`,    `pf_bz`,    `pf_jjglrmc`,    `pf_jjglrid`,    `pf_gllx`,    `pf_tgrmc`,    `pf_yzzt`,    `pf_gxsj`,    `pf_tbts`,    `pf_bbyb`,    `pf_bbbnb`,    `pf_bbnb`,    `pf_bbjb`FROM `bigdata`.`pf_product_base` where pf_cpid=%s",
            pf_cpid)
        self.render("pf_product_detail.html", pf_product_bases=pf_product_bases, userinfo=self.current_user)


#私募地图
class pf_map_list(BaseHandler):
    def get(self):
        #pf_map_list = self.db.query("SELECT c.registerNo, a.business_id, a.business_name, a.business_legal_name, a.business_reg_capital, a.business_reg_time, a.business_industry, a.business_scope, a.business_phone, b.jglx FROM `business_base` a INNER JOIN pf_base_info  b ON a.business_reg_number = b.gszch INNER JOIN pf_base c ON c.registerNo = b.djbm WHERE c.officecity = %s limit 10")
        #print(pf_map_list)
        self.render("pf_map.html", userinfo=self.current_user)




class api_rest(BaseHandler):
    def get(self):
        api_name = self.get_argument("api_name", None)
        if api_name is not None:
            api_name=api_name
            resultapi=self.db.query("SELECT  a.registerProvince,  COUNT(a.registerProvince) as vcount, a.officeProvince FROM bigdata.pf_base a WHERE a.registerProvince <> a.officeProvince and a.registerProvince!='' GROUP BY a.registerProvince , a.officeProvince")
            #print(resultapi)
            resultapi=json.dumps(resultapi)

        else:
            api_name='TEST_API'
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        #self.write(json.dumps({'message': 'ok','data':'+resultapi+''}))
        self.write(resultapi)
        self.finish()

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
    def get(self):
        # If there are no authors, redirect to the account creation page.
        if not self.any_author_exists():
            self.redirect("/auth/create")
        else:
            self.render("login.html", error=None)

    @gen.coroutine
    def post(self):
        author = self.db.get("SELECT * FROM authors WHERE email = %s",
                             self.get_argument("email"))
        if not author:
            self.render("login.html", error="邮箱或密码不正确")
            return
        hashed_password = yield executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            tornado.escape.utf8(author.hashed_password))
        if str(hashed_password, encoding = "utf-8") == author.hashed_password:
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
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
