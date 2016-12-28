'''
Created on Jan 29, 2016

@author: wlerin
'''
from bs4 import BeautifulSoup
import json
import requests
import os
import sys
import datetime
import re
from dateutil import parser as date_parser
from collections import OrderedDict
from collections import namedtuple
from social48config import CONFIG

# ROOT_URL = 'http://ameblo.jp/'
PAGE_URL = 'page-{num:d}.html'
ROOT_DIR = CONFIG['root_directory'] + '/services/ameblo'
SERVICE  = 'ameblo'
HTML_PARSER = 'lxml'

   

class AmebloEntry(object):
    # contains:
    # date
    # title
    # url
    # contents
    # media    
    def __init__(self, date=None, title=None, url=None, theme=None, theme_url=None,
                 contents=None, media=None):
        self._date = date
        self._title = title
        self._url = url
        self._theme = theme
        self._theme_url = theme_url
        self._contents = contents
        self._media = media
    
    @property
    def date(self):
        return self._date
    
    @date.setter
    def date(self, new_date):
        #TODO: verify date, title, etc.
        # and do some parsing for contents/media? maybe save media here?
        self._date = new_date
        return self._date
    
    @property
    def title(self):
        return self._title
    
    @title.setter
    def title(self, new_title):
        self._title = new_title
        return self._title
        
    @property
    def url(self):
        return self._url
    
    @url.setter
    def url(self, new_url):
        self._url = new_url
        return self._url
        
    @property
    def theme(self):
        return self._theme
    
    @theme.setter
    def theme(self, new_theme):
        self._theme = new_theme
        return self._theme
    
    @property
    def theme_url(self):
        return self._theme_url
    
    @theme_url.setter
    def theme_url(self, new_theme_url):
        self._theme_url = new_theme_url
        return self._theme_url
    
    @property
    def contents(self):
        return self._contents
    
    @contents.setter
    def contents(self, new_contents):
        self._contents = new_contents
        return self._contents
        
    @property
    def media(self):
        return self._media
    
    @media.setter
    def media(self, new_media):
        self._media = new_media
        return self._media
    
    @property
    def month(self):
        return self.date[:7]

    def save_media(self, outdir):
        os.makedirs(outdir + '/' + self.month, exist_ok=True)
        base_filename = '/' + self.month + '/' + 'ameblo {date}_{count:02d}.{ext}'
        
        count = 1
        # max_count = len(media_list)
        for item in self.media:
            url = item['img_url']
            ext = url.rsplit('.', 1)[1]
            filename = base_filename.format(date=self.date.replace(':', ''), count=count, ext=ext)
            path = outdir + filename
            if download_url_to_file(url, path):
                item['img_file'] = filename
            count +=1

    def to_dict(self):
        post_order = ['date', 'title', 'url', 'theme', 'theme_url', 'contents', 'media']
        return OrderedDict((key, self.__dict__['_' + key]) for key in post_order if '_'+ key in self.__dict__)


