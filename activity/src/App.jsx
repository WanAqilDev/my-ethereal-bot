import React, { useState, useEffect, useRef } from 'react'
import io from 'socket.io-client'
import { DiscordSDK } from "@discord/embedded-app-sdk";

// Mock SDK if outside Discord
const discordSdk = new DiscordSDK(import.meta.env.VITE_DISCORD_CLIENT_ID || "1234567890");

const socket = io({
  path: '/socket.io',
  transports: ['websocket'],
  autoConnect: false
});

function App() {
  const [session, setSession] = useState(null);
  const [sessionIdInput, setSessionIdInput] = useState("");
  const [status, setStatus] = useState("Disconnected");
  const [videoUrl, setVideoUrl] = useState("");
  const videoRef = useRef(null);

  useEffect(() => {
    async function setupDiscord() {
        try {
            await discordSdk.ready();
            // Authorize
            const { code } = await discordSdk.commands.authorize({
                client_id: import.meta.env.VITE_DISCORD_CLIENT_ID,
                response_type: "code",
                state: "",
                prompt: "none",
                scope: [
                    "identify",
                    "guilds",
                ],
            });
            // Authenticate with backend
            // const response = await fetch('/api/auth', { method: 'POST', body: JSON.stringify({ code }) })
            // ...
            setStatus("Discord Authorized");
        } catch (e) {
            console.error(e);
            setStatus("Discord SDK Error (Dev Mode?)");
        }
    }
    setupDiscord();

    socket.connect();
    socket.on('connect', () => setStatus("Socket Connected"));
    socket.on('disconnect', () => setStatus("Socket Disconnected"));
    
    socket.on('sync_video', (data) => {
        console.log("Sync Event", data);
        if (data.action === 'play') {
            setVideoUrl(data.url);
            // Auto play logic
        } else if (data.action === 'seek') {
             if (videoRef.current) videoRef.current.currentTime = data.timestamp;
        } else if (data.action === 'pause') {
             if (videoRef.current) videoRef.current.pause();
        }
    });

    return () => {
        socket.off('connect');
        socket.off('disconnect');
        socket.off('sync_video');
        socket.disconnect();
    }
  }, []);

  const joinSession = () => {
      socket.emit('join_session', { session_id: sessionIdInput });
      setSession(sessionIdInput);
  };

  return (
    <div style={{ padding: 20, textAlign: 'center' }}>
      <h1>🎬 Ethereal Cinema</h1>
      <p>Status: {status}</p>

      {!session ? (
        <div style={{ marginTop: 20 }}>
            <input 
                type="text" 
                placeholder="Enter Session ID" 
                value={sessionIdInput}
                onChange={e => setSessionIdInput(e.target.value)}
                style={{ padding: 10, borderRadius: 5, border: 'none', marginRight: 10 }}
            />
            <button 
                onClick={joinSession}
                style={{ padding: '10px 20px', borderRadius: 5, border: 'none', background: '#5865F2', color: 'white', cursor: 'pointer' }}
            >
                Join Session
            </button>
        </div>
      ) : (
        <div style={{ marginTop: 20 }}>
            <h2>Session: {session}</h2>
            {videoUrl ? (
                <div style={{ marginTop: 20 }}>
                    <p>Playing: {videoUrl}</p>
                    {/* Simple Video Tag for Demo */}
                    <video 
                        ref={videoRef}
                        src={videoUrl} 
                        controls 
                        style={{ width: '100%', maxWidth: 800, borderRadius: 10 }}
                    />
                </div>
            ) : (
                <p>Waiting for host to play video...</p>
            )}
        </div>
      )}
    </div>
  )
}

export default App
