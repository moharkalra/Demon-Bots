#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import codecs
import configparser
import errno
import glob
from operator import itemgetter
import json
import logging.config
import hashlib
import os
import pickle
import re
import socket
import sys
import textwrap
import time
from socket import *
from re import *
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import warnings
import threading
import concurrent.futures
import requests
import requests.packages.urllib3.util.connection as urllib3_connection
import tqdm
import aiohttp
import asyncio
from random import seed
from random import randint
from PIL import Image, ImageSequence
import numpy as np
import cv2
import matplotlib.pyplot as plt


from instagram_scraper.constants import *



class InstagramScraper(object):
    """InstagramScraper scrapes and downloads an instagram user's photos and videos"""

    def __init__(self, **kwargs):
        default_attr = dict(username='', usernames=[], filename=None,
                            login_user="USERNAME", login_pass="PASSWORD",
                            followings_input=True, followings_output='profiles.txt',
                            destination='tmp', logger=None, retain_username=False, interactive=False,
                            quiet=False, maximum=0, media_metadata=False, profile_metadata=False, latest=False,
                            latest_stamps=False, cookiejar=None, filter_location=None, filter_locations=None,
                            media_types=['image'],
                            tag=False, location=False, search_location=False, comments=False,
                            verbose=0, include_location=False, filter=None, proxies={}, no_check_certificate=False,
                                                        template='{urlname}', log_destination='')

        allowed_attr = list(default_attr.keys())
        default_attr.update(kwargs)

        for key in default_attr:
            if key in allowed_attr:
                self.__dict__[key] = default_attr.get(key)

        # story media type means story-image & story-video
        if 'story' in self.media_types:
            self.media_types.remove('story')
            if 'story-image' not in self.media_types:
                self.media_types.append('story-image')


        # Read latest_stamps file with ConfigParser
        self.latest_stamps_parser = None
        if self.latest_stamps:
            parser = configparser.ConfigParser()
            parser.read(self.latest_stamps)
            self.latest_stamps_parser = parser
            # If we have a latest_stamps file, latest must be true as it's the common flag
            self.latest = True

        # Set up a logger
        if self.logger is None:
            self.logger = InstagramScraper.get_logger(level=logging.DEBUG, dest=default_attr.get('log_destination'), verbose=default_attr.get('verbose'))

        self.posts = []
        self.stories = []

        self.session = requests.Session()
        if self.no_check_certificate:
            self.session.verify = False

        try:
            if self.proxies and type(self.proxies) == str:
                self.session.proxies = json.loads(self.proxies)
        except ValueError:
            self.logger.error("Check is valid json type.")
            raise

        self.session.headers = {'user-agent': CHROME_WIN_UA}
        if self.cookiejar and os.path.exists(self.cookiejar):
            with open(self.cookiejar, 'rb') as f:
                self.session.cookies.update(pickle.load(f))
        self.session.cookies.set('ig_pr', '1')
        self.rhx_gis = ""

        self.cookies = None
        self.authenticated = False
        self.logged_in = False
        self.last_scraped_filemtime = 0
        self.initial_scraped_filemtime = 0
        if default_attr['filter']:
            self.filter = list(self.filter)
        self.quit = False

    def sleep(self, secs):
        min_delay = 1
        for _ in range(secs // min_delay):
            time.sleep(min_delay)
            if self.quit:
                return
        time.sleep(secs % min_delay)



    def safe_get(self, *args, **kwargs):
        # out of the box solution
        # session.mount('https://', HTTPAdapter(max_retries=...))
        # only covers failed DNS lookups, socket connections and connection timeouts
        # It doesnt work when server terminate connection while response is downloaded
        retry = 0
        retry_delay = RETRY_DELAY
        while True:
            if self.quit:
                return
            # try:
            response = self.session.get(timeout=CONNECT_TIMEOUT, cookies=self.cookies, *args, **kwargs)
            if response.status_code == 404:
                return
            response.raise_for_status()
            content_length = response.headers.get('Content-Length')
            if content_length is not None and len(response.content) != int(content_length):
                #if content_length is None we repeat anyway to get size and be confident
                raise PartialContentException('Partial response')
            return response


    def get_json(self, *args, **kwargs):
        """Retrieve text from url. Return text as string or None if no data present """
        resp = self.safe_get(*args, **kwargs)
        # print(resp)
        # print(resp.text)
        if resp is not None:
            return resp.text



    def authenticate_with_login(self):
        """Logs in to instagram."""
        self.session.headers.update({'Referer': BASE_URL, 'user-agent': STORIES_UA})
        req = self.session.get(BASE_URL)

        self.session.headers.update({'X-CSRFToken': req.cookies['csrftoken']})

        login_data = {'username': self.login_user, 'password': self.login_pass}
        login = self.session.post(LOGIN_URL, data=login_data, allow_redirects=True)
        self.session.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        self.cookies = login.cookies
        login_text = json.loads(login.text)

        if login_text.get('authenticated') and login.status_code == 200:
            self.authenticated = True
            self.logged_in = True
            self.session.headers.update({'user-agent': CHROME_WIN_UA})
            self.rhx_gis = ""
        else:
            self.logger.error('Login failed for ' + self.login_user)

            if 'checkpoint_url' in login_text:
                checkpoint_url = login_text.get('checkpoint_url')
                self.logger.error('Please verify your account at ' + BASE_URL[0:-1] + checkpoint_url)

                if self.interactive is True:
                    self.login_challenge(checkpoint_url)
            elif 'errors' in login_text:
                for count, error in enumerate(login_text['errors'].get('error')):
                    count += 1
                    self.logger.debug('Session error %(count)s: "%(error)s"' % locals())
            else:
                self.logger.error(json.dumps(login_text))
            sys.exit(1)

    def login_challenge(self, checkpoint_url):
        self.session.headers.update({'Referer': BASE_URL})
        req = self.session.get(BASE_URL[:-1] + checkpoint_url)
        self.session.headers.update({'X-CSRFToken': req.cookies['csrftoken'], 'X-Instagram-AJAX': '1'})

        self.session.headers.update({'Referer': BASE_URL[:-1] + checkpoint_url})
        mode = int(input('Choose a challenge mode (0 - SMS, 1 - Email): '))
        challenge_data = {'choice': mode}
        challenge = self.session.post(BASE_URL[:-1] + checkpoint_url, data=challenge_data, allow_redirects=True)
        self.session.headers.update({'X-CSRFToken': challenge.cookies['csrftoken'], 'X-Instagram-AJAX': '1'})

        code = int(input('Enter code received: '))
        code_data = {'security_code': code}
        code = self.session.post(BASE_URL[:-1] + checkpoint_url, data=code_data, allow_redirects=True)
        self.session.headers.update({'X-CSRFToken': code.cookies['csrftoken']})
        self.cookies = code.cookies
        code_text = json.loads(code.text)

        if code_text.get('status') == 'ok':
            self.authenticated = True
            self.logged_in = True
        elif 'errors' in code.text:
            for count, error in enumerate(code_text['challenge']['errors']):
                count += 1
                self.logger.error('Session error %(count)s: "%(error)s"' % locals())
        else:
            self.logger.error(json.dumps(code_text))

    def logout(self):
        """Logs out of instagram."""
        if self.logged_in:
            try:
                logout_data = {'csrfmiddlewaretoken': self.cookies['csrftoken']}
                self.session.post(LOGOUT_URL, data=logout_data)
                self.authenticated = False
                self.logged_in = False
            except requests.exceptions.RequestException:
                self.logger.warning('Failed to log out ' + self.login_user)

    def get_dst_dir(self, username):
        """Gets the destination directory and last scraped file time."""
        if self.destination == './':
            dst = './' + username
        else:
            if self.retain_username:
                dst = self.destination + '/' + username
            else:
                dst = self.destination

        # Resolve last scraped filetime
        if self.latest_stamps_parser:
            self.last_scraped_filemtime = self.get_last_scraped_timestamp(username)
            self.initial_scraped_filemtime = self.last_scraped_filemtime
        elif os.path.isdir(dst):
            self.last_scraped_filemtime = self.get_last_scraped_filemtime(dst)

        return dst

    def make_dir(self, dst):
        try:
            os.makedirs(dst)
        except OSError as err:
            if err.errno == errno.EEXIST and os.path.isdir(dst):
                # Directory already exists
                pass
            else:
                # Target dir exists as a file, or a different error
                raise

    def get_last_scraped_timestamp(self, username):
        if self.latest_stamps_parser:
            try:
                return self.latest_stamps_parser.getint(LATEST_STAMPS_USER_SECTION, username)
            except configparser.Error:
                pass
        return 0

    def set_last_scraped_timestamp(self, username, timestamp):
        if self.latest_stamps_parser:
            if not self.latest_stamps_parser.has_section(LATEST_STAMPS_USER_SECTION):
                self.latest_stamps_parser.add_section(LATEST_STAMPS_USER_SECTION)
            self.latest_stamps_parser.set(LATEST_STAMPS_USER_SECTION, username, str(timestamp))
            with open(self.latest_stamps, 'w') as f:
                self.latest_stamps_parser.write(f)

    def get_last_scraped_filemtime(self, dst):
        """Stores the last modified time of newest file in a directory."""
        list_of_files = []
        file_types = ('*.jpg', '*.mp4')

        for type in file_types:
            list_of_files.extend(glob.glob(dst + '/' + type))

        if list_of_files:
            latest_file = max(list_of_files, key=os.path.getmtime)
            return int(os.path.getmtime(latest_file))
        return 0

    def query_followings_gen(self, username, end_cursor=''):
        """Generator for followings."""
        user = self.get_shared_data_userinfo(username)
        id = user['id']
        followings, end_cursor = self.__query_followings(id, end_cursor)


        if followings:
            while True:
                for following in followings:

                    yield following
                if end_cursor:
                    followings, end_cursor = self.__query_followings(id, end_cursor)
                else:
                    return

    def __query_followings(self, id, end_cursor=''):
        params = QUERY_FOLLOWINGS_VARS.format(id, end_cursor)
        resp = self.get_json(QUERY_FOLLOWINGS.format(params))

        if resp is not None:
            payload = json.loads(resp)['data']['user']['edge_follow']
            if payload:
                end_cursor = payload['page_info']['end_cursor']
                followings = []
                names = []
                for node in payload['edges']:
                    flag = self.checkFollower(node)
                    if (flag):
                        followings.append(node['node']['id'])
                        names.append(node['node']['username'])

                return followings, end_cursor
        return None, None



    def checkFollower(self, node):
        img_count = 0
        item = node

        item['urls'] = [node['node']['profile_pic_url']]
        files, count = self.download(item, img_count, True, 'tmp')
        print(item['node']['username'])
        os.remove(files)
        if count > img_count:
            return True
        else:
            return False



    def _get_nodes(self, container):
        return [self.augment_node(node['node']) for node in container['edges']]

    def augment_node(self, node):

        print("augmenting")
        details = None
        # if self.include_location and 'location' not in node:
        #     details = self.__get_media_details(node['shortcode'])
        #     node['location'] = details.get('location') if details else None
        #
        if 'urls' not in node:
            r = node['thumbnail_resources'][0]
            node['urls'] = []
            node['urls'] = [self.get_original_image(r['src'])]


        return node
    async def scrape(self, executor=concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)):
        """Crawls through and downloads user's media"""
        self.session.headers.update({'user-agent': STORIES_UA})
        print(time.time())
        tasks = []
        for username in self.usernames:
            self.posts = []
            self.stories = []
            future_to_item = {}

            dst = "tmp"

            # Get the user metadata.



            self.rhx_gis = ""



            if self.logged_in:
                task = asyncio.create_task(self.get_media(dst, username))
                tasks.append(task)
            await asyncio.gather(*tasks)
            self.createImage()


    def appendToImage(self, filepath):
        global toSend
        toSend.append(filepath)


    def createImage(self):
        img = Image.new('RGBA', (300, 300), (255, 0, 0, 0))
        counter = 1
        global ready
        global toSend
        lenList = len(toSend)
        for filepath in toSend:
            addon = Image.open(filepath)
            addon.thumbnail((100, 100))
            if counter==1:
                pos = (0, 0)
            elif counter==2:
                pos = (100, 100)
            elif counter==3:
                pos = (200, 200)
            elif counter==4:
                pos = (0, 100)
            elif counter==5:
                pos = (100, 0)
            elif counter==6:
                pos = (100, 200)
            elif counter==7:
                pos = (200, 0)
            elif counter==8:
                pos = (200, 100)
            elif counter==9:
                pos = (0, 200)
            counter = counter+1
            img.paste(addon, pos)


        if(lenList==9):
            img.save('background.png')
            ready = True
        elif(lenList==3):
            img.save('backgroun1.png')
        elif(lenList==6):
            img.save('backgroun2.png')


    async def get_media(self, dst, username):


        iter = 0;
        rand = randint(0,9);
        print("querying")

        items = self.query_media_gen(username)
        reject_paths = []
        printpaths = []
        img_count = 0
        for item in items:
            if img_count == 3:
                break;
            else:
                item['id']=username;
                item['urls'] = [item['urls'][0]];
                old_count = img_count
                files, img_count = self.download(item, img_count, False, dst);
                if img_count == old_count:
                    reject_paths.append(files)
                else:
                    self.appendToImage(files)
                    printpaths.append(files)

        if img_count<3:
            for filename in os.listdir('tmp'):
                filename = 'tmp\\' + filename
                if img_count == 3:
                    break;
                elif filename in reject_paths:
                    self.appendToImage(filename)
                    printpaths.append(filename)
                    img_count = img_count + 1
        print(printpaths)




    def get_shared_data_userinfo(self, username=''):
        """Fetches the user's metadata."""
        resp = self.get_json(BASE_URL + username)

        userinfo = None

        if resp is not None:
            try:
                if "window._sharedData = " in resp:
                    shared_data = resp.split("window._sharedData = ")[1].split(";</script>")[0]
                    if shared_data:
                        userinfo = self.deep_get(json.loads(shared_data), 'entry_data.ProfilePage[0].graphql.user')

                if "window.__additionalDataLoaded(" in resp and not userinfo:
                    parameters = resp.split("window.__additionalDataLoaded(")[1].split(");</script>")[0]
                    if parameters and "," in parameters:
                        shared_data = parameters.split(",", 1)[1]
                        if shared_data:
                            userinfo = self.deep_get(json.loads(shared_data), 'graphql.user')
            except (TypeError, KeyError, IndexError):
                pass

        return userinfo



    def query_media_gen(self, user_id, end_cursor=''):
        """Generator for media."""
        print("generating")
        media, end_cursor = self.__query_media(user_id, end_cursor)

        print("generated")

        item = media[0:5]

        return item;

    def __query_media(self, id, end_cursor=''):
        params = QUERY_MEDIA_VARS.format(id, end_cursor)
        self.update_ig_gis_header(params)

        resp = self.get_json(QUERY_MEDIA.format(params))



        if resp is not None:
            payload = json.loads(resp)['data']['user']

            if payload:
                container = payload['edge_owner_to_timeline_media']
                print("forming nodes")
                nodes = self._get_nodes(container)
                end_cursor = container['page_info']['end_cursor']
                return nodes, end_cursor

        return None, None

    def get_ig_gis(self, rhx_gis, params):
        data = rhx_gis + ":" + params
        if sys.version_info.major >= 3:
            return hashlib.md5(data.encode('utf-8')).hexdigest()
        else:
            return hashlib.md5(data).hexdigest()

    def update_ig_gis_header(self, params):
        self.session.headers.update({
            'x-instagram-gis': self.get_ig_gis(
                self.rhx_gis,
                params
            )
        })

    def has_selected_media_types(self, item):
        filetypes = {'jpg': 0, 'mp4': 0}

        for url in item['urls']:
            ext = self.__get_file_ext(url)
            if ext not in filetypes:
                filetypes[ext] = 0
            filetypes[ext] += 1

        if ('image' in self.media_types and filetypes['jpg'] > 0):
            return True

        return False





    def get_original_image(self, url):
        """Gets the full-size image from the specified url."""
        # these path parts somehow prevent us from changing the rest of media url
        #url = re.sub(r'/vp/[0-9A-Fa-f]{32}/[0-9A-Fa-f]{8}/', '/', url)
        # remove dimensions to get largest image
        #url = re.sub(r'/[sp]\d{3,}x\d{3,}/', '/', url)
        # get non-square image if one exists
        #url = re.sub(r'/c\d{1,}.\d{1,}.\d{1,}.\d{1,}/', '/', url)

        return url



    def download(self, item, img_count, profile, save_dir='./'):
        """Downloads the media file."""

        if self.filter_locations:
            save_dir = os.path.join(save_dir, self.get_key_from_value(self.filter_locations, item["location"]["id"]))

        files_path = ''

        for full_url, base_name in self.templatefilename(item):
            url = full_url.split('?')[0] #try the static url first, stripping parameters

            file_path = os.path.join(save_dir, base_name)

            if not os.path.exists(os.path.dirname(file_path)):
                self.make_dir(os.path.dirname(file_path))

            if not os.path.isfile(file_path):
                headers = {'Host': urlparse(url).hostname}

                part_file = file_path + '.part'
                downloaded = 0
                total_length = None
                with open(part_file, 'wb') as media_file:
                    try:
                        retry = 0
                        retry_delay = RETRY_DELAY
                        while (True):
                            if self.quit:
                                return
                            try:
                                downloaded_before = downloaded
                                headers['Range'] = 'bytes={0}-'.format(downloaded_before)

                                with self.session.get(url, cookies=self.cookies, headers=headers, stream=True, timeout=CONNECT_TIMEOUT) as response:
                                    if response.status_code == 404 or response.status_code == 410:
                                        #on 410 error see issue #343
                                        #instagram don't lie on this
                                        break
                                    if response.status_code == 403 and url != full_url:
                                        #see issue #254
                                        url = full_url
                                        continue
                                    response.raise_for_status()

                                    if response.status_code == 206:
                                        try:
                                            match = re.match(r'bytes (?P<first>\d+)-(?P<last>\d+)/(?P<size>\d+)', response.headers['Content-Range'])
                                            range_file_position = int(match.group('first'))
                                            if range_file_position != downloaded_before:
                                                raise Exception()
                                            total_length = int(match.group('size'))
                                            media_file.truncate(total_length)
                                        except:
                                            raise requests.exceptions.InvalidHeader('Invalid range response "{0}" for requested "{1}"'.format(
                                                response.headers.get('Content-Range'), headers.get('Range')))
                                    elif response.status_code == 200:
                                        if downloaded_before != 0:
                                            downloaded_before = 0
                                            downloaded = 0
                                            media_file.seek(0)
                                        content_length = response.headers.get('Content-Length')
                                        if content_length is None:
                                            self.logger.warning('No Content-Length in response, the file {0} may be partially downloaded'.format(base_name))
                                        else:
                                            total_length = int(content_length)
                                            media_file.truncate(total_length)
                                    else:
                                        raise PartialContentException('Wrong status code {0}', response.status_code)

                                    for chunk in response.iter_content(chunk_size=64*1024):
                                        if chunk:
                                            downloaded += len(chunk)
                                            media_file.write(chunk)
                                        if self.quit:
                                            return

                                if downloaded != total_length and total_length is not None:
                                    raise PartialContentException('Got first {0} bytes from {1}'.format(downloaded, total_length))

                                break

                            # In case of exception part_file is not removed on purpose,
                            # it is easier to exemine it later when analising logs.
                            # Please do not add os.remove here.
                            except (KeyboardInterrupt):
                                raise
                            except (requests.exceptions.RequestException, PartialContentException) as e:
                                media = url
                                if item['shortcode'] and item['shortcode'] != '':
                                    media += " from https://www.instagram.com/p/" + item['shortcode']
                                if downloaded - downloaded_before > 0:
                                    # if we got some data on this iteration do not count it as a failure
                                    self.logger.warning('Continue after exception {0} on {1}'.format(repr(e), media))
                                    retry = 0 # the next fail will be first in a row with no data
                                    continue
                                if retry < MAX_RETRIES:
                                    self.logger.warning('Retry after exception {0} on {1}'.format(repr(e), media))
                                    self.sleep(retry_delay)
                                    retry_delay = min( 2 * retry_delay, MAX_RETRY_DELAY )
                                    retry = retry + 1
                                    continue
                                else:
                                    keep_trying = self._retry_prompt(media, repr(e))
                                    if keep_trying == True:
                                        retry = 0
                                        continue
                                    elif keep_trying == False:
                                        break
                                raise
                    finally:
                        media_file.truncate(downloaded)

                if downloaded == total_length or total_length is None and downloaded > 100:
                    os.rename(part_file, file_path)
                    timestamp = self.__get_timestamp(item)
                    file_time = int(timestamp if timestamp else time.time())
                    os.utime(file_path, (file_time, file_time))

            files_path=file_path


            print(file_path)



            if(profile):
                img = cv2.imread(file_path)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                haar_cascade_face = cv2.CascadeClassifier('haarcascades/haarcascade_frontalface_default.xml')
                haar_cascade_face2 = cv2.CascadeClassifier('haarcascades/haarcascade_profileface.xml')
                haar_cascade_face3 = cv2.CascadeClassifier('haarcascades/haarcascade_upperbody.xml')
                haar_cascade_face4 = cv2.CascadeClassifier('haarcascades/haarcascade_fullbody.xml')
                faces_rects = haar_cascade_face.detectMultiScale(img, scaleFactor = 1.2, minNeighbors = 5);
                faces_rects2 = haar_cascade_face2.detectMultiScale(img, scaleFactor = 1.2, minNeighbors = 5);
                faces_rects3 = haar_cascade_face3.detectMultiScale(img, scaleFactor = 1.2, minNeighbors = 5);
                faces_rects4 = haar_cascade_face4.detectMultiScale(img, scaleFactor = 1.2, minNeighbors = 5);
                print(len(faces_rects) + len(faces_rects2) + len(faces_rects3) + len(faces_rects4))
                if (len(faces_rects) + len(faces_rects2) + len(faces_rects3) + len(faces_rects4))>0:
                    img_count = img_count+1

            else:
                img = Image.open(file_path)
                unique_colors = set()
                for i in range(img.size[0]):
                    for j in range(img.size[1]):
                        pixel = img.getpixel((i, j))
                        unique_colors.add(pixel)

                if len(unique_colors)>15000:
                    img_count = img_count+1
        print(time.time())
        return files_path, img_count

    def templatefilename(self, item):

        for url in item['urls']:
            filename, extension = os.path.splitext(os.path.split(url.split('?')[0])[1])
            try:
                template = self.template
                template_values = {
                                    'username' : item['id'],
                                   'urlname': filename,
                                    'shortcode': str(item['shortcode']),
                                    'mediatype' : item['__typename'][5:],
                                   'datetime': time.strftime('%Y%m%d %Hh%Mm%Ss',
                                                             time.localtime(self.__get_timestamp(item))),
                                   'date': time.strftime('%Y%m%d', time.localtime(self.__get_timestamp(item))),
                                   'year': time.strftime('%Y', time.localtime(self.__get_timestamp(item))),
                                   'month': time.strftime('%m', time.localtime(self.__get_timestamp(item))),
                                   'day': time.strftime('%d', time.localtime(self.__get_timestamp(item))),
                                   'h': time.strftime('%Hh', time.localtime(self.__get_timestamp(item))),
                                   'm': time.strftime('%Mm', time.localtime(self.__get_timestamp(item))),
                                   's': time.strftime('%Ss', time.localtime(self.__get_timestamp(item)))}

                customfilename = str(template.format(**template_values) + extension)
                yield url, customfilename
            except KeyError:
                customfilename = str(filename + extension)
                yield url, customfilename

    def is_new_media(self, item):
        """Returns True if the media is new."""
        if self.latest is False or self.last_scraped_filemtime == 0:
            return True

        current_timestamp = self.__get_timestamp(item)
        return current_timestamp > 0 and current_timestamp > self.last_scraped_filemtime

    @staticmethod
    def __get_timestamp(item):
        if item:
            for key in ['taken_at_timestamp', 'created_time', 'taken_at', 'date', 'published_time']:
                found = item.get(key, 0)
                try:
                    found = int(found)
                    if found > 1:  # >1 to ignore any boolean casts
                        return found
                except ValueError:
                    pass
        return 0

    @staticmethod
    def __get_file_ext(url):
        return os.path.splitext(urlparse(url).path)[1][1:].strip().lower()

    @staticmethod
    def __search(query):
        resp = requests.get(SEARCH_URL.format(query))
        return json.loads(resp.text)

    def search_locations(self):
        query = ' '.join(self.usernames)
        result = self.__search(query)

        if len(result['places']) == 0:
            raise ValueError("No locations found for query '{0}'".format(query))

        sorted_places = sorted(result['places'], key=itemgetter('position'))

        for item in sorted_places[0:5]:
            place = item['place']
            print('location-id: {0}, title: {1}, subtitle: {2}, city: {3}, lat: {4}, lng: {5}'.format(
                place['location']['pk'],
                place['title'],
                place['subtitle'],
                place['location']['city'],
                place['location'].get('lat'),
                place['location'].get('lng')
            ))

    def merge_json(self, data, dst='./'):
        if not os.path.exists(dst):
            self.save_json(data, dst)
        if data:
            merged = data
            with open(dst, 'rb') as f:
                key = list(merged.keys())[0]
                file_data = json.load(codecs.getreader('utf-8')(f))
                self.remove_duplicate_data(file_data[key])
                if key in file_data:
                    merged[key] = file_data[key]
            self.save_json(merged, dst)

    @staticmethod
    def remove_duplicate_data(file_data):
        unique_ids = set()
        file_data_ids = []
        for post in file_data:
            file_data_ids.append(post["id"])
        file_ids_copy = file_data_ids.copy()
        for id_ in file_ids_copy:
            if id_ in unique_ids:
                file_data_ids.pop(file_data_ids.index(id_))
            else:
                unique_ids.add(id_)

    @staticmethod
    def save_json(data, dst='./'):
        """Saves the data to a json file."""
        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))

        if data:
            output_list = {}
            if os.path.exists(dst):
                with open(dst, "rb") as f:
                    output_list.update(json.load(codecs.getreader('utf-8')(f)))

            with open(dst, 'wb') as f:
                output_list.update(data)
                json.dump(output_list, codecs.getwriter('utf-8')(f), indent=4, sort_keys=True, ensure_ascii=False)

    def _persist_metadata(self, dirname, filename):
        metadata_path = '{0}/{1}.json'.format(dirname, filename)
        if (self.media_metadata or self.comments or self.include_location):
            if self.posts:
                if self.latest:
                    self.merge_json({'GraphImages': self.posts}, metadata_path)
                else:
                    self.save_json({'GraphImages': self.posts}, metadata_path)

            if self.stories:
                if self.latest:
                    self.merge_json({'GraphStories': self.stories}, metadata_path)
                else:
                    self.save_json({'GraphStories': self.stories}, metadata_path)

    @staticmethod
    def get_logger(level=logging.DEBUG, dest='', verbose=0):
        """Returns a logger."""
        logger = logging.getLogger(__name__)

        dest +=  '/' if (dest !=  '') and dest[-1] != '/' else ''
        fh = logging.FileHandler(dest + 'instagram-scraper.log', 'w')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        fh.setLevel(level)
        logger.addHandler(fh)

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        sh_lvls = [logging.ERROR, logging.WARNING, logging.INFO]
        sh.setLevel(sh_lvls[verbose])
        logger.addHandler(sh)

        logger.setLevel(level)

        return logger

    @staticmethod
    def get_values_from_file(usernames_file):
        """Parses a file containing a list of usernames."""
        users = []

        try:
            with open(usernames_file) as user_file:
                for line in user_file.readlines():
                    # Find all usernames delimited by ,; or whitespace
                    users += re.findall(r'[^,;\s]+', line.split("#")[0])
        except IOError as err:
            raise ValueError('File not found ' + err)

        return users

    @staticmethod
    def get_locations_from_file(locations_file):
        """
        parse an ini like file with sections composed of headers, [location],
        and arguments that are location ids
        """
        locations={}
        with open(locations_file, 'r') as f_in:
            lines = filter(None, (line.rstrip() for line in f_in))
            for line in lines:
                match = re.search(r"\[(\w+)\]", line)
                if match:
                    current_group = match.group(1)
                    locations.setdefault(current_group, [])
                else:
                    if  not line.strip().startswith("#"):
                        try:
                            locations[current_group].append(line.strip())
                        except NameError:
                            print("Must Start File with A Heading Enclosed in []")
                            sys.exit(1)
        return locations

    @staticmethod
    def get_key_from_value(location_dict, value):
        """
        Determine if value exist inside dict and return its key, otherwise return None
        """
        for key, values in location_dict.items():
            if value in values:
                return key
        return None

    @staticmethod
    def parse_delimited_str(input):
        """Parse the string input as a list of delimited tokens."""
        return re.findall(r'[^,;\s]+', input)

    def deep_get(self, dict, path):
        def _split_indexes(key):
            split_array_index = re.compile(r'[.\[\]]+')  # ['foo', '0']
            return filter(None, split_array_index.split(key))

        ends_with_index = re.compile(r'\[(.*?)\]$')  # foo[0]

        keylist = path.split('.')

        val = dict

        for key in keylist:
            try:
                if ends_with_index.search(key):
                    for prop in _split_indexes(key):
                        if prop.isdigit():
                            val = val[int(prop)]
                        else:
                            val = val[prop]
                else:
                    val = val[key]
            except (KeyError, IndexError, TypeError):
                return None

        return val

    def save_cookies(self):
        if self.cookiejar:
            with open(self.cookiejar, 'wb') as f:
                pickle.dump(self.session.cookies, f)



