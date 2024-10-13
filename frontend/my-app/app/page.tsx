"use client"
import { useEffect, useState, useRef } from "react";
import { Tweet } from 'react-tweet'
import Box from '../components/Box';

export default function Home() {
  const [tweets, setTweets] = useState<{ id: string; text: string }[]>([]);
  const [transcriptions, setTranscriptions] = useState<string[]>([]);
  const transcriptionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('http://localhost:5001/get_data');
        const data = await response.json();
        console.log(data);
        
        // Append new transcription if it's different from the last one
        setTranscriptions(prev => {
          if (prev.length === 0 || data.transcript !== prev[prev.length - 1]) {
            const newTranscriptions = [...prev, data.transcript];
            // Keep only the last 10 transcriptions
            return newTranscriptions.slice(-10);
          }
          return prev;
        });
        
        setTweets(data.tweets);
      } catch (error) {
        console.error('There was a problem with the fetch operation:', error);
      }
    };

    const intervalId = setInterval(fetchData, 500); // Update more frequently

    return () => clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (transcriptionRef.current) {
      transcriptionRef.current.scrollTop = transcriptionRef.current.scrollHeight;
    }
  }, [transcriptions]);

  return (
    <div className="container mx-auto px-4 py-8 bg-gray-900 text-white">
      <header className="text-center mb-8">
        <h1 className="text-4xl font-bold text-blue-400">X spaces Simulation</h1>
      </header>
      <main className="flex flex-col md:flex-row gap-8">
        <Box title="Live Transcription">
          <div ref={transcriptionRef} className="space-y-2">
            {transcriptions.map((transcript, index) => (
              <p key={index} className="text-lg whitespace-pre-wrap text-gray-200">
                {transcript}
              </p>
            ))}
            {transcriptions.length === 0 && (
              <p className="text-lg text-gray-400">Waiting for transcription...</p>
            )}
          </div>
        </Box>
        <Box title="Related Tweets">
          <div className="space-y-4 pr-2">
            {tweets.map((tweet, index) => (
              <div key={index} className="bg-gray-700 rounded-lg shadow border border-gray-600">
                <Tweet id={tweet.id} />
              </div>
            ))}
          </div>
        </Box>
      </main>
    </div>
  );
}
