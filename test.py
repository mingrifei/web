#!/usr/bin/env python
import os,requests

f = open("d:\\apt\\urls_pf.txt",'r')  # 返回一个文件对象
lines = f.readlines()  # 调用文件的 readline()方法
i=0
vdata=''
for line in lines:
    i=i+1
    #r=requests.get(line)
    #print(r.text)

    if(i%1==0):
        vdata=vdata+line
        data = line
        headers = {'content-type': 'text/plain','User-Agent': 'curl/7.12.1'}
        r = requests.post('http://data.zz.baidu.com/urls?site=www.futouzs.com&token=bC7EMK6gg5kB2HrJ', data=data, headers=headers)
        print(r.text)
    #print (line)

f.close()