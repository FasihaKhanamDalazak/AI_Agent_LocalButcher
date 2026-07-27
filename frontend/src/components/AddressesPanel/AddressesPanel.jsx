import { useCallback, useEffect, useState } from "react";
import { Loader2, MapPin, Pencil, Plus, Star, Trash2, X } from "lucide-react";
import SlideOver from "../SlideOver/SlideOver.jsx";
import TextField from "../TextField/TextField.jsx";
import * as api from "../../services/api.js";

const LABEL_PRESETS = ["Home", "Office"];
const EMPTY_FORM = { labelChoice: "Home", customLabel: "", addressText: "" };
const MAX_ADDRESSES = 4;

// An existing address's label might be a preset ("Home"/"Office", any case)
// or a custom string saved before this picker existed (or via "Other") —
// derive which chip should be pre-selected either way.
function formFromAddress(address) {
  const preset = LABEL_PRESETS.find((p) => p.toLowerCase() === address.label.trim().toLowerCase());
  return preset
    ? { labelChoice: preset, customLabel: "", addressText: address.address_text }
    : { labelChoice: "Other", customLabel: address.label, addressText: address.address_text };
}

/**
 * Address book. Deliberately no lat/lng inputs for the address itself —
 * matching the backend's own stance (see backend/CLAUDE.md: chat never
 * sets coordinates either) that there's no geocoding in this project, so
 * free-text address_text is the honest shape for that field, not a
 * placeholder for a map picker that doesn't exist.
 *
 * The label is a Home/Office/Other chip picker, not free text — a real
 * production bug (two addresses labeled "Home"/"home" on one account)
 * showed free-text labels invite typo/casing duplicates even though the
 * backend already blocks exact-duplicate labels case-insensitively.
 * "Other" reveals a custom text field for anything that doesn't fit
 * (a second home, "Mom's place", etc.) — see formFromAddress for how an
 * existing custom label gets recognized as "Other" on edit.
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
    setForm(formFromAddress(address));
    setEditingId(address.id);
  };

  const cancelForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    const label = form.labelChoice === "Other" ? form.customLabel.trim() : form.labelChoice;
    if (!label) {
      setError("Enter a label for this address.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      if (editingId === "new") {
        await api.createAddress({ label, addressText: form.addressText });
      } else {
        await api.updateAddress(editingId, { label, addressText: form.addressText });
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

          {!editingId && addresses.length >= MAX_ADDRESSES && (
            <p className="mb-2 text-center text-xs text-ink-soft">
              You've reached the limit of {MAX_ADDRESSES} saved addresses — delete one to add another.
            </p>
          )}

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
              <div>
                <span className="mb-1.5 block text-sm font-medium text-ink">Label</span>
                <div className="flex gap-2">
                  {[...LABEL_PRESETS, "Other"].map((choice) => (
                    <button
                      key={choice}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, labelChoice: choice }))}
                      className={`rounded-chip border px-4 py-1.5 text-sm font-medium transition ${
                        form.labelChoice === choice
                          ? "border-red/50 bg-red/[0.08] text-red"
                          : "border-line text-ink-soft hover:border-red/30 hover:text-red"
                      }`}
                    >
                      {choice}
                    </button>
                  ))}
                </div>
              </div>
              {form.labelChoice === "Other" && (
                <TextField
                  label="Custom label"
                  value={form.customLabel}
                  onChange={(e) => setForm((f) => ({ ...f, customLabel: e.target.value }))}
                  placeholder="Mom's place, Gym…"
                  required
                  maxLength={50}
                />
              )}
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
              disabled={addresses.length >= MAX_ADDRESSES}
              className="flex w-full items-center justify-center gap-2 rounded-button border border-dashed border-line py-3 text-sm font-medium text-ink-soft transition hover:border-red/40 hover:text-red disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-line disabled:hover:text-ink-soft"
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
