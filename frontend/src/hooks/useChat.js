import { useCallback, useEffect, useRef, useState } from "react";
import { getGreeting, sendChatMessage } from "../services/api.js";
import { generateId } from "../utils/helpers.js";
import { MESSAGE_ROLES } from "../utils/constants.js";

/**
 * Encapsulates all chat state and behavior for the current session:
 * - one conversation_id, assigned by the backend on the first greeting
 *   call and reused for every message after (text AND voice both feed
 *   the same conversation — see useVoiceChat, which takes conversationId
 *   from here rather than managing its own).
 * - message history (user + assistant)
 * - loading / error state
 *
 * Every app load starts a fresh conversation (calls GET /chat/greeting)
 * — the backend has no "resume last conversation" endpoint yet, and that
 * was a deliberate scope decision, not an oversight.
 *
 * Components stay purely presentational; all logic lives here.
 */
export function useChat() {
  const conversationIdRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGreeting, setIsGreeting] = useState(true);
  const [error, setError] = useState(null);

  const startConversation = useCallback(async () => {
    setIsGreeting(true);
    setError(null);
    try {
      const { conversationId, greeting, followUps } = await getGreeting();
      conversationIdRef.current = conversationId;
      setMessages([
        {
          id: generateId(),
          role: MESSAGE_ROLES.ASSISTANT,
          text: greeting,
          followUps: followUps ?? [],
          timestamp: new Date(),
        },
      ]);
    } catch (err) {
      setError(err.message);
      setMessages([
        {
          id: generateId(),
          role: MESSAGE_ROLES.ASSISTANT,
          text: err.message,
          followUps: [],
          timestamp: new Date(),
          isError: true,
          isRateLimited: Boolean(err.isRateLimited),
        },
      ]);
    } finally {
      setIsGreeting(false);
    }
  }, []);

  useEffect(() => {
    startConversation();
    // Deliberately run once on mount — see startConversation's own note
    // about always starting fresh, not on every re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Appends a message that originated elsewhere (e.g. a voice turn) without re-sending it to the backend. */
  const appendMessage = useCallback((message) => {
    setMessages((prev) => [...prev, { id: generateId(), timestamp: new Date(), followUps: [], ...message }]);
  }, []);

  const sendMessage = useCallback(async (rawText) => {
    const text = rawText.trim();
    if (!text) return;

    setError(null);

    const userMessage = {
      id: generateId(),
      role: MESSAGE_ROLES.USER,
      text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const { conversationId, reply, followUps } = await sendChatMessage(text, conversationIdRef.current);
      conversationIdRef.current = conversationId;

      const assistantMessage = {
        id: generateId(),
        role: MESSAGE_ROLES.ASSISTANT,
        text: reply,
        followUps: followUps ?? [],
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err.message);

      const errorMessage = {
        id: generateId(),
        role: MESSAGE_ROLES.ASSISTANT,
        text: err.message,
        followUps: [],
        timestamp: new Date(),
        isError: true,
        isRateLimited: Boolean(err.isRateLimited),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const resetChat = useCallback(() => {
    startConversation();
  }, [startConversation]);

  /** Lets useVoiceChat report the conversation_id a voice turn resolved to, keeping text and voice on one shared conversation. */
  const setConversationId = useCallback((id) => {
    conversationIdRef.current = id;
  }, []);

  return {
    conversationId: conversationIdRef.current,
    getConversationId: () => conversationIdRef.current,
    setConversationId,
    messages,
    isLoading,
    isGreeting,
    error,
    sendMessage,
    appendMessage,
    resetChat,
  };
}
