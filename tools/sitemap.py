#coding:utf-8
#python生成sitemap，超过5万条数据自动生成新文件。
#
import os,datetime
host = 'http://www.futouzs.com/' #手动设置你网站的域名，别忘记了结尾的斜杠！
#rm = os.popen('rm -rf sitemap') #自动新建一个存放sitemap.xml的文件夹，默认叫sitemap，可自行修改。
dir = os.popen('mkdir sitemap') #自动新建一个存放sitemap.xml的文件夹，默认叫sitemap，可自行修改。
path = 'sitemap/'#设定sitemap.xml文件存放的路径，别忘记了结尾的斜杠！
path1 = 'static/sitemap/'#设定sitemap.xml文件存放的路径，别忘记了结尾的斜杠！
lastmod = datetime.date(2018,10,11)
def add_file(j,f1,host,path):
    file_name = 'sitemap_%s.xml'%(j)
    f1.write("\n<sitemap>\n<loc>%s%s%s</loc>\n<lastmod>%s</lastmod>\n</sitemap>"%(host,path1,file_name,lastmod))
    f=open("%s%s"%(path,file_name),"a")
    f.write('<?xml version="1.0" encoding="utf-8"?>\n<urlset  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    return f
#判断总的URL数
c = 0
for i in open('url.txt'):
    url = i.strip()
    if len(url)==0:
        pass
    else:
        c+=1
print (c)
#判断需要生成的sitemap个数
file_num = c%50000
if file_num==0:
    file_num = c/50000
    print ('总共有%s条URL，生成%s个sitemap文件'%(c,file_num))
else:
    file_num = (c/50000)+1
    print ('总共有%s条URL，生成%s个sitemap文件'%(c,file_num))
#自动按5W条URL生成sitemap，并自动命名为sitemap_1.xml
i = 0
j = 2
f = open('%s/sitemap_1.xml'%(path),'w+')
f.write('<?xml version="1.0" encoding="utf-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
f1 = open('%s/sitemapindex.xml'%(path),'a')
f1.write('<?xml version="1.0" encoding="utf-8"?>\n<sitemapindex  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
f1.write("\n<sitemap>\n<loc>%s%s%s</loc>\n<lastmod>%s</lastmod>\n</sitemap>"%(host,path1,'sitemap_1.xml',lastmod))
for url in open('url.txt'):
    url = url.strip()
    i += 1
    if i == 50000 or j == 50000:
        f.write('\n</urlset>')
        f.close()
        i = 0
        f = add_file(j,f1,host,path)
        j += 1
    f.write("\n<url>\n<loc>%s%s</loc>\n<lastmod>%s</lastmod>\n<priority>0.8</priority>\n</url>"%(host,url,lastmod))
f.write('\n</urlset>')
f1.write('\n</sitemapindex>')
f1.close()