def status():
    global redirectUrl

    global ready
    print(len(toSend))
    if ready:
        return "ready"
    elif len(toSend) >=3 and os.path.exists('backgroun2.png'):
        return "reload2"
    elif len(toSend) >=3 and os.path.exists('backgroun1.png'):
        return "reload1"
    else:
        return "not ready"


def ReqProcess(clientSocket, scraper, followers):
    global redirectUrl
    global toSend
    global ready
    while True:
        try:
            #if a message is received and it is not empty
            message = clientSocket.recv(1024).decode()
            if message:
                print("Message from client: ", message)
                #server name, filepath and http version are extracted from client request
                msg = message.split('/')
                msg = msg[1]
                print(msg)
                print(msg[0])
                if msg[0]=='b':
                    print(len(toSend))
                    print("delivering background")
                    filename = msg[0:14]
                    print(filename)
                    f = open(filename, 'rb')
                    resp = f.read()
                    response = "HTTP/1.1 200 OK\n"+"Access-Control-Allow-Origin: *\nContent-Length:" + str(len(resp)) + "\nContent-Type: image/png\nConnection: close\n"+"\n"
                    print(response)
                    clientSocket.send(response.encode())
                    clientSocket.send(resp)
                elif msg[0]=='&':
                    print("url received")
                    m = message.split('&', 1)
                    redirectUrl = m[1]
                    redirectUrl = redirectUrl.split(' ', 1)[0]

                    print(redirectUrl)
                elif msg[0]=='?':
                    print(len(toSend))
                    resp = status()
                    print(resp)
                    response = "HTTP/1.1 200 OK\n"+"Access-Control-Allow-Origin: *\nContent-Length:" + str(len(resp)) + "\nContent-Type: text/plain; charset=utf-8\nConnection: close\n"+"\n"+ resp + "\n"
                    print(response)
                    clientSocket.send(response.encode())
                elif msg[0]=='!':
                    print("loading")
                    selected = [];
                    print("followers queried")
                    while(len(selected)<3):
                        ind = randint(0, (len(followers)-1));
                        if not followers[ind] in selected:
                            selected.append(followers[ind]);
                    print(selected)
                    scraper.usernames = selected;
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                    asyncio.run(scraper.scrape());
                elif msg[0]=='@':
                    resp = redirectUrl
                    print(resp)
                    for filename in os.listdir('tmp'):
                        filepath = os.path.join('tmp', filename)
                        os.remove(filepath)
                    os.remove('background.png')
                    os.remove('backgroun1.png')
                    os.remove('backgroun2.png')
                    toSend = []
                    response = "HTTP/1.1 200 OK\n"+"Access-Control-Allow-Origin: *\nContent-Length:" + str(len(resp)) + "\nContent-Type: text/plain; charset=utf-8\nConnection: close\n"+"\n"+ resp + "\n"
                    redirectUrl = ""
                    ready = False
                    clientSocket.send(response.encode())
                clientSocket.close()

                print(" Client Connection closed")
            else:
                readable, writable, errorable = select([],[], [clientSocket])
                for s in errorable:
                    s.close()
                break
        except:
            #if the message has no content, connection to client is closed
            clientSocket.close()

            print("Client Connection closed")
            break



