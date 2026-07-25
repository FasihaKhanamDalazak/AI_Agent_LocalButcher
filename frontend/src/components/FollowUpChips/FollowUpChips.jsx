import { motion } from "framer-motion";
import SuggestedChips from "../SuggestedChips/SuggestedChips.jsx";

/**
 * Follow-up chips beneath an assistant reply. Renders nothing when follow_ups
 * is empty — that's intentional for off-topic redirects, not a bug.
 *
 * @param {string[]} followUps
 * @param {(question: string) => void} onSelect
 */
function FollowUpChips({ followUps, onSelect }) {
  if (!followUps?.length) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.15 }}
      className="mt-3 flex justify-start"
    >
      <SuggestedChips chips={followUps} onSelect={onSelect} align="start" />
    </motion.div>
  );
}

export default FollowUpChips;