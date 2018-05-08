#!/usr/bin/env python
import os,requests

f = open("C:\\Users\\Administrator\\Documents\\urls10.txt",'r')  # 返回一个文件对象
lines = f.readlines()  # 调用文件的 readline()方法
i=0
vdata=''
for line in lines:
    i=i+1
    #r=requests.get(line)
    vdata = vdata + line
    data = vdata

    if(i%2000==0):

        #print(data)
        headers = {'content-type': 'text/plain','User-Agent': 'curl/7.12.1'}
        r = requests.post('http://data.zz.baidu.com/urls?site=www.futouzs.com&token=bC7EMK6gg5kB2HrJ', data=data, headers=headers)
        print(r.text)
        print(i)
        vdata = ''
    #print (line)

f.close()