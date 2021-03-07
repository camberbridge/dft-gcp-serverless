import config
import tweepy
import datetime
from google.cloud import datastore
import numpy as np
import cv2
import tempfile
import requests


"""
Twitter API 
"""

# Authentication
auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)
api = tweepy.API(auth, wait_on_rate_limit=True)
# Num of top tweets on the home timeline
N = 10


def do_fav(tweet_id):
    try:
        api.create_favorite(tweet_id)
    except:
        pass


def do_tweet(tweet_url):
    msg = "今日も１日＼＼\\٩( 'ω' )و //／／\n"
    msg += tweet_url
    try:
        api.update_status(msg)
    except:
        pass


"""
Cloud Datastore
"""

# Instantiates a client
datastore_client = datastore.Client()
# The kind for the new entity
kind = "Twitter_home"
# The name/ID for the new entity
name = "latest_tweet_id"
# The Cloud Datastore key for the new entity
task_key = datastore_client.key(kind, name)


def put_datastore(tweet_id):
    # Prepare the new entity
    task = datastore.Entity(key=task_key)
    task["id"] = tweet_id
    task["timestamp"] = datetime.datetime.now()

    # Save the entity
    datastore_client.put(task)


def get_datastore():
    entity = datastore_client.get(key=task_key)
    return entity["id"]


"""
Detect faces by OpenCV(DNN) with pretrained caffe model
"""

# Pretrained DNN caffe model
# Ref: https://github.com/spmallick/learnopencv/tree/master/FaceDetectionComparison/models
PROTOTXT_PATH = './deploy.prototxt'
WEIGHTS_PATH = './res10_300x300_ssd_iter_140000_fp16.caffemodel'
# Confidence threshold
CONFIDENCE = 0.9


def imread_web(url, flags=cv2.IMREAD_COLOR, dtype=np.uint8):
    try:
        res = requests.get(url)
        # Create tmpfile(Download img in tmpfile)
        # Ref: https://cloud.google.com/appengine/docs/standard/go/using-temp-files
        with tempfile.NamedTemporaryFile(dir="/tmp/") as fp:
            fp.write(res.content)
            fp.file.seek(0)

            n = np.fromfile(fp.name, dtype)
            img = cv2.imdecode(n, flags)
            img_h, img_w = img.shape[:2]
            img_hf_w = img_w // 2
            img_hf_h = img_h // 2
            halfimg = cv2.resize(img, (img_hf_w, img_hf_h))
            return halfimg
    except Exception as e:
        print(e)
        return None


def get_face_num(img):
    img_size = 600
    blob = cv2.dnn.blobFromImage(cv2.resize(img, (img_size, img_size)), 1.0,
                                 (img_size, img_size), (104.0, 177.0, 123.0))

    # Load a model
    net = cv2.dnn.readNetFromCaffe(PROTOTXT_PATH, WEIGHTS_PATH)
    net.setInput(blob)
    detections = net.forward()

    face_num = 0
    for i in range(0, detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > CONFIDENCE:
            face_num += 1

    print("Detected face Num: ", face_num)
    return face_num


def main(event, context):
    id_counter = 0

    # If latest ID is in Datastore, give since_id for param
    try:
        timeline = api.home_timeline(since_id=get_datastore(), count=N)
    except:
        timeline = api.home_timeline(count=N)

    for status in timeline:
        if id_counter == 0:
            latest_t_id = status.id
            # Write latest ID to Datastore
            put_datastore(latest_t_id)

        # Exclude RT
        if not "RT @" in status.text[0:4]:
            tweet_url = "https://twitter.com/" + str(
                status.user.screen_name) + "/status/" + str(status.id)
            print("~~~", status.id)
            print("name:" + status.user.name)
            print(status.text)
            print(tweet_url)

            if 'media' in status.entities:
                for media in status.extended_entities['media']:
                    media_url = media['media_url']
                    print(media_url)

                    # Image (Face) Recognition & do_tweet
                    img = imread_web(media_url)
                    if img is None:
                        pass
                    elif get_face_num(img) > 0:
                        do_tweet(tweet_url)
                        break

        id_counter += 1


# For test
#if __name__ == "__main__":
#  main("foo", "bar")
