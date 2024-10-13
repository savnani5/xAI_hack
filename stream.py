import os
import asyncio
import json
import pyaudio
import websockets
from dotenv import load_dotenv
import aiohttp
import requests
from flask import Flask, request, jsonify
from threading import Thread
from collections import deque
from flask_cors import CORS  # Add this import
load_dotenv()

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 16000

class AudioProcessor:
    def __init__(self):
        self.grok_api_key = os.getenv("GROK_API_KEY")
        self.dg_api_key = os.getenv("DG_API_KEY")
        self.deepgram_url = f"wss://api.deepgram.com/v1/listen?punctuate=true&encoding=linear16&sample_rate={RATE}"
        self.audio_queue = asyncio.Queue()
        self.transcript_queue = asyncio.Queue()
        self.keyword_queue = asyncio.Queue()
        self.transcript_buffer = ""
        self.min_chunk_size = 100  # Minimum number of characters before processing
        self.BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
        self.flask_app = Flask(__name__)
        CORS(self.flask_app)  # Enable CORS for all routes
        self.data_queue = deque(maxlen=10)  # Store last 10 data points
        self.setup_flask_routes()

    async def process_deepgram_stream(self, websocket):
        async for message in websocket:
            data = json.loads(message)
            if data.get("is_final"):
                transcript = data.get("channel", {}).get("alternatives", [{}])[0].get("transcript", "")
                if transcript:
                    await self.transcript_queue.put(transcript)

    async def connect_to_deepgram(self):
        async with websockets.connect(
            self.deepgram_url,
            extra_headers={"Authorization": f"Token {self.dg_api_key}"}
        ) as websocket:
            receive_task = asyncio.create_task(self.process_deepgram_stream(websocket))
            send_task = asyncio.create_task(self.send_audio(websocket))
            
            print("Starting real-time capture and transcription...")

            try:
                await asyncio.gather(receive_task, send_task)
            except KeyboardInterrupt:
                print("Stopping capture...")
            finally:
                receive_task.cancel()
                send_task.cancel()

    async def send_audio(self, websocket):
        while True:
            audio_data = await self.audio_queue.get()
            await websocket.send(audio_data)

    def mic_callback(self, input_data, frame_count, time_info, status_flag):
        self.audio_queue.put_nowait(input_data)
        return (input_data, pyaudio.paContinue)

    async def capture_audio(self):
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            stream_callback=self.mic_callback,
        )

        stream.start_stream()

        try:
            while stream.is_active():
                await asyncio.sleep(0.1)
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    async def process_transcripts(self):
        while True:
            transcript = await self.transcript_queue.get()
            print(f"Transcript: {transcript}")
            
            self.transcript_buffer += transcript + " "
            
            if len(self.transcript_buffer) >= self.min_chunk_size:
                keywords = await self.generate_keywords(self.transcript_buffer)
                await self.keyword_queue.put(keywords)
                print(f"Keywords: {keywords}")
                
                # Get tweets based on keywords
                tweets = await self.get_stream_past(keywords)
                
                # Display transcript and tweets
                print("\n--- Transcript and Related Tweets ---")
                print(f"Transcript: {self.transcript_buffer}")
                print("Related Tweets:")
                for tweet in tweets:
                    print(f"- {tweet['text']}")
                print("-----------------------------------\n")
                
                # Send POST request to Flask server
                await self.send_data_to_flask(self.transcript_buffer, tweets)
                
                self.transcript_buffer = ""  # Reset the buffer after processing

    async def send_data_to_flask(self, transcript, tweets):
        self.data_queue.append({
            "transcript": transcript,
            "tweets": [{"id": tweet['id'], "text": tweet['text']} for tweet in tweets]
        })

    def setup_flask_routes(self):
        @self.flask_app.route('/get_data', methods=['GET'])
        def get_data():
            if self.data_queue:
                return jsonify(self.data_queue[-1]), 200
            else:
                return jsonify({"transcript": "", "tweets": []}), 200

    def run_flask_server(self):
        self.flask_app.run(host='127.0.0.1', port=5001)

    async def create_chat_completion(self, messages):
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.grok_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        data = {
            "messages": messages,
            "model": "grok-2-public",
            "stream": True,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        line = line[6:]
                    if line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0]["delta"]
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        pass

    async def generate_keywords(self, transcript):
        print(f"Generating keywords using Grok API for chunk of size {len(transcript)}...")
        
        conversation = [{"role": "system", "content": "You are an AI assistant that generates relevant keywords from a given transcript."}]
        user_input = f"Generate 2-3 relevant keywords or key phrases from the following transcript. Provide only the keywords, separated by commas:\n\n{transcript}"
        conversation.append({"role": "user", "content": user_input})
        
        full_response = ""
        async for token in self.create_chat_completion(conversation):
            full_response += token
        
        # Extract keywords from the response
        keywords = [kw.strip() for kw in full_response.split(',')]
        return ", ".join(keywords)

    async def get_stream_past(self, keywords, limit=10):
        query = " OR ".join(keywords.split(", "))
        querystring = {"query": query, "max_results": str(limit)}
        url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {
            "Authorization": f"Bearer {self.BEARER_TOKEN}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=querystring) as response:
                if response.status != 200:
                    raise Exception(f"Cannot get stream (HTTP {response.status}): {await response.text()}")
                data = await response.json()
                return data.get('data', [])

    async def run(self):
        # Start Flask server in a separate thread
        flask_thread = Thread(target=self.run_flask_server)
        flask_thread.start()

        tasks = [
            self.capture_audio(),
            self.connect_to_deepgram(),
            self.process_transcripts()
        ]
        await asyncio.gather(*tasks)

async def main():
    processor = AudioProcessor()
    await processor.run()

if __name__ == "__main__":
    asyncio.run(main())