class AmebloStyleBase(object):
    '''
    '''
    jpndate_format = '%Y年%m月%d日 %H時%M分%S秒'
    remove_weekday_pttn = re.compile(r'(?P<date>[^\(]+)\([^\)]*\) (?P<time>.*)')
    date_format    = '%Y-%m-%d %H:%M:%S'
    style_ref = {'official': {'last':       'a.lastPage',
                              'entry':      'div.entry',
                              'time':       'span.date',
                              'title':      'h3.title a',
                              'theme':      'span.theme a',
                              'body':       'div.subContentsInner'},
                 'new':      {'last':       'a.pagingNext',
                              'entry':      'div.skinArticle',
                              'time':       'span.articleTime time',
                              'title':      'div.skinArticleHeader a',
                              'theme':      'div.articleTheme',
                              'body':       'div.articleText'},
                 'uranus':   {'last':       'a.ga-pagingTopNextTop',
                              'entry':      'div.skin-entryInner',
                              'time':       'p.skin-entryPubdate time',
                              'title':      'h2.skin-entryTitle a',
                              'theme':      'dl.skin-entryThemes a',
                              'body':       'div.skin-entryBody'}}
    
    StyleDict = namedtuple('StyleDict', style_ref['official'].keys())
    
    
    def __init__(self, style_name='official'):
        self.selector = self.StyleDict(*self.style_ref[style_name].values())

    @property
    def _is_style(self):
        return True
    
    @staticmethod
    def is_style_match(page):
        return False
    
    def is_last_page(self, page):
        if not page.select(self.selector.last):
            return True
        else:
            return False
    
    def parse_entries(self, page):
        entries = page.select(self.selector.entry)
        for entry in entries:
            yield self.parse_post(entry)
    
    def parse_post(self, entry):
        """
        Genericised post parser
        """
        post = AmebloEntry()
        post.date = self.parse_date(entry.select_one(self.selector.time))
        
        title = entry.select_one(self.selector.title)
        post.title = title.text
        post.url   = title['href']
        
        theme = entry.select_one(self.selector.theme)
        if theme:
            post.theme = theme.text
            post.theme_url = theme['href']
        else:
            post.theme = post.theme_url = ''
        
        raw_contents = entry.select_one(self.selector.body)
        
        post.contents, post.media = self.parse_contents(raw_contents)
        
        return post
    
    def parse_contents(self, entry):
        def format_contents():
            contents = entry.prettify(formatter="minimal")
            return contents
        
        contents = format_contents()
        
        media = self.parse_media(entry.select('a.detailOn'))

        return contents, media
    
    def parse_media(self, media_list):
        media = []
        for item in media_list:
            new_item = {}
            try:
                new_item['id'] = item['id']
            # in some pages (mid-december 2015 akb48cafe was the first noticed)
            # id is on the img tag rather than the a tag
            except KeyError:
                if 'id' in item.img:
                    new_item['id'] = item.img['id']
                # and then there are others where there doesn't seem to *be* an id
                else:
                    new_item['id'] = ""

            new_item['album_url'] = item['href']
            try:
                new_item['img_url']   = self._fix_photo_link(item.img['src'])
            except TypeError:
                # deleted or moved the image but left the link in place
                continue
            media.append(new_item)
        return media
    
    def _fix_photo_link(self, photo_url):
        split_url = photo_url.split('/')
        
        if split_url[-1].startswith('t'):
            split_url[-1] = 'o' + split_url[-1].split('_')[-1]

        return '/'.join(split_url)

class AmebloStyleOfficial(AmebloStyleBase):
    def __init__(self):
        AmebloStyleBase.__init__(self, 'official')
        
    @staticmethod
    def is_style_match(page):
        if page.select('div.entry'):
            return True
        else:
            return False

    def parse_date(self, src_date):
        return src_date.text


class AmebloStyleNew(AmebloStyleBase):
    def __init__(self):
        AmebloStyleBase.__init__(self, 'new')

    @staticmethod
    def is_style_match(page):
        if page.select('div.skinArticle'):
            return True
        else:
            return False
    
    def parse_date(self, time_span):
        # date is in YYYY-MM-DD format
        if time_span['datetime'] in time_span.text:
            return time_span.text
        elif '年' in time_span.text:
            # remove day of the week
            jpn_date = ' '.join(re.match(self.remove_weekday_pttn, time_span.text).groups())
            new_date = datetime.datetime.strptime(jpn_date, self.jpndate_format)
            return new_date.strftime(self.date_format)
        else:
            # can set timezone using a default datetime object, but this is probably unnecessary
            # Wait. Why on earth am I not just returning datetime? ah because i want the time of day...
            # but chances are if we reach this point there is no time. meh.
            # return time_span['datetime']
            new_date = date_parser.parse(time_span.text)
            return new_date.strftime(self.date_format)
        # TODO: catch other date formats
        # TODO: check whether 年 dates are always correctly formatted

    # TODO: filter out the excess divvery in post contents?

