import { useCallback, useEffect, useState } from "react";
import { Loader2, MapPin, Pencil, Plus, Star, Trash2, X } from "lucide-react";
import SlideOver from "../SlideOver/SlideOver.jsx";
import TextField from "../TextField/TextField.jsx";
import * as api from "../../services/api.js";

const EMPTY_FORM = { label: "", addressText: "" };

/**
 * Address book. Deliberately text-only — no lat/lng inputs — matching the
 * backend's own stance (see backend/CLAUDE.md: chat never sets
 * coordinates either) that there's no geocoding in this project, so a
 * free-text address is the honest shape for this data, not a placeholder
 * for a map picker that doesn't exist.
 */
function AddressesPanel({ isOpen, onClose }) {
  const [addresses, setAddresses] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const [editingId, setEditingId] = useState(null); // "new" | address id | null
  const [form, setForm] = useState(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setAddresses(await api.listAddresses());
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) load();
    else {
      setEditingId(null);
      setForm(EMPTY_FORM);
    }
  }, [isOpen, load]);

  const startAdd = () => {
    setForm(EMPTY_FORM);
    setEditingId("new");
  };

  const startEdit = (address) => {
    setForm({ label: address.label, addressText: address.address_text });
    setEditingId(address.id);
  };

  const cancelForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      if (editingId === "new") {
        await api.createAddress({ label: form.label, addressText: form.addressText });
      } else {
        await api.updateAddress(editingId, { label: form.label, addressText: form.addressText });
      }
      await load();
      cancelForm();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (id) => {
    setBusyId(id);
    setError(null);
    try {
      await api.deleteAddress(id);
      setAddresses((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleSetDefault = async (address) => {
    setBusyId(address.id);
    setError(null);
    try {
      await api.updateAddress(address.id, { isDefault: true });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <SlideOver isOpen={isOpen} onClose={onClose} title="Your addresses" icon={MapPin}>
      {error && (
        <div className="mb-4 rounded-card-sm border border-error/30 bg-error/[0.06] px-4 py-2.5 text-sm text-error">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-16 text-ink-soft">
          <Loader2 size={22} className="animate-spin" />
        </div>
      )}

      {!isLoading && (
        <>
          <ul className="mb-4 flex flex-col gap-3">
            {addresses.map((address) => (
              <li key={address.id} className="rounded-card-sm border border-line bg-cream/40 p-4">
                <div className="mb-1 flex items-center gap-2">
                  <p className="text-sm font-semibold text-ink">{address.label}</p>
                  {address.is_default && (
                    <span className="rounded-chip bg-gold/15 px-2 py-0.5 text-[11px] font-semibold text-brown">
                      Default
                    </span>
                  )}
                </div>
                <p className="mb-3 text-sm text-ink-soft">{address.address_text}</p>
                <div className="flex items-center gap-4 text-xs font-semibold">
                  {!address.is_default && (
                    <button
                      type="button"
                      disabled={busyId === address.id}
                      onClick={() => handleSetDefault(address)}
                      className="flex items-center gap-1 text-ink-soft transition hover:text-gold disabled:opacity-40"
                    >
                      <Star size={12} /> Set default
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => startEdit(address)}
                    className="flex items-center gap-1 text-ink-soft transition hover:text-red"
                  >
                    <Pencil size={12} /> Edit
                  </button>
                  <button
                    type="button"
                    disabled={busyId === address.id}
                    onClick={() => handleDelete(address.id)}
                    className="flex items-center gap-1 text-ink-soft transition hover:text-error disabled:opacity-40"
                  >
                    <Trash2 size={12} /> Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>

          {editingId ? (
            <form
              onSubmit={handleSave}
              className="flex flex-col gap-3 rounded-card-sm border border-line bg-surface p-4"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-ink">
                  {editingId === "new" ? "New address" : "Edit address"}
                </p>
                <button type="button" onClick={cancelForm} aria-label="Cancel" className="text-ink-soft hover:text-ink">
                  <X size={16} />
                </button>
              </div>
              <TextField
                label="Label"
                value={form.label}
                onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
                placeholder="Home, Office…"
                required
                maxLength={50}
              />
              <TextField
                label="Address"
                value={form.addressText}
                onChange={(e) => setForm((f) => ({ ...f, addressText: e.target.value }))}
                placeholder="Flat, street, area, city"
                required
                maxLength={500}
              />
              <button
                type="submit"
                disabled={isSaving}
                className="sheen rounded-button bg-red-gradient px-5 py-2.5 text-sm font-semibold text-white shadow-glow transition duration-200 hover:shadow-glow-lg disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSaving ? "Saving…" : "Save address"}
              </button>
            </form>
          ) : (
            <button
              type="button"
              onClick={startAdd}
              className="flex w-full items-center justify-center gap-2 rounded-button border border-dashed border-line py-3 text-sm font-medium text-ink-soft transition hover:border-red/40 hover:text-red"
            >
              <Plus size={15} /> Add address
            </button>
          )}
        </>
      )}
    </SlideOver>
  );
}

export default AddressesPanel;
