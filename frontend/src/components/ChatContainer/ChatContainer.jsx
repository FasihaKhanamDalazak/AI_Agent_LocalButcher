import { AnimatePresence } from "framer-motion";
import ChatMessage from "../ChatMessage/ChatMessage.jsx";
import LoadingMessage from "../LoadingMessage/LoadingMessage.jsx";

/**
 * Renders the conversation beneath the (permanent) Hero. Scrolling and
 * auto-scroll-to-latest are owned by the page-level scroll container —
 * this component is purely presentational.
 *
 * @param {object[]} messages
 * @param {boolean} isLoading
 * @param {(question: string) => void} onFollowUpSelect
 */
function ChatContainer({ messages, isLoading, onFollowUpSelect }) {
  return (
    <div className="mx-auto flex max-w-chat flex-col gap-5 px-6 pb-10 sm:px-8">
      <AnimatePresence initial={false}>
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            onFollowUpSelect={onFollowUpSelect}
          />
        ))}
        {isLoading && <LoadingMessage key="loading" />}
      </AnimatePresence>
    </div>
  );
}

export default ChatContainer;
