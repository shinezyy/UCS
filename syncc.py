#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Date     : 2015/09/25 20:21:53
FileName : syncc.py
Author   : septicmk
"""

from HttpClient import *
import re
import logging
import configparser
import getopt
import sys
from importlib import reload
from html import unescape
reload(sys)
# sys.setdefaultencoding('utf-8')

force_update_flag = False

logging.basicConfig(
    filename='UCS.log',
    level=logging.DEBUG,
    format='%(asctime)s  %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
    datefmt='%a, %d %b %Y %H:%M:%S',
)

def usage():
    print('''
[options]
    -f, --force-update      Download all files and overwrite the existed.
                            Useful when teachers have updated original files.
                            ATTENTION: Causing heavy net traffic.
''')

def check_existed(path):
    import os
    return os.path.exists(path)

def pause():
    eval(input('press \'Enter\' to continue'))

def get_revalue(html, rex, er, ex):
    if type(html) is not str:
        html = html.decode('utf-8')
    v = re.search(rex, html)
    if v is None:
        if ex:
            logging.error(er)
            raise TypeError(er)
        else:
            logging.warning(er)
        return ''
    return v.group(1)

class Course:

    def __init__(self):
        self.hosturl = 'http://sep.ucas.ac.cn'
        self.loginurl = 'http://sep.ucas.ac.cn/slogin'
        self.req = HttpClient()
        config = configparser.ConfigParser()
        config.read('./config.ini')
        self.usrname =  config.get('USER','usrname')
        self.passwd = config.get('USER', 'passwd')
        self.pwd = config.get('USER', 'savedir')
        if not (self.usrname and self.passwd and self.pwd):
            print('Please setup your account in \'config.ini\'')
            pause()
            sys.exit()

    def login(self):

        self.req.Get(self.hosturl)
        postData = {'userName': self.usrname,
                    'pwd': self.passwd,
                    'sb':'sb'}
        html = self.req.Post(self.loginurl, postData)
        logging.info('login success')

        course_index = 'http://sep.ucas.ac.cn/portal/site/16'
        html = self.req.Get(course_index) 

        Identity= get_revalue(html, r'Identity=(.+?)"', 'get Identity error', 1)
        logging.debug("Identity=" + Identity)

        html = self.req.Get("http://course.ucas.ac.cn/portal/plogin?Identity={0}".format(Identity) )
        session = get_revalue(html, r'session=(.+?)&', 'get session error', 1)
        _mid = get_revalue(html, r'_mid=(.+?)"', 'get mid error', 1)
        guid = get_revalue(html, r'guid=(.+?)"', 'get guid error', 1)
        logging.debug("session=" + session)
        logging.debug("_mid=" + _mid)
        logging.debug("guid=" + guid)

        html = self.req.Get("http://course.ucas.ac.cn/portal?sakai.session={0}&_mid={1}".format(session, _mid))
        course_urls = re.findall(r'http://course.ucas.ac.cn/portal/site/\d+', html.decode('utf-8'))
        #return course_urls
        for test_url in course_urls:
            self.get_resource(test_url)


    def get_resource(self, url):
        import html.parser
        import os

        html_parser = html.parser.HTMLParser()
        html = self.req.Get(url)
        res_url = get_revalue(html, r'class="icon-sakai-resources" href="(.+?)"', 'get resource error', 1)
        logging.debug("res_url= "+res_url)
        html = self.req.Get(res_url)
        wtf_url = get_revalue(html, r'http://course.ucas.ac.cn/portal/tool-reset/(.+?)/', 'what the fuxk error', 1)
        logging.debug("wtf_url= "+wtf_url)
        html = self.req.Get("http://course.ucas.ac.cn/portal/tool-reset/{0}/?panel=Main".format(wtf_url))
        html = unescape(html.decode('utf-8'))
        #logging.debug(html)

        title = get_revalue(html, r'<img src =.*?/>([\s\S]+?)</h3>', 'get title error', 1).strip().replace(' ','_')

        logging.debug(title)

        folders = [x for x in re.findall(r'onclick="javascript[\s\S]+?submit', html) if 'doNavigate' in x]
        folders = [re.findall(r'group/\d+/[\s\S]+?/', x) for x in folders][1:]
        folders = ['/'+x[0] for x in folders]
        #print folders

        res = re.findall(r'http://course.ucas.ac.cn/access/content/group/[^"]+', html)
        res = [x[:-1] if x.endswith(";") else x for x in res]
        res = list(set(res))
        # logging.debug(html)
        self.download(title, res)


        for folder in folders:
            postData = {'source': 0,
                'collectionId': folder,
                'criteria':'title',
                'sakai_action': 'doNavigate'}
            content = self.req.Post("http://course.ucas.ac.cn/portal/tool/{0}/?panel=Main".format(wtf_url), postData)
            tmp = re.findall(r'http://course.ucas.ac.cn/access/content/group/[^"]+', content.decode('utf-8'))
            tmp = list(set(tmp))
            name = get_revalue(folder, r'([^/]+?)/$', 'folder error', 1).replace(' ', '_')
            #print name
            self.download(os.path.join(title,name), tmp)

        logging.debug(str(res))

    def download(self, title, res):
        import os
        print(('Linking' + '  ' + title))
        logging.info('linking... ' + title)
        if not os.path.exists(self.pwd):
            os.makedirs(self.pwd)
        _pwd = os.path.join(self.pwd, title)
        if not os.path.exists(_pwd):
            os.makedirs(_pwd)
        for f in res:
            name = get_revalue(f, r'([^/]+?)$', 'get name error', 1).replace(' ', '_')

            if name.__contains__('copyrightAlertWindow'):
                f = re.findall("http://course.ucas.ac.cn/access/content/group/[^']+", f)[0]
                name = get_revalue(f, r'([^/]+?)$', 'get name error', 1).replace(' ', '_')
                content = self.req.Get(f)
                #logging.debug(content)
                f = get_revalue(content, r'a href="(.+?)"', 'get wotongyi error', 1)
                #print  title + ' has contents which is protected by COPYRIGHT, failed to download'

            __pwd = os.path.join(_pwd, name)
            if (not force_update_flag) and check_existed(__pwd):
                print(('skip' + '  ' + name + ' already exists, skip'))
                logging.info( name + ' already exists, skip')
                continue

            #print 'downloading ' + name
            logging.info('downloading ' + name)
            self.req.Download(f, __pwd)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hf', ['help','force-update'])
        for name, value in opts:
            if name in ("-h","--help"):
                usage()
                pause()
                sys.exit()
            if name in ("-f","--force-update"):
                force_update_flag = True
    except getopt.GetoptError as err:
        print((str(err)))
        usage()
        pause()
        sys.exit(2)

    c = Course()
    c.login()
    pause()



