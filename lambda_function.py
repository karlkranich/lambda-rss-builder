# This function is meant to be triggered by an mp3 file uploaded to the podcast S3 bucket.
# It reads podcast episode info from a DynamoDB table, figures out the mp3 duration and file size,
# and builds a new podcast rss feed.
# *** Be sure that the rss file update doesn't trigger this function in an infinite loop ***
# We limit the trigger to a prefix that has only the mp3 files.  You could also limit the trigger to *.mp3 files.

import json
import boto3
from podgen import Podcast, Media, Category, htmlencode, Person
import datetime
import pytz
from mutagen.mp3 import MP3
import os
import sys

# Returns all the items from the DynamoDB podcast table
def query_episodes():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('ccc-podcast')
    response = table.scan()
    return response['Items']

# Creates or updates the specified episode in the DynamoDB table    
def update_episode(episodeNum, mediaFile, size, duration):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('ccc-podcast')
    response = table.update_item(
        ExpressionAttributeNames={
            '#M': 'media-file',
            '#S': 'size',
            '#D': 'duration'
        },
        Key={'episode-num': episodeNum},
        UpdateExpression="set #M=:m, #S=:s, #D=:d",
        ExpressionAttributeValues={
            ':m': mediaFile,
            ':s': size,
            ':d': duration
        },
        ReturnValues="UPDATED_NEW"
    )

def lambda_handler(event, context):
    print('Starting cccRssBuilder Lambda function')
    # Get episodes from DynamoDB
    episodes = query_episodes()
    episodes.sort(key=lambda x: x['episode-num'])
    
    # Create the podcast feed
    # Main podcast info comes from "episode 0"
    episodeInfo = episodes[0]
    separator = ', '
    p = Podcast()
    p.name = episodeInfo['name']
    p.description = episodeInfo['description']
    p.website = episodeInfo['website']
    p.explicit = episodeInfo['explicit']
    p.image = episodeInfo['image']
    p.feed_url = episodeInfo['feed-url']
    p.language = episodeInfo['language']
    p.category = Category(episodeInfo['category'], episodeInfo['subcategory'])
    p.owner = Person(episodeInfo['owner-name'], episodeInfo['owner-email'])
    
    # Process each episode
    for episode in episodes:
        # Skip "Episode 0"
        if episode['episode-num'] == 0:
            continue
        # Check if episode contains media file info (name, duration, size).  If not, add it to db and episode object.
        if 'media-file' not in episode:
            episodeNum = episode['episode-num']
            print('Analyzing media file for episode', episodeNum)
            mediaFile = 'ccc-{:03d}-{}.mp3'.format(int(episodeNum), episode['pub-date'])
            print('Media file:', mediaFile)
            localMediaFile = '/tmp/' + mediaFile
            s3 = boto3.client('s3')
            s3.download_file('kwksolutions.com', 'ccc/media/' + mediaFile, localMediaFile)
            
            # Try to analyze the mp3 file - looking for duration and file size
            try:
                audio = MP3(localMediaFile)
            except:
                print('Not an MP3 file!')
                return
            duration = round(audio.info.length)
            hours = int(duration/3600)
            minutes = int((duration % 3600)/60)
            seconds = duration % 60
            if hours == 0:
                durationStr = '{:02d}:{:02d}'.format(minutes, seconds)
            else:
                durationStr = '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
            size = str(os.path.getsize(localMediaFile))
            update_episode(episodeNum, mediaFile, size, durationStr)
            episode['media-file'] = mediaFile
            episode['size'] = size
            episode['duration'] = durationStr
    
        # Figure out all the info needed for the episode object
        mediaURL = 'https://www.kwksolutions.com/ccc/media/' + episode['media-file']
        durationList = episode['duration'].split(':')
        secs = int(durationList[-1])
        mins = int(durationList[-2])
        try:
            h = int(durationList[-3])
        except:
            h = 0
        pubdateList = episode['pub-date'].split('-')
        year = int(pubdateList[0])
        month = int(pubdateList[1])
        day = int(pubdateList[2])
        
        # Build the episode object
        e = p.add_episode()
        e.id = mediaURL
        e.title = 'Episode ' + str(episode['episode-num'])
        e.summary = episode['description']
        e.link = 'http://christcommunitycarmel.org/get-involved/podcasts'
        e.publication_date = datetime.datetime(year, month, day, 12, 00, 00, tzinfo=pytz.timezone('EST'))
        e.media = Media(mediaURL, episode['size'], duration=datetime.timedelta(hours = h, minutes = mins, seconds = secs))
    
    # Write the rss file
    print('Writing RSS file to S3')
    rssLocalFile = '/tmp/podcast.rss'
    rssS3File = 'ccc/podcast.rss'
    p.rss_file(rssLocalFile)
    s3 = boto3.client('s3')
    s3.upload_file(rssLocalFile, 'kwksolutions.com', rssS3File, ExtraArgs={'ContentType': 'text/xml'})

    return
