# lambda-rss-builder
This function is meant to be triggered by an mp3 file uploaded to the podcast S3 bucket **after** episode info has been added to a DynamoDB table.

It reads podcast episode info from DynamoDB, figures out the mp3 duration and file size, and builds a new podcast rss feed.

**Be sure that the rss file update doesn't trigger this function in an infinite loop**

Limit the trigger to a prefix that has only the mp3 files, or to *.mp3 files.

## Build info

Python modules are installed into a "package" folder on a linux machine (I used Cloud9) according to instructions here: [AWS Lambda deployment package in Python](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
