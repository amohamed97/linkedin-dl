import urllib.request
import requests
import http.cookiejar as cookielib
import os
import getpass
from bs4 import BeautifulSoup as soup
from collections import namedtuple
import logging
from urllib.parse import urljoin
import re
from itertools import filterfalse

### Logger settings
logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')

### User data
USERNAME = ''
PASSWORD = ''
COURSE_SLUG = ''
BASE_DOWNLOAD_PATH = os.getcwd()

##
URL = 'https://www.linkedin.com'
LOGIN_URL = f"{URL}/login"
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
            "Accept": "*/*"}
COOKIE_JAR = requests.cookies.RequestsCookieJar()

FILE_TYPE_VIDEO = ".mp4"
Course = namedtuple("Course", ["name", "slug", "description", "unlocked", "chapters"])
Chapter = namedtuple("Chapter", ["name", "videos", "index"])
Video = namedtuple("Video", ["name", "slug", "index", "filename"])

## 
def build_course(course_element: dict):
    """
    Takes the whole course part of the json response and creates
    objects (named tuples) with it to be easily accessible later
    """
    chapters = [
        Chapter(name=chapter['title'],
                videos=[
                    Video(name=video['title'],
                          slug=video['slug'],
                          index=idx,
                          filename=f"{str(idx).zfill(2)} - {clean_dir_name(video['title'])}{FILE_TYPE_VIDEO}"
                          )
                    for idx, video in enumerate(chapter['videos'], start=1)
                ],
                index=idx)
        for idx, chapter in enumerate(course_element['chapters'], start=1)
    ]
    course = Course(name=course_element['title'],
                    slug=course_element['slug'],
                    description=course_element['description'],
                    unlocked=course_element['fullCourseUnlocked'],
                    chapters=chapters)
    return course


def clean_dir_name(dir_name):
    # Remove starting digit and dot (e.g '1. A' -> 'A')
    # Remove bad characters         (e.g 'A: B' -> 'A B')
    no_digit = re.sub(r'^\d+\.', "", dir_name)
    no_bad_chars = re.sub(r'[\\:<>"/|?*]', "", no_digit)
    return no_bad_chars.strip()

def chapter_dir(course: Course, chapter: Chapter):
    """
    Forms the path to the chapter using the course's name and the chapter's name
    """
    folder_name = f"{str(chapter.index).zfill(2)} - {clean_dir_name(chapter.name)}"
    chapter_path = os.path.join(BASE_DOWNLOAD_PATH, clean_dir_name(course.name), folder_name)
    return chapter_path

def login():
    with requests.Session() as session:
        logging.info("Logging in")
        session.headers = HEADERS
        session.cookies = COOKIE_JAR
        data = session.get(LOGIN_URL)
        # creating a soup (easily accessible html DOM representation) to get the csrf token 
        page_soup = soup(data.text, "html.parser")
        login_csrf_el = page_soup.findAll("input", {'name': 'loginCsrfParam'})

        payload = {
            'session_key': USERNAME,
            'session_password': PASSWORD,
            'loginCsrfParam': login_csrf_el[0].attrs['value'],
            "isJsEnabled": False
        }

        session.post(urljoin(URL, 'uas/login-submit'), data=payload)
        # li_at cookie existance proves that i'm logged in
        if 'li_at' not in (key.lower() for key in session.cookies.get_dict().keys()):
            logging.error("Failed to login")
            raise RuntimeError("[!] Could not login. Please check your credentials")
        # adding csrf-token to the headers to be used for future requests
        HEADERS['Csrf-Token'] = next(v.strip('"') for k,v in session.cookies.get_dict().items() if k.lower() == 'jsessionid')        
        logging.info("Logged in successfully")

def fetch_course():
    """
    Fetches the courses data from the linkedin-learning API directly
    """
    url = f"{URL}/learning-api/detailedCourses??fields=fullCourseUnlocked,releasedOn,exerciseFileUrls,exerciseFiles&" \
          f"addParagraphsToTranscript=true&courseSlug={COURSE_SLUG}&q=slugs"
    with requests.Session() as session:
        session.headers = HEADERS
        session.cookies = COOKIE_JAR
        resp = session.get(url)
        resp_json = resp.json()
        course = build_course(resp_json['elements'][0])
        fetch_chapters(course)

def fetch_chapters(course):
    chapters_dirs = [chapter_dir(course, chapter) for chapter in course.chapters]
    # get the chapters directories that are not created yet
    missing_directories = filterfalse(os.path.exists, chapters_dirs)
    # create the missing directories
    for d in missing_directories:
        os.makedirs(d)
    for chapter in course.chapters:
        fetch_chapter(course, chapter)

def fetch_chapter(course, chapter):
    for video in chapter.videos:
        fetch_video(course, chapter, video)

def fetch_video(course, chapter, video):
    video_file_path = os.path.join(chapter_dir(course, chapter), video.filename)
    video_exists = os.path.exists(video_file_path)
    if video_exists:
        return
    logging.info(f"Fetching Chapter #{chapter.index} Video #{video.index}")
    with requests.Session() as session:
        session.headers = HEADERS
        session.cookies = COOKIE_JAR
        video_url = f'{URL}/learning-api/detailedCourses?addParagraphsToTranscript=false&courseSlug={course.slug}&' \
                    f'q=slugs&resolution=_720&videoSlug={video.slug}'
        resp_json = None
        tries = 3
        for _ in range(tries):
            try:
                resp = session.get(video_url, headers=HEADERS)
                resp_json = resp.json()
                resp.raise_for_status()
                break
            except Exception:
                pass
        if not resp_json:
            logging.error(f"Failed to fetch Chapter #{chapter.index} Video #{video.index}")
            logging.error(f"Couldn't get the video url json")
            return

        try:
            # This throws exception if the course is locked for the user as url is not available
            video_url = resp_json['elements'][0]['selectedVideo']['url']['progressiveUrl']
        except Exception as e:
            logging.error(f"Failed to fetch Chapter #{chapter.index} Video #{video.index}")
            logging.exception(f"Couldn't get video_url: {e}")
            return
            
        download_file(video_url, video_file_path)

def download_file(url, output):
    with requests.Session() as session:
        session.headers = HEADERS
        session.cookies = COOKIE_JAR
        with session.get(url, timeout=100, stream=True) as resp:
            try:
                with open(output, 'wb') as fd:
                    for chunk in resp.iter_content(chunk_size=1024):
                        fd.write(chunk)
            except Exception as e:
                logging.exception(f"Error while downloading: '{e}'")
                if os.path.exists(output):
                    os.remove(output)

def main():
    login()
    fetch_course()

if __name__ == "__main__":
    USERNAME = input("Enter your username:")
    PASSWORD = getpass.getpass("Enter your password:")
    print("Enter the course's slug (the course name as specified in the url linkedin.com/learning/<SLUG>)")
    COURSE_SLUG = input("Course slug:")    
    main()