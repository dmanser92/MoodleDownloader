import http.cookiejar as cookielib
import urllib
import urllib.request as ur
import os.path
import re

from configparser import ConfigParser


def getContentType(pageUrl):
    with urllib.request.urlopen(pageUrl) as url:
        pageHeaders = url.read()
        pageHeaders = dict(response.info())
    contentType = pageHeaders.getheader('content-type')
    return contentType


def readConfig():
    conf = ConfigParser()
    project_dir = os.path.dirname(os.path.abspath(__file__))
    conf.read(os.path.join(project_dir, 'config.ini'))

    root_directory = conf.get("dirs", "root_dir").strip('\'"')
    username = conf.get("auth", "username").strip('\'"')
    password = conf.get("auth", "password").strip('\'"')
    authentication_url = conf.get("auth", "url").strip('\'"')
    return root_directory, username, password, authentication_url


def installOpener():
    # Store the cookies and create an opener that will hold them
    cj = cookielib.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # Add our headers
    opener.addheaders = [('User-agent', 'Moodle-Crawler')]

    # Install our opener (note that this changes the global opener to the one
    # we just made, but you can also just call opener.open() if you want)
    urllib.request.install_opener(opener)


def getDataForPOST():
    # Input parameters we are going to send
    payload = {
        'username': username,
        'password': password
    }

    # Use urllib to encode the payload
    data = urllib.parse.urlencode(payload)
    data = data.encode('ascii')

    user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
    headers = {'User-Agent': user_agent}
    return data, headers


# Read ConfigFile
(root_directory, username, password, authentication_url) = readConfig()

# Install Opener with cookie
installOpener()

# Encrypt Data and create headers
(data, headers) = getDataForPOST()

# Build our Request object (supplying 'data' makes it a POST)
req = urllib.request.Request(authentication_url, data, headers)

# Make the request and read the response
with urllib.request.urlopen(req) as response:
    contents = response.read()
    dashboardUrl = response.geturl()
    contents = contents.decode(encoding='UTF-8')

# Verify the contents
if "Dashboard" not in contents:
    print("Cannot connect to moodle")
    exit(1)

# Find the links to all courses and remove doubles
courses_withDoubles = re.findall('href="[^"]*\/course\/view\.php\?id=\d{3,6}"', contents)
courses_withDoubles = list((s.replace('"', '').replace('href=', '')) for s in courses_withDoubles)
courses = []
[courses.append(i) for i in courses_withDoubles if not i in courses]
coursecounter = 0


# Now let's do the following for every course
for course in courses:

    # Get the course html content
    with urllib.request.urlopen(course) as response:
        course_content = response.read()
        course_content = course_content.decode(encoding='UTF-8')

    # Find the title of the course we're in
    course_contents_title = re.findall('<h1>[^"]*<\/h1>', course_content)
    course_contents_title = (s.replace('<h1>', '') for s in course_contents_title)
    course_contents_title = list((s.replace('</h1>', '') for s in course_contents_title))
    course_contents_title = "".join(y for y in course_contents_title[0] if y.isalnum())

    # Create directory for the course-files
    if not os.path.isdir(root_directory + course_contents_title):
        os.mkdir(root_directory+course_contents_title)

    # Find all the names of the resources and titles
    course_strings = course_content.split('class="course-content"', 1)[-1]
    course_strings = course_strings.split('mod/resource/view.php?id=')
    course_splitted = []
    del course_strings[0]
    [course_splitted.append(s) for s in course_strings if (len(course_strings) > 0) and "&amp;redirect=" not in s]

    course_resources = []
    course_titles = []

    for i in range(0, len(course_splitted) - 1):
        # Resource
        course_resources.append(dashboardUrl.replace('my/', '') + "mod/resource/view.php?id=" + re.search('^\d{3,6}', course_splitted[i]).group())
        # Title
        str = re.search('instancename">[^"]*<span', course_splitted[i]).group()
        str = str.replace('instancename">', '')
        str = str.replace('<span', '')
        course_titles = list(course_titles)
        course_titles.append(str)
        course_titles = ((s.replace('instancename">', '') for s in course_titles))
        # Folder
        if ("mod/folder/download_folder.php" in course_splitted[i]):
            course_titles = list(course_titles)
            course_titles.append(str)
            idValue = re.findall('value="\d{3,6}', course_splitted[i])[0]
            idValue = idValue.replace('value="', '')
            course_resources.append(dashboardUrl.replace('my/', '') + "mod/folder/download_folder.php?id=" + idValue)

    # Correction title for directoryname
    course_titles = [x for x in course_titles if (x != 'Ankündigungen') and (x != 'Nachrichtenforum') and (x != 'News Forum')]
    for x in range(0, len(course_titles)):
        course_titles[x] = "".join(y for y in course_titles[x] if y.isalnum())

    counter = 0
    real_link = ''

    # Download resource list
    for link in course_resources:
        current_dir = root_directory + course_contents_title + "\\"

        with urllib.request.urlopen(link) as response:
            content_file = response.read()
            redirectedurl = response.geturl()

            # get extension
            ext_test_old = redirectedurl.rsplit('.')
            ext_test = ext_test_old[len(ext_test_old) - 1]
            ext = ''
            extlist = []
            ext_test = ext_test.replace('forcedownload', '')
            extcounter = 0

            for i in ext_test:
                if(i.isalpha() or (i.isdigit() and extcounter<3)):
                    ext += i
                else:
                    continue
                extcounter += 1

        # find final link of resource
        if (redirectedurl.find("download_folder") != -1):
            ext = "zip"
            real_link = redirectedurl
        elif (re.match('phpid', ext)):
            content_file = content_file.decode(encoding='UTF-8')

            real_link = re.search('<a href="[^"]*mod_resource[^"]*"', content_file).group()
            real_link = real_link.replace('<a href=', '').replace('"', '')

            extlist = real_link.rsplit('.')
            ext = extlist[len(extlist)-1]
            ext = "".join(y for y in ext if y.isalpha())
        else:
            real_link = redirectedurl
            pass

        # Put filename together
        filename = current_dir + course_titles[counter] + '.' + ext

        # Check if file is already there
        if os.path.isfile(filename):
            print("File found : ", filename)
            counter += 1
            continue
        print("Creating file : ", filename)

        # Try to download the file to the path
        urllib.request.URLopener()
        try:
            urllib.request.urlretrieve(real_link, filename)
        except:
            print("Failed to write file from %s to %s", real_link, filename)

        counter += 1
    coursecounter += 1

print("Update Complete")