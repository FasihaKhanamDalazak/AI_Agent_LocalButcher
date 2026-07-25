import { useCallback, useEffect, useRef, useState } from "react";
import Header from "../components/Header/Header.jsx";
import Hero from "../components/Hero/Hero.jsx";
import ChatInput from "../components/ChatInput/ChatInput.jsx";
import ChatContainer from "../components/ChatContainer/ChatContainer.jsx";
import CartPanel from "../components/CartPanel/CartPanel.jsx";
import OrdersPanel from "../components/OrdersPanel/OrdersPanel.jsx";
import AddressesPanel from "../components/AddressesPanel/AddressesPanel.jsx";
import AccountPanel from "../components/AccountPanel/AccountPanel.jsx";
import { useChat } from "../hooks/useChat.js";
import { useVoiceChat } from "../hooks/useVoiceChat.js";

// How close to the bottom (px) the user must be for new messages to
// auto-scroll. Beyond this, we assume they're deliberately reading back
// through history and leave their scroll position alone.
const AUTO_SCROLL_THRESHOLD_PX = 120;

/**
 * Top-level chat page. The Hero (headline + starter chips) stays visible
 * above the conversation permanently, rather than clearing away once
 * chatting starts. ChatInput is docked at the bottom of the viewport;
 * Hero and the conversation scroll together in the space above it.
 */
function ChatPage() {
  const { messages, isLoading, isGreeting, sendMessage, resetChat, conversationId, setConversationId, appendMessage } =
    useChat();
  const [openPanel, setOpenPanel] = useState(null); // "cart" | "orders" | "addresses" | "account" | null

  const voice = useVoiceChat({ conversationId, setConversationId, appendMessage });

  const scrollContainerRef = useRef(null);
  const bottomRef = useRef(null);
  const shouldAutoScroll = useRef(true);

  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldAutoScroll.current = distanceFromBottom < AUTO_SCROLL_THRESHOLD_PX;
  }, []);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (shouldAutoScroll.current && el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isLoading]);

  // Surface voice-connection errors (mic denied, socket dropped, etc.) the
  // same way a failed text send shows up — an error-styled assistant bubble
  // — rather than a separate toast system just for this one path.
  useEffect(() => {
    if (voice.error) {
      appendMessage({ role: "assistant", text: voice.error, isError: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voice.error]);

  // Logo click: start a brand-new conversation and scroll up.
  const handleLogoClick = useCallback(() => {
    resetChat();
    shouldAutoScroll.current = true;
    scrollContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [resetChat]);

  const showConversation = messages.length > 0 || isLoading || isGreeting;

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden bg-background">
      {/* Ambient animated background — matches localbutcher.com's .bg-fx */}
      <div className="bg-fx" aria-hidden="true">
        <div className="bg-fx__glow bg-fx__glow--red" />
        <div className="bg-fx__glow bg-fx__glow--brown" />
        <div className="bg-fx__grain" />
      </div>

      <div className="relative z-10 flex h-full flex-col">
        <Header onLogoClick={handleLogoClick} onOpenPanel={setOpenPanel} />

        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="scrollbar-elegant flex-1 overflow-y-auto"
        >
          <Hero onStarterSelect={sendMessage} chipsDisabled={isGreeting} />

          {showConversation && (
            <ChatContainer
              messages={messages}
              isLoading={isLoading || isGreeting}
              onFollowUpSelect={sendMessage}
            />
          )}

          <div ref={bottomRef} />
        </div>

        <ChatInput
          onSend={sendMessage}
          isLoading={isLoading || isGreeting}
          onMicClick={voice.toggleRecording}
          isRecording={voice.isRecording}
          isConnecting={voice.isConnecting}
          interimTranscript={voice.interimTranscript}
        />
      </div>

      <CartPanel isOpen={openPanel === "cart"} onClose={() => setOpenPanel(null)} />
      <OrdersPanel isOpen={openPanel === "orders"} onClose={() => setOpenPanel(null)} />
      <AddressesPanel isOpen={openPanel === "addresses"} onClose={() => setOpenPanel(null)} />
      <AccountPanel isOpen={openPanel === "account"} onClose={() => setOpenPanel(null)} />
    </div>
  );
}

export default ChatPage;
