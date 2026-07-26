import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUp, Loader2, Mic } from "lucide-react";
import Tooltip from "../Tooltip/Tooltip.jsx";

const MAX_TEXTAREA_HEIGHT_PX = 160;

/**
 * Message composer. Enter sends, Shift+Enter inserts a newline. Textarea
 * grows with content up to a max height, then scrolls. Mic + send live
 * together inside one rounded pill, matching the layout ChatGPT/Claude
 * use — a single unified composer rather than a separate external button.
 *
 * @param {(text: string) => void} onSend
 * @param {boolean} isLoading
 * @param {() => void} onMicClick
 * @param {boolean} [isRecording] - live voice turn in progress
 * @param {boolean} [isConnecting] - voice socket/mic permission still opening
 * @param {boolean} [isProcessingVoice] - utterance sent, reply not back yet — distinct
 *   from isRecording so a several-second reply doesn't look like nothing happened
 * @param {string} [interimTranscript] - live (not-yet-final) speech-to-text preview
 */
function ChatInput({
  onSend,
  isLoading,
  onMicClick,
  isRecording = false,
  isConnecting = false,
  isProcessingVoice = false,
  interimTranscript = "",
}) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef(null);

  const resizeTextarea = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
  };

  const handleChange = (e) => {
    setValue(e.target.value);
    resizeTextarea();
  };

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setValue("");
    requestAnimationFrame(resizeTextarea);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = value.trim().length > 0 && !isLoading;

  return (
    <div className="glass border-t border-line px-4 py-4 sm:px-6">
      <div className="mx-auto max-w-chat">
        <div
          className={`flex items-end gap-2 rounded-[26px] border bg-surface py-2 pl-5 pr-2 shadow-sm transition duration-200 ${
            focused ? "border-red/50 shadow-glow" : "border-line"
          }`}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            rows={1}
            enterKeyHint="send"
            placeholder={
              isProcessingVoice
                ? "Thinking…"
                : isRecording
                  ? interimTranscript || "Listening…"
                  : "Ask anything about LocalButcher…"
            }
            disabled={isLoading || isRecording || isProcessingVoice}
            aria-label="Message"
            className="
              max-h-40 flex-1 resize-none self-center bg-transparent py-1.5 text-sm sm:text-base
              text-ink placeholder:text-ink-soft placeholder:truncate
              focus:outline-none disabled:opacity-60
            "
          />

          <div className="flex shrink-0 items-center gap-1">
            <Tooltip
              label={
                isProcessingVoice
                  ? "Thinking…"
                  : isConnecting
                    ? "Connecting…"
                    : isRecording
                      ? "Stop voice input"
                      : "Speak your message"
              }
              align="end"
            >
              <motion.button
                type="button"
                onClick={onMicClick}
                disabled={isConnecting || isProcessingVoice}
                whileTap={{ scale: 0.92 }}
                aria-label={isRecording ? "Stop voice input" : "Speak your message"}
                aria-pressed={isRecording}
                className={`
                  flex h-10 w-10 items-center justify-center rounded-full
                  transition duration-200 focus-visible:outline-none
                  disabled:cursor-not-allowed
                  ${
                    isRecording
                      ? "animate-pulse-dot bg-red text-white"
                      : isProcessingVoice
                        ? "text-red"
                        : "text-ink-soft hover:bg-line/60 hover:text-red disabled:opacity-60"
                  }
                `}
              >
                {isProcessingVoice ? (
                  <Loader2 size={18} strokeWidth={2} className="animate-spin" />
                ) : (
                  <Mic size={18} strokeWidth={2} />
                )}
              </motion.button>
            </Tooltip>

            <Tooltip label="Send message" align="end">
              <motion.button
                type="button"
                onClick={handleSend}
                disabled={!canSend}
                whileHover={canSend ? { y: -1 } : undefined}
                whileTap={canSend ? { scale: 0.92 } : undefined}
                aria-label="Send message"
                className={`
                  sheen flex h-10 w-10 shrink-0 items-center justify-center rounded-full
                  transition duration-200
                  ${
                    canSend
                      ? "bg-red-gradient text-white shadow-glow hover:shadow-glow-lg"
                      : "cursor-not-allowed bg-line text-ink-soft"
                  }
                `}
              >
                <ArrowUp size={17} strokeWidth={2.5} />
              </motion.button>
            </Tooltip>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatInput;
