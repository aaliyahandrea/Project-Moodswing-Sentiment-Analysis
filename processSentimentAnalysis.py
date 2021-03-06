# make sure runtime = Python 3.7
import csv
import json
import boto3

s3 = boto3.client('s3')

"""
@author: Neha Deshpande, Harrison Banh
Triggered by the creation of a csv file of tweets in the S3 bucket tweetdump/csv/files/tmp
Makes a call to Amazon Comprehend in order to determine the sentiment of each tweet
Writes the tweet as a message to the SQS queue processed_tweets so that it can be 
written into the db by the next lambda function
"""

def lambda_handler(event, context):
    bucket = 'tweetdump'
    if event:
        # get S3 file whose creation triggered this lambda
        file_obj = event["Records"][0]
        filename = str(file_obj['s3']['object']['key'])
        fileObj = s3.get_object(Bucket=bucket, Key=filename)

        # read the csv file
        file_content = fileObj["Body"].read().decode('utf-8')
        rows = csv.reader(file_content.split("\n"))
        # skip the row of column headers
        next(rows)
        for row in rows:
            # A dictionary of all the associated sentiment values for SQS
            sentimentMap = {}

            if len(row) == 0:
                break

            text = row[2]

            # format the date into a YY-MM-DD HH:MM:SS
            tweetdate = row[5]
            tokens = tweetdate.split(' ')
            date_string = tokens[-1] + '-' + month_to_numbers(tokens[1]) + '-' + tokens[2] + ' ' + tokens[3]

            # generate sentiment score for the text
            client = boto3.client('comprehend')
            sentimentJSON = client.detect_sentiment(Text=text, LanguageCode='en')
            overall_sentiment = sentimentJSON['Sentiment']
            sentiment = sentimentJSON['SentimentScore']
            positive = sentiment["Positive"]
            neutral = sentiment["Neutral"]
            negative = sentiment["Negative"]
            mixed = sentiment["Mixed"]

            # Adding to dictionary for SQS messaging
            sentimentMap['positive score'] = str(positive)
            sentimentMap['neutral score'] = str(neutral)
            sentimentMap['negative score'] = str(negative)
            sentimentMap['mixed score'] = str(mixed)
            sentimentMap['overall sentiment'] = str(overall_sentiment)

            # Adding in all other attributes into the map
            sentimentMap['id str'] = 'null' if len(row[1]) == 0 else row[1]
            sentimentMap['tweet text'] = 'null' if len(row[2]) == 0 else row[2]
            if sentimentMap['tweet text'] != 'null':
                tweet_text = sentimentMap['tweet text']
                tweet_text = tweet_text.replace('"', '')
                tweet_text = tweet_text.replace("'", '')
                sentimentMap['tweet text'] = tweet_text

            sentimentMap['retweet count'] = 'null' if len(row[3]) == 0 else row[3]
            sentimentMap['favorite count'] = 'null' if len(row[4]) == 0 else row[4]
            sentimentMap['created at'] = date_string
            sentimentMap['coordinates'] = 'null' if len(row[6]) == 0 else row[6]
            sentimentMap['in reply to screen name'] = 'null' if len(row[7]) == 0 else row[7]
            sentimentMap['user id str'] = 'null' if len(row[8]) == 0 else row[8]
            sentimentMap['user location'] = 'null' if len(row[9]) == 0 else row[9]
            sentimentMap['user screen name'] = 'null' if len(row[10]) == 0 else row[10]
            sentimentMap['hashtags'] = 'null' if len(row[11]) == 0 else row[11]
            if sentimentMap['hashtags'] != 'null':
                hashtags = sentimentMap['hashtags']
                hashtags.replace("'", '')
                hashtags = hashtags[1:-1]
                if len(hashtags) == 0:
                    hashtags = 'null'
                sentimentMap['hashtags'] = hashtags
            sentimentMap['mentions'] = 'null' if len(row[12]) == 0 else row[12]
            if sentimentMap['mentions'] != 'null':
                mentions = sentimentMap['mentions']
                mentions.replace("'", '')
                mentions = mentions[1:-1]
                if len(mentions) == 0:
                    mentions = 'null'
                print(mentions)
                sentimentMap['mentions'] = mentions
            sentimentMap['group'] = 'null' if len(row[13]) == 0 else row[13]

            print(sentimentMap)
            body = "twitter.com/status/" + sentimentMap['id str']
            # Upload the processed sentiment and the tweet to a queue
            sqs = boto3.resource('sqs')
            queue = sqs.get_queue_by_name(QueueName='processed_tweets')
            # Define the messages's structure and send all the tweet attributes to SQS queue: processed_tweets as a message
            response = queue.send_message(MessageBody=body, MessageAttributes={
                'ids': {
                    'StringValue': sentimentMap['id str'] + ' ' + sentimentMap['in reply to screen name'] + ' ' +
                                   sentimentMap['user id str'] + ' ' + sentimentMap['user screen name'],
                    'DataType': 'String'
                },
                'tweet_text': {
                    'StringValue': sentimentMap['tweet text'],
                    'DataType': 'String'
                },
                'counts': {
                    'StringValue': sentimentMap['retweet count'] + " " + sentimentMap['favorite count'],
                    'DataType': 'String'
                },
                'created_at': {
                    'StringValue': sentimentMap['created at'],
                    'DataType': 'String'
                },
                'coordinates': {
                    'StringValue': sentimentMap['coordinates'],
                    'DataType': 'String'
                },
                'user_location': {
                    'StringValue': sentimentMap['user location'],
                    'DataType': 'String'
                },
                'hashtags': {
                    'StringValue': sentimentMap['hashtags'],
                    'DataType': 'String'
                },
                'mentions': {
                    'StringValue': sentimentMap['mentions'],
                    'DataType': 'String'
                },
                'group': {
                    'StringValue': sentimentMap['group'],
                    'DataType': 'String'
                },
                'scores': {
                    'StringValue': sentimentMap['positive score'] + " " + sentimentMap['neutral score'] + " " +
                                   sentimentMap['negative score'] + " " + sentimentMap['mixed score'] + " " +
                                   sentimentMap['overall sentiment'],
                    'DataType': 'String'
                }
            }
                                          )
            print(response.get('MessageId'))
            print("Failure: " + str(response.get('Failure')))

    return {
        'statusCode': 200,
        'body': json.dumps('Tweets have been processed and pushed into processed_tweets')
    }


"""
Psuedo switch statement used to convert month abbreviations to their numerical
counterpart. Used to help reformat Tweet dates to YY-MM-DD TIME format.   
"""


def month_to_numbers(month):
    switcher = {
        'Jan': '01',
        'Feb': '02',
        'Mar': '03',
        'Apr': '04',
        'May': '05',
        'Jun': '06',
        'Jul': '07',
        'Aug': '08',
        'Sep': '09',
        'Oct': '10',
        'Nov': '11',
        'Dec': '12'
    }
    return switcher[month]