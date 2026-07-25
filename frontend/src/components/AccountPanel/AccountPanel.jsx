import { LogOut, Mail, Phone, User as UserIcon } from "lucide-react";
import SlideOver from "../SlideOver/SlideOver.jsx";
import { useAuth } from "../../context/AuthContext.jsx";

function AccountPanel({ isOpen, onClose }) {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    onClose();
  };

  return (
    <SlideOver isOpen={isOpen} onClose={onClose} title="Account" icon={UserIcon}>
      {user && (
        <div className="flex flex-col gap-3">
          <div className="rounded-card border border-line bg-cream/40 p-5">
            <p className="font-display text-lg font-bold text-ink">{user.name}</p>
            <div className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
              <Mail size={14} /> {user.email}
            </div>
            {user.phone && (
              <div className="mt-1.5 flex items-center gap-2 text-sm text-ink-soft">
                <Phone size={14} /> {user.phone}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="
              flex items-center justify-center gap-2 rounded-button border border-error/30
              px-5 py-3 text-sm font-semibold text-error transition duration-200
              hover:bg-error/[0.06]
            "
          >
            <LogOut size={16} /> Log out
          </button>
        </div>
      )}
    </SlideOver>
  );
}

export default AccountPanel;
