# Post2Image

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

To run:
```
python3 main.py
```
