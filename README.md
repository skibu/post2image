# Xrosspost.com 
Welcome to Xrosspost.com, a tool for easily crossposting tweets from Xitter to Bluesky. This is convenient for folks who want to migrate from Xitter to Bluesky, yet still want to show others some choice toxic tweets, yet without the user actually going to Xitter and supporting ads on that system.

Xrosspost.com also works for Threads as well, which is nice since Threads has recently gone fully toxic, too.

Normally if you add a URL of a Tweet (e.g. https://x.com/skibuSmith/status/1861280658573725949) to a Bluesky post the viewers will just see the ugly URL and not an image of the actual tweet. This is because Space Karen Leon Musk broke Twitter intentionally to try to keep users on the hellsite by making crossposts problematic. Some people have resorted to taking screen shots of a tweet and posting that image. That of course is a nuisance. Plus one then doesn't provide a link back to the original Tweet to show that it really was posted and is not just some photoshopped image.

Xrosspost.com simply makes it nice and easy to crosspost Tweet images on Bluesky (and Threads too)

# How to use

You can get the link for a Tweet by clicking on its adjacent share button on the lower right side of the Tweet and clicking on "Copy link". Then in Bluesky start to create a new Bluesky post and past in the URL (e.g. https://x.com/skibuSmith/status/1861280658573725949). Bluesky will automatically create the ugly version of the link. No problem! Delete the ugly link by clicking on the "X" delete button. Then edit the link so that instead of referring to "x.com" it instead points to "xrosspost.com" just by adding the characters "rosspost" in the right place. The new image version of the crosspost will then appear. If the image for the post isn't automatically generated then move the pointer to the end of the URL and add a space. This should nudge Bluesky into generating the image. Then finish up your Bluesky post and you are all done. 

# Technical Details
For those who want to know how this all works behind the scenes...

## Post2Image
The Post2Image GitHub repository is [here](https://github.com/skibu/post2image)

post2image takes in a URL for a social media post and returns an Open Graph card that points to an image of the post. 

## Purpose 
The main goal is to make it easy to repost or quote post a Xitter post (but also threads and possibly 
others) onto Bluesky and have it look like a the full original post. This would be simpler than having 
to take a screenshot of the original post and then post it. 

And importantly, currently Xitter doesn't provide any reasonable image of the post if one just uses the 
original URL on Bluesky. Yes, something else broken by Space Karen.

## How it works
Idea is to have a domain name similar to x.com, like fixedX.com so that can easily change it to x.com. So when a user wants to repost a tweet to Bluesky they get the URL for the tweet, like https://x.com/outbreakupdates/status/1871187575500841435, and then post it to Bluesky as https://fixedx.com/outbreakupdates/status/1871187575500841435 . 

Bluesky will access the link in order to get the Open Graph card info that contains a description of the link. The fixedx.com site is running the post2image python web server. It will handle the Open Graph card request. post2image determines the post type (Xitter, Threads, or Bluesky) and uses the appropriate social media site to render the post as html. Then it passes the html to a headless browser which renders the html, including javascript, iframes, and css, and obtains the corresponding png image for the post. The image is stored and made available via a URL. Then post2image returns a html page that contains the Open Graph card info, including a link to the created image of the tweet. 

The social media system that made the https://fixedx.com/ request takes the Open Graph card info and incorporates into the Bluesky post being created.

Caching of the tweet info is of course done.

## Status

Was able to manually get convert a tweet to html and use headless browser to convert it an image. Lots more to do!!!

## Configuring Server
Install chromedriver, which allows selenium to actually communicate with the browser.
```
sudo apt install chromium-chromedriver
```

Download code from github:
```
git clone https://github.com/skibu/post2image.git
```

Need to load in certain python libraries first.
```
# Because of version complications when loading Pillow might
# need to first get proper version of libijpeg62 libs
sudo apt install libjpeg62-turbo=1:2.0.6-4
sudo apt install libjpeg62-turbo-dev=1:2.0.6-4

# Note that running pip via python3 to make sure using proper version

# Image processing is done using Pillow (aka PIL)
python3 -m pip install --upgrade Pillow

# For more easily handling http requests
python3 -m pip install requests

# Using selenium to run headless browser that converts html to image
# Note that running pip via python3 to make sure using proper version
python3 -m pip install --upgrade selenium
```

## Running app
First, from home directory, get the application from github: git clone https://github.com/skibu/post2image.git

Then run it via either: `python3 post2image/main.py` or `post2image/main.py`

## Auto startup
Important consideration is to have the application start automatically at bootup. If using a Raspberry Pi one can simply modify the /etc/rc.local and add:

```
# Start post2image, as user pi instead of root.
# Note, when running the app, need to first cd into ones post2image
# directory so that the config data file and the image and cache 
# directories can be found
sudo -H -u pi bash -c 'cd /home/pi/post2image/; /usr/bin/python3 main.py' &
```
