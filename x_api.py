import requests
import json 
import time
import os
from dotenv import load_dotenv

load_dotenv()

BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

def set_rules(keywords):
    url = "https://api.twitter.com/2/tweets/search/stream/rules"
    
    payload = {"add": [{"value": f"{', '.join(keywords)} -is:tweet", "tag": "Keyword posts"}]}
    print(payload)
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code != 201:
        raise Exception(f"Cannot add rules (HTTP {response.status_code}): {response.text}")
    
    print(f"Rules set: {response.json()}")

def get_stream(limit=5):
    url = "https://api.twitter.com/2/tweets/search/stream"
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }

    tweets = []
    with requests.get(url, headers=headers, stream=True) as response:
        if response.status_code != 200:
            raise Exception(f"Cannot get stream (HTTP {response.status_code}): {response.text}")
        for line in response.iter_lines():
            if line:
                tweets.append(json.loads(line))
                if len(tweets) >= limit:
                    break
    
    return tweets

def delete_all_rules():
    url = "https://api.twitter.com/2/tweets/search/stream/rules"
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Cannot get rules (HTTP {response.status_code}): {response.text}")
    
    data = response.json()
    rules = data.get("data", [])
    ids = [rule["id"] for rule in rules]
    
    if ids:
        payload = {"delete": {"ids": ids}}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Cannot delete rules (HTTP {response.status_code}): {response.text}")

def get_stream_past(limit=5):
    querystring = {"query":"elon"}
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }

    tweets = []
    with requests.get(url, headers=headers, params=querystring, stream=True) as response:
        if response.status_code != 200:
            raise Exception(f"Cannot get stream (HTTP {response.status_code}): {response.text}")
        for line in response.iter_lines():
            if line:
                tweets.append(json.loads(line))
                if len(tweets) >= limit:
                    break
    
    return tweets

if __name__ == "__main__":
    # set_rules(["elon", "tesla", "spacex"])
    tweets = get_stream_past()
    print(tweets)
    # delete_all_rules()
