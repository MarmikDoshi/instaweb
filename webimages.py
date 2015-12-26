import json
import os
import urllib
import datetime

from google.appengine.api import users, mail
from google.appengine.ext import blobstore, ndb
from google.appengine.ext.blobstore.blobstore import BlobKey
from google.appengine.ext.webapp import blobstore_handlers

import webapp2
import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

DEFAULT_IMAGE_NAME = 'Instaimage'


class UserImage(ndb.Model):
    owner = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()
    likes_count = ndb.IntegerProperty(default=0)
    unlike_count = ndb.IntegerProperty(default=0)
    comment = ndb.StringProperty()
    number_of_comments = ndb.IntegerProperty(default=0)
    type = ndb.StringProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)


def uploaded_image_key(image_name=DEFAULT_IMAGE_NAME):
    """Constructs a Datastore key for a Imagename entity with name."""
    return ndb.Key('Uploadeddata', image_name)


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.out.write('<html><body>')
        upload_url = blobstore.create_upload_url('/upload_photo')
        image_name = self.request.get('image_name', DEFAULT_IMAGE_NAME)
        images = UserImage.query(
            ancestor=uploaded_image_key(image_name)) \
            .order(-UserImage.date) \
            .fetch(10)

        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'user': user,
            'images': images,
            'upload_url': upload_url,
            'url': url,
            'url_linktext': url_linktext,
        }
        template = JINJA_ENVIRONMENT.get_template('uploadimage.html')
        self.response.write(template.render(template_values))


class UploadImage(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        try:
            image_name = self.request.get('image_name', DEFAULT_IMAGE_NAME)
            image = UserImage(parent=uploaded_image_key(image_name))

            upload = self.get_uploads()[0]
            if users.get_current_user():
                image.owner = users.get_current_user().nickname()
            filetype = upload.content_type
            if filetype.startswith('video'):
                image.type = 'video'
                image.put()
            elif filetype.startswith('image'):
                image.type = 'image'
                image.put()
            else:
                return self.response.out.write("Invalid file format")
            image.blob_key = upload.key()
            image.put()

            self.redirect('/?' + urllib.urlencode(
                {'Uploadeddata': image_name}))
        except Exception as e:
            self.response.out.write('Please try after sometime.')


class DisplayImage(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        photo_key = self.request.get('img_id')

        blobinfo = blobstore.get(photo_key)

        if not blobstore.get(photo_key):
            self.error(404)
        else:
            self.send_blob(photo_key, blobinfo.content_type)


class Countlikes(webapp2.RequestHandler):
    """
    Increase the count of likes and dislikes
    """
    def post(self):
        user = users.get_current_user()
        if user:
            data = json.loads(self.request.body)
            response = data['like']

            image = UserImage.query().filter(
                UserImage.blob_key == BlobKey((data['id']))).get()

            if response == 'Like':
                if not image.likes_count:
                    image.likes_count = 0
                image.likes_count += 1
            else:
                if not image.unlike_count:
                    image.unlike_count = 0
                image.unlike_count += 1
            image.put()
            self.response.out.write(json.dumps({'type': '+OK'}))
        else:
            self.response.out.write(
                json.dumps({'msg': 'Please login to change the like',
                            'type': '-ERR'}))


class CommentOnImage(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if user:
            data = json.loads(self.request.body)

            image = UserImage.query().filter(
                UserImage.blob_key == BlobKey(data['id'])).get()
            image.comment = data['comment']
            image.put()
            if not image.number_of_comments:
                image.number_of_comments = 0
            image.number_of_comments += 1
            image.put()
            self.response.out.write(json.dumps({'type': '+OK'}))
        else:
            self.response.out.write(json.dumps(
                {'msg': 'Please login to comment on the image',
                 'type': '-ERR'}))


class SendUploadedData(webapp2.RequestHandler):
    """
    Send email that contains the website details
    """
    def get(self):
        sender_address = "doshimarmik018@gmail.com"
        recipient = "get@znapin.com"
        subject = "Website details"

        last_hour = datetime.datetime.now() - datetime.timedelta(hours=1)

        image_name = self.request.get('image_name', DEFAULT_IMAGE_NAME)
        images = UserImage.query(
            ancestor=uploaded_image_key(image_name)) \
            .filter(UserImage.date > last_hour)
        uploads = images.count()
        likes = 0
        unlikes = 0
        comments = 0
        for image in images:
            likes += image.likes_count
            unlikes += image.unlike_count
            comments += image.number_of_comments

        body = """
            Following are the last hour updates:
            Number of uploads = %s
            Number of likes = %s
            Number of unlikes = %s
            Number of comments = %s
        """ % (uploads, likes, unlikes, comments)
        mail.send_mail(sender_address, recipient, subject, body)


app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/upload_photo', UploadImage),
    ('/img', DisplayImage),
    ('/changelike', Countlikes),
    ('/comment', CommentOnImage),
    ('/senduploadeddata', SendUploadedData),
], debug=True)