class AmebloStyleUranus(AmebloStyleBase):
    def __init__(self):
        AmebloStyleBase.__init__(self, 'uranus')
    
    @staticmethod
    def is_style_match(page):
        if page.select('div.skin-entryInner'):
            return True
        else:
            return False
    
    
    def parse_date(self, src_date):
        new_date = src_date.text
        assert src_date['datetime'] in new_date
        return new_date


class AmebloWrapper(object):
    STYLES = [AmebloStyleOfficial, AmebloStyleNew, AmebloStyleUranus]
    
    def __init__(self, url=None, style=None, end_date=None):
        # use a property instead?
        if end_date:
            self.end_date = end_date
        else:
            self.end_date = None

        self.style = style

        if url:
            self.page = url
        else:
            self.page = None
            
    def guess_style(self):
        for style in self.STYLES:
            if style.is_style_match(self.page):
                self.style = style()
                break
    
    @property
    def page(self):
        return self._page
    
    @page.setter
    def page(self, url):
        if url == None:
            self._page = None
        else:
            self._load_page(url)
            
            if self.style == None:
                self.guess_style()

    def _load_page(self, url):
        r = requests.get(url)
        if r.status_code == 200:
            self._page = BeautifulSoup(r.text, 'lxml')
        else:
            #TODO: handle failed read
            r.raise_for_status()

    def is_last_page(self):
        return self.style.is_last_page(self.page)
    
    @property
    def entries(self):
        return self.style.parse_entries(self.page)


def rip_ameblo(member):
    print("Ripping {}'s Ameba Blog".format(member['engName']))
    base_url = member[SERVICE]['webUrl']
    filename = member[SERVICE]['handle']
    
    if member['type'] == 'member':
        subfolder = member['group']
    else: subfolder = member['type']

    outdir = '{}/{}/{}'.format(ROOT_DIR, subfolder, filename)
    datafile = '{}/{}_{}.json'.format(outdir, SERVICE, filename)
    
    def create_new_member(source):
        m_data = {'info': {}, 'posts': [], 'emotes': {}}
        for key in ('engName', 'engNick', 'jpnName', 'jpnNick', 'jpnNameKana'):
            m_data['info'][key] = source[key]
        m_data['info']['{}Id'.format(SERVICE)] = source[SERVICE]['apiId']
        m_data['info']['updated'] = "2006-01-01 00:00:00"
        return m_data

    def collected(entry, info): 
        if info['lastEntry'] == entry.url:
            return True
        if entry.date < info['updated']:
            return True
        else:
            return False

    if os.path.isfile(datafile):
        with open(datafile, mode='r', encoding='utf8') as src:
            data = json.load(src)
        backupfile = datafile + '.backup'
        if os.path.isfile(backupfile):
            os.replace(backupfile, backupfile + '2')
        os.replace(datafile, backupfile)
    # restore from most recent backup, e.g. after a failed run
    elif os.path.isfile(datafile + '.backup'):
        with open(datafile + '.backup', mode='r', encoding='utf8') as src:
            data = json.load(src)
    else:
        # data contains the following: posts, feed
        # posts are the items returned by activities, feed may or may not be necessary
        data = create_new_member(member)
        os.makedirs('{}'.format(outdir), exist_ok=True)
        data['info']['lastEntry'] = ''

    # TODO: move this to the end once all existing records are fixed.
    if data['posts']:
        data['info']['updated'] = data['posts'][-1]['date']
        data['info']['lastEntry'] = data['posts'][-1]['url']
    wrapper = AmebloWrapper()
    # loop
    # start at the first page, keep going until either a) you reach the end, or b) post date matches info.updated
    page_num = 1
    last_date = None
    bContinue = True
    
    while bContinue:
        full_url = '{}/{}'.format(base_url.strip('/'), PAGE_URL.format(num=page_num))
        
        wrapper.page = full_url
        page_num +=1
                
        # some blog have more than one entry per page
        for entry in wrapper.entries:
            try:
                if collected(entry, data['info']):
                    bContinue = False
                    break
            except TypeError as e:
                print("Problem on page {}: {}".format(full_url, e))
            if last_date:
                if last_date[:7] > entry.date[:7]:
                    print('Starting {}'.format(entry.date[:7]))
            
            last_date = entry.date
            # prepare media files
            entry.save_media(outdir)
            
            data['posts'].append(entry.to_dict())
        
        if wrapper.is_last_page():
            break
    
    data['posts'] = sorted(data['posts'], key=lambda post: post['date'])
    
    print("Finished scraping {}'s Ameba Blog, beginning output".format(member['engName']))
    try:
        with open(datafile, mode='w', encoding='utf8') as outfp:
            json.dump(data, outfp, ensure_ascii=False, indent=2)
    except TypeError as e:
        with open('ameblo_errors.txt', mode='w', encoding='utf8') as outfp:
            outfp.write(str(data))
        raise

