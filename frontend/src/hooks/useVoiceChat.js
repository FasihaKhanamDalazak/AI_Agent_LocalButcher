import { useCallback, useRef, useState } from "react";
import { getToken } from "../utils/authStorage.js";
import { MESSAGE_ROLES } from "../utils/constants.js";

const WS_BASE_URL = import.meta.env.VITE_WS_URL;
const TARGET_SAMPLE_RATE = 16000;
// Matches voice_service.open_transcription_stream on the backend — raw
// linear16 PCM, 16kHz, mono, no container/header (not WAV frames).
const PROCESSOR_BUFFER_SIZE = 4096;

function floatTo16BitPCM(float32Array) {
  const out = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

/**
 * Real-time voice conversation over WS /api/v1/chat/voice/stream — same
 * agent, same conversation, as text chat (see useChat's conversationId /
 * setConversationId, which this hook reads from and writes back to so a
 * customer can freely switch between typing and talking mid-conversation).
 *
 * Push-to-talk, one turn per connection: the mic stops capturing the
 * moment the backend confirms it heard a complete utterance
 * (final_transcript) rather than staying open for the whole visit — both
 * because leaving a mic capturing indefinitely after the customer's done
 * talking is bad practice, and because "still listening" with no other
 * feedback is exactly what read as "nothing happened" when a reply
 * actually takes several seconds (tool call + generation) to arrive. The
 * WS itself stays open just long enough to receive that reply, then
 * closes — the NEXT tap opens a fresh connection, continuing the same
 * conversation via conversationId (see voice_service._load_agent_history
 * on the backend), not starting over.
 *
 * Mic capture uses a ScriptProcessorNode rather than an AudioWorklet —
 * deprecated but universally supported without shipping a separate
 * worklet module, and simplicity was the explicit call made for every
 * other "good enough vs. state of the art" tradeoff in this project
 * (see backend/CLAUDE.md's voice layer notes).
 *
 * @param {{conversationId: string|null, setConversationId: (id: string) => void, appendMessage: (msg: object) => void}} deps
 */
export function useVoiceChat({ conversationId, setConversationId, appendMessage }) {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  // True from the moment the mic stops (final_transcript) until the reply
  // arrives — the "thinking" state ChatInput shows distinctly from
  // "still listening", so a several-second wait doesn't look like nothing
  // is happening.
  const [isProcessing, setIsProcessing] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const sourceRef = useRef(null);
  const streamRef = useRef(null);

  // Tears down mic capture only — NOT the WebSocket, which needs to stay
  // open a little longer to receive the pending reply. Safe to call
  // multiple times (e.g. also from the full cleanup below).
  const stopMicCapture = useCallback(() => {
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    processorRef.current = null;
    sourceRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close();
    }
    audioContextRef.current = null;
  }, []);

  const cleanup = useCallback(() => {
    stopMicCapture();

    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      wsRef.current.close();
    }
    wsRef.current = null;

    setIsRecording(false);
    setIsConnecting(false);
    setIsProcessing(false);
    setInterimTranscript("");
  }, [stopMicCapture]);

  const stop = useCallback(() => {
    cleanup();
  }, [cleanup]);

  const start = useCallback(async () => {
    if (!WS_BASE_URL) {
      setError("Voice isn't configured (VITE_WS_URL is missing).");
      return;
    }

    setError(null);
    setIsConnecting(true);

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone access was denied.");
      setIsConnecting(false);
      return;
    }
    streamRef.current = stream;

    const token = getToken();
    const params = new URLSearchParams({ token: token ?? "" });
    if (conversationId) params.set("conversation_id", conversationId);
    const ws = new WebSocket(`${WS_BASE_URL}/api/v1/chat/voice/stream?${params.toString()}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnecting(false);
      setIsRecording(true);

      const audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: TARGET_SAMPLE_RATE,
      });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioContext.createScriptProcessor(PROCESSOR_BUFFER_SIZE, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const pcm16 = floatTo16BitPCM(e.inputBuffer.getChannelData(0));
        ws.send(pcm16.buffer);
      };

      source.connect(processor);
      // A ScriptProcessorNode only fires while connected into the graph's
      // output — a muted, zero-gain sink avoids audibly looping the mic
      // back through the speakers while still driving onaudioprocess.
      const silentSink = audioContext.createGain();
      silentSink.gain.value = 0;
      processor.connect(silentSink);
      silentSink.connect(audioContext.destination);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      switch (data.type) {
        case "interim_transcript":
          setInterimTranscript(data.text);
          break;
        case "final_transcript":
          // Mic's job is done — stop capturing immediately and switch to
          // a distinct "processing" state while the reply is generated,
          // rather than staying visually "still listening".
          stopMicCapture();
          setIsRecording(false);
          setIsProcessing(true);
          setInterimTranscript("");
          appendMessage({ role: MESSAGE_ROLES.USER, text: data.text });
          break;
        case "assistant_reply":
          setConversationId(data.conversation_id);
          appendMessage({ role: MESSAGE_ROLES.ASSISTANT, text: data.text });
          if (data.audio_base64) {
            new Audio(`data:audio/wav;base64,${data.audio_base64}`).play().catch(() => {});
          }
          // This turn is complete — close out. The next tap opens a fresh
          // connection for the next turn (see hook-level doc comment).
          cleanup();
          break;
        case "error":
          setError(data.message);
          break;
        default:
          break;
      }
    };

    ws.onerror = () => {
      setError("Voice connection failed.");
    };

    ws.onclose = (event) => {
      if (event.code === 4401) setError("Your session has expired — please log in again.");
      else if (event.code === 4429) setError("Too many voice connections — slow down a moment.");
      cleanup();
    };
  }, [conversationId, setConversationId, appendMessage, cleanup, stopMicCapture]);

  const toggleRecording = useCallback(() => {
    if (isProcessing) return; // a reply is already on the way — nothing to toggle until it lands
    if (isRecording || isConnecting) stop();
    else start();
  }, [isRecording, isConnecting, isProcessing, start, stop]);

  return { isRecording, isConnecting, isProcessing, interimTranscript, error, toggleRecording };
}
