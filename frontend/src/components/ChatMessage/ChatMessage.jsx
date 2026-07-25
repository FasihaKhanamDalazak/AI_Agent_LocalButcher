import { useState } from "react";
import { motion } from "framer-motion";
import { Check, ChefHat, Copy } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import FollowUpChips from "../FollowUpChips/FollowUpChips.jsx";
import Tooltip from "../Tooltip/Tooltip.jsx";
import { formatTimestamp } from "../../utils/helpers.js";
import { MESSAGE_ROLES } from "../../utils/constants.js";

/**
 * Renders a single message: user bubbles right-aligned, assistant
 * replies left-aligned with its avatar, a timestamp, a copy action,
 * and any follow-up chips attached to that reply.
 *
 * @param {object} message - { id, role, text, timestamp, followUps?, isError?, isRateLimited? }
 * @param {(question: string) => void} onFollowUpSelect
 */
function ChatMessage({ message, onFollowUpSelect }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === MESSAGE_ROLES.USER;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable — non-critical, fail silently.
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`flex items-start gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {!isUser && (
        <span
          className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-gradient text-white shadow-sm"
          aria-hidden="true"
        >
          <ChefHat size={17} strokeWidth={2} />
        </span>
      )}

      <div
        className={`flex max-w-[80%] flex-col sm:max-w-[70%] ${isUser ? "items-end" : "items-start"}`}
      >
        <div
          className={`group relative rounded-card border px-5 py-3.5 text-[15px] leading-relaxed shadow-sm transition duration-200 hover:shadow-card ${
            isUser
              ? "border-line bg-surface shadow-sm"
              : message.isError
                ? message.isRateLimited
                  ? "border-gold/40 bg-gold/[0.08]"
                  : "border-error/30 bg-surface"
                : "border-line bg-surface"
          }`}
        >
          {isUser || message.isError ? (
            <p
              className={`whitespace-pre-wrap ${
                message.isError
                  ? message.isRateLimited
                    ? "text-brown"
                    : "text-error"
                  : "text-ink"
              }`}
            >
              {message.text}
            </p>
          ) : (
            <div className="markdown-answer text-ink">
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {message.text}
              </ReactMarkdown>
            </div>
          )}

          {!isUser && !message.isError && (
            <Tooltip label={copied ? "Copied!" : "Copy"}>
              <button
                type="button"
                onClick={handleCopy}
                aria-label="Copy response"
                className="
                  absolute -bottom-2 -right-2 flex h-7 w-7 items-center justify-center
                  rounded-full border border-line bg-surface text-ink-soft
                  opacity-0 shadow-sm transition duration-200
                  hover:text-red group-hover:opacity-100
                  focus-visible:opacity-100
                "
              >
                {copied ? <Check size={13} /> : <Copy size={13} />}
              </button>
            </Tooltip>
          )}
        </div>

        <span className="mt-1.5 px-1 text-xs text-ink-soft">
          {formatTimestamp(message.timestamp)}
        </span>

        {!isUser && (
          <FollowUpChips followUps={message.followUps} onSelect={onFollowUpSelect} />
        )}
      </div>
    </motion.div>
  );
}

export default ChatMessage;