def download_url_to_file(url, path, overwrite = False):
    if not overwrite and os.path.isfile(path):
        return True
    # TODO: check for problems
       
    r = requests.get(url, stream=True)
    with open(path, 'wb') as outfp:
        for chunk in r.iter_content(chunk_size=2048):
            outfp.write(chunk)
    r.close()
    
    return True

def find_blog(target, blogs):
    '''Returns a list of talks matching the provided criteria'''
    return [e for e in blogs if e['ameblo']['handle'].lower() == target.lower()] + \
    [e for e in blogs if e['engNick'].lower() == target.lower()] + \
    [e for e in blogs if e['engName'].lower()  == target.lower()] + \
    [e for e in blogs if e['jpnName']  == target]


def search_blog(blog_file, *search_terms):
    """
    Extremely simple search, finds every entry with all search terms,
    prints results to a file
    """
    # TODO: make a blog object to handle this
    with open(blog_file, encoding='utf8') as infp:
        blog_data = json.load(infp)

    found = []
    for post in blog_data['posts']:
        # 'AND' check for false
        # 'OR' check for true
        # only 'AND' is implemented right now
        if False not in [term in post['contents'] for term in search_terms]:
            found.append(post)

    print('Found {} results'.format(len(found)))
    with open(ROOT_DIR + '/search_results.json', mode='w', encoding='utf8') as outfp:
        json.dump(found, outfp, ensure_ascii=False, indent=2)
    with open(ROOT_DIR + '/search_results.txt', mode='w', encoding='utf8') as outfp:
        for post in found:
            outfp.write('{}\n{}\n{}\n'.format(post['title'], post['date'], post['url']))
            print(BeautifulSoup(post['contents'], 'lxml').text, file=outfp)

def main():
    with open(ROOT_DIR + '/ameblo_index.json', mode='r', encoding='utf8') as infp:
        blogs = json.load(infp)
    
    if len(sys.argv) < 2:
        for blog in blogs:
            rip_ameblo(blog)
        return
    else:
        goal = sys.argv[1]

    if 'search' == goal:
        if len(sys.argv) < 4:
            print('Syntax: python ameblog.py search <target> <terms>')
            return
        else:
            # TODO: make options more intelligent, allow other kinds of search
            target = sys.argv[2]
            terms = sys.argv[3:]

            # TODO: get a unicode-capable commandline lol
            terms = ['武藤十夢', '不参加']
            
            try:
                blog = find_blog(target, blogs)[0]
            except IndexError:
                print('Blog not found')
                return

            blog_file = '{0}/{1}/{2}/ameblo_{2}.json'.format(ROOT_DIR, 
                                                             blog['group'], 
                                                             blog['ameblo']['handle'])
            search_blog(blog_file, *terms)


if __name__ == '__main__':
    main()
    