def main():
    # seed random number generator
    seed(time.time())
    parser = argparse.ArgumentParser(
        description="instagram-scraper scrapes and downloads an instagram user's photos and videos.",
        epilog=textwrap.dedent("""
        You can hide your credentials from the history, by reading your
        username from a local file:

        $ instagram-scraper @insta_args.txt user_to_scrape

        with insta_args.txt looking like this:
        -u=my_username
        -p=my_password

        You can add all arguments you want to that file, just remember to have
        one argument per line.

        Customize filename:
        by adding option --template or -T
        Default is: {urlname}
        And there are some option:
        {username}: Instagram user(s) to scrape.
        {shortcode}: post shortcode, but profile_pic and story are none.
        {urlname}: filename form url.
        {mediatype}: type of media.
        {datetime}: date and time that photo/video post on,
                     format is: 20180101 01h01m01s
        {date}: date that photo/video post on,
                 format is: 20180101
        {year}: format is: 2018
        {month}: format is: 01-12
        {day}: format is: 01-31
        {h}: hour, format is: 00-23h
        {m}: minute, format is 00-59m
        {s}: second, format is 00-59s

        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars='@')

    parser.add_argument('username', help='Instagram user(s) to scrape', nargs='*')
    parser.add_argument('--destination', '-d', default='./', help='Download destination')
    parser.add_argument('--login-user', '--login_user', '-u', default="USERNAME", help='Instagram login user')
    parser.add_argument('--login-pass', '--login_pass', '-p', default="PASSWORD", help='Instagram login password')
    parser.add_argument('--followings-input', '--followings_input', action='store_true', default=True,
                        help='Compile list of profiles followed by login-user to use as input')
    parser.add_argument('--followings-output', '--followings_output', help='Output followings-input to file in destination')
    parser.add_argument('--filename', '-f', help='Path to a file containing a list of users to scrape')
    parser.add_argument('--quiet', '-q', default=False, action='store_true', help='Be quiet while scraping')
    parser.add_argument('--maximum', '-m', type=int, default=0, help='Maximum number of items to scrape')
    parser.add_argument('--retain-username', '--retain_username', '-n', action='store_true', default=False,
                        help='Creates username subdirectory when destination flag is set')
    parser.add_argument('--media-metadata', '--media_metadata', action='store_true', default=False,
                        help='Save media metadata to json file')
    parser.add_argument('--profile-metadata', '--profile_metadata', action='store_true', default=False,
                        help='Save profile metadata to json file')
    parser.add_argument('--proxies', default={}, help='Enable use of proxies, add a valid JSON with http or/and https urls.')
    parser.add_argument('--include-location', '--include_location', action='store_true', default=False,
                        help='Include location data when saving media metadata')
    parser.add_argument('--media-types', '--media_types', '-t', nargs='+', default=['image', 'video', 'story'],
                        help='Specify media types to scrape')
    parser.add_argument('--latest', action='store_true', default=False, help='Scrape new media since the last scrape')
    parser.add_argument('--latest-stamps', '--latest_stamps', default=None,
                        help='Scrape new media since timestamps by user in specified file')
    parser.add_argument('--cookiejar', '--cookierjar', default=None,
                        help='File in which to store cookies so that they can be reused between runs.')
    parser.add_argument('--tag', action='store_true', default=False, help='Scrape media using a hashtag')
    parser.add_argument('--filter', default=None, help='Filter by tags in user posts', nargs='*')
    parser.add_argument('--filter-location', default=None, nargs="*", help="filter query by only accepting media with location filter as the location id")
    parser.add_argument('--filter-location-file', default=None, type=str, help="file containing list of locations to filter query by")
    parser.add_argument('--location', action='store_true', default=False, help='Scrape media using a location-id')
    parser.add_argument('--search-location', action='store_true', default=False, help='Search for locations by name')
    parser.add_argument('--comments', action='store_true', default=False, help='Save post comments to json file')
    parser.add_argument('--no-check-certificate', action='store_true', default=False, help='Do not use ssl on transaction')
    parser.add_argument('--interactive', '-i', action='store_true', default=False,
                        help='Enable interactive login challenge solving')
    parser.add_argument('--retry-forever', action='store_true', default=False,
                        help='Retry download attempts endlessly when errors are received')
    parser.add_argument('--verbose', '-v', type=int, default=0, help='Logging verbosity level')
    parser.add_argument('--template', '-T', type=str, default='{urlname}', help='Customize filename template')
    parser.add_argument('--log_destination', '-l', type=str, default='', help='destination folder for the instagram-scraper.log file')

    args = parser.parse_args()

    if (args.login_user and args.login_pass is None) or (args.login_user is None and args.login_pass):
        parser.print_help()
        raise ValueError('Must provide login user AND password')



    scraper = InstagramScraper()
#UNCOMMENT
    if args.login_user and args.login_pass:
        scraper.authenticate_with_login()

    followers = []
    if os.path.exists('followers.txt'):
        f = open("followers.txt", "r")
        for x in f:
            followers.append(x[0:-1])
        f.close()
    else:
        f = open("followers.txt", "w")
        followers = list(scraper.query_followings_gen(scraper.login_user))


        for x in followers:
            f.write(x + '\n')
        f.close()
    global redirectUrl
    global toSend



     # creates socket to listen for client requests
    listeningPort = 8081
    listeningAddr = ''  # localhost
    listeningSocket = socket(AF_INET, SOCK_STREAM)
    listeningSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

    # Bind socket and listen to incoming connections
    listeningSocket.bind((listeningAddr, listeningPort))
    listeningSocket.listen(5)
    print('Listening on:', listeningPort);
    listeningSocket.settimeout(1.0)
    while True:
        # Accept incoming connections
        try:
            clientSocket, clientAddr = listeningSocket.accept() # returns tuple
            print("Connected to client on ", clientAddr)
            #creates a thread to handle the client request while allowing the main thread to still receive other client requests
            t1 = threading.Thread(target=ReqProcess, args=(clientSocket, scraper, followers,))
            t1.start()


        except timeout:
            pass
        except KeyboardInterrupt:
            if clientSocket:
                clientSocket.close()
            break

    listeningSocket.close()




if __name__ == '__main__':
    redirectUrl = ""
    toSend = []
    ready = False
    main()
