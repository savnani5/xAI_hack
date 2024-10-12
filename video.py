import os
import subprocess
import glob
import shutil
import time
import requests
import json
from dotenv import load_dotenv
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

load_dotenv()

class VideoProcessor:
    def __init__(self):
        self.deepgram_client = DeepgramClient(os.getenv("DG_API_KEY"))
        self.grok_api_key = os.getenv("GROK_API_KEY")

    def download_video(self, source, path, quality):
        if not os.path.exists(path):
            os.makedirs(path)

        quality = quality.replace('p', '')
        
        if isinstance(source, str):  # It's a URL
            video_title = subprocess.check_output(["yt-dlp", source, "--get-title"], universal_newlines=True).strip()
            path = os.path.join(path, video_title)
            if not os.path.exists(path):
                os.mkdir(path)
            else:
                for file in os.listdir(path):
                    file_path = os.path.join(path, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            
            subprocess.run(["yt-dlp", source, "-P", path, "-S", f"res:{quality}", "--output", "%(title)s.%(ext)s"])
            print("Video downloaded successfully!")
            video_path = glob.glob(os.path.join(path, "*.*"))[0]
        else:  # It's a local file path
            video_title = os.path.splitext(os.path.basename(source))[0]
            path = os.path.join(path, video_title)
            if not os.path.exists(path):
                os.mkdir(path)
            video_path = os.path.join(path, os.path.basename(source))
            shutil.copy(source, video_path)
            print("Video copied successfully!")

        # Extract audio from the video
        audio_path = os.path.join(path, f"{video_title}.mp3")
        subprocess.run(["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", audio_path])
        print("Audio extracted successfully!")

        return video_path, audio_path, video_title

    def transcribe_audio(self, audio_path):
        print("Transcribing audio...")
        
        with open(audio_path, "rb") as file:
            buffer_data = file.read()

        payload: FileSource = {
            "buffer": buffer_data,
        }

        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True
        )

        tick = time.time()
        response = self.deepgram_client.listen.prerecorded.v("1").transcribe_file(payload, options)
        
        print(f"Transcription completed in {time.time() - tick:.2f} seconds")

        word_timings = []
        full_transcript = ''
        
        for word in response.results.channels[0].alternatives[0].words:
            word_timings.append({
                'start': word.start,
                'end': word.end,
                'word': word.word.strip().lower()
            })
            full_transcript += word.word + ' '
        
        full_transcript = full_transcript.strip()
        
        print("Audio transcribed successfully!")
        return full_transcript, word_timings

    def create_chat_completion(self, messages):
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

        with requests.post(url, headers=headers, json=data, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                    if line.strip() == "[DONE]":
                        break
                    chunk = json.loads(line)
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0]["delta"]
                        if "content" in delta:
                            yield delta["content"]

    def generate_keywords(self, transcript):
        print("Generating keywords using Grok API...")
        
        conversation = [{"role": "system", "content": "You are an AI assistant that generates relevant keywords from a given transcript."}]
        
        # Split the transcript into chunks of about 1000 characters
        chunk_size = 1000
        transcript_chunks = [transcript[i:i+chunk_size] for i in range(0, len(transcript), chunk_size)]
        
        all_keywords = []
        
        for chunk in transcript_chunks:
            user_input = f"Generate 2-3 relevant keywords or key phrases from the following transcript chunk. Provide only the keywords, separated by commas:\n\n{chunk}"
            conversation.append({"role": "user", "content": user_input})
            
            print("Grok-2: ", end="", flush=True)
            full_response = ""
            for token in self.create_chat_completion(conversation):
                print(token, end="", flush=True)
                full_response += token
            print("\n")
            
            # Extract keywords from the response
            keywords = [kw.strip() for kw in full_response.split(',')]
            all_keywords.extend(keywords)
            
            # Remove the last user message to keep the conversation focused
            conversation.pop()
        
        # Remove duplicates and join the keywords
        unique_keywords = list(dict.fromkeys(all_keywords))
        return ", ".join(unique_keywords)

def main():
    processor = VideoProcessor()

    # Example usage
    # video_path = "./downloads"
    # youtube_url = input("Enter YouTube video URL: ")
    # video_quality = input("Enter video quality (e.g., 720p, 1080p): ")
    # video_path, audio_path, video_title = processor.download_video(youtube_url, video_path, video_quality)
    audio_path = "/Users/parassavnani/Desktop/dev/xAI_hackathon/downloads/Vijeta Choudhary - 🇺🇸 BREAKING: Elon Musk's interview with Donald Trump becomes the biggest Space in X(Twitter )history with over 1.3 million+ listeners tuning in. #Trump2024/Vijeta Choudhary - 🇺🇸 BREAKING: Elon Musk's interview with Donald Trump becomes the biggest Space in X(Twitter )history with over 1.3 million+ listeners tuning in. #Trump2024.mp3"
    transcript, word_timings = processor.transcribe_audio(audio_path)

    print(f"Transcript: {transcript}...")  # Print first 100 characters of transcript
    print(f"Number of words: {len(word_timings)}")

    # Save transcript to a file
    with open("transcript.txt", "w") as f:
        f.write(transcript)

    # Read transcript from file and generate keywords
    with open("transcript.txt", "r") as f:
        file_transcript = f.read()
    
    keywords = processor.generate_keywords(file_transcript)
    if keywords:
        print(f"Generated keywords: {keywords}")

if __name__ == "__main__":
    main()
