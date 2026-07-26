import { useCallback, useEffect, useState } from "react";
import { Loader2, Minus, Plus, ShoppingCart, Trash2 } from "lucide-react";
import SlideOver from "../SlideOver/SlideOver.jsx";
import Select from "../Select/Select.jsx";
import * as api from "../../services/api.js";
import { formatCurrency } from "../../utils/helpers.js";

/**
 * Cart contents + checkout, in one panel. Delivery only — checkout needs
 * an outlet and a saved address; both lists are loaded lazily, only once
 * the panel is actually opened.
 */
function CartPanel({ isOpen, onClose }) {
  const [cart, setCart] = useState(null);
  const [outlets, setOutlets] = useState([]);
  const [addresses, setAddresses] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyItemId, setBusyItemId] = useState(null);

  const [outletId, setOutletId] = useState("");
  const [addressId, setAddressId] = useState("");
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [placedOrder, setPlacedOrder] = useState(null);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [cartData, outletsData, addressesData] = await Promise.all([
        api.getCart(),
        api.listOutlets(),
        api.listAddresses(),
      ]);
      setCart(cartData);
      setOutlets(outletsData);
      setAddresses(addressesData);
      setOutletId((prev) => prev || outletsData[0]?.id || "");
      setAddressId((prev) => prev || addressesData.find((a) => a.is_default)?.id || addressesData[0]?.id || "");
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      setPlacedOrder(null);
      loadAll();
    }
  }, [isOpen, loadAll]);

  const refreshCart = async () => {
    try {
      setCart(await api.getCart());
    } catch (err) {
      setError(err.message);
    }
  };

  const changeQuantity = async (item, nextQty) => {
    setBusyItemId(item.id);
    setError(null);
    try {
      if (nextQty <= 0) {
        await api.removeCartItem(item.id);
      } else {
        await api.updateCartItem(item.id, nextQty);
      }
      await refreshCart();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyItemId(null);
    }
  };

  const handleCheckout = async () => {
    setIsCheckingOut(true);
    setError(null);
    try {
      const order = await api.checkout({ outletId, addressId });
      setPlacedOrder(order);
      setCart({ items: [], subtotal: 0 });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsCheckingOut(false);
    }
  };

  const hasItems = cart?.items?.length > 0;

  return (
    <SlideOver isOpen={isOpen} onClose={onClose} title="Your cart" icon={ShoppingCart}>
      {isLoading && (
        <div className="flex items-center justify-center py-16 text-ink-soft">
          <Loader2 size={22} className="animate-spin" />
        </div>
      )}

      {!isLoading && error && (
        <div className="mb-4 rounded-card-sm border border-error/30 bg-error/[0.06] px-4 py-2.5 text-sm text-error">
          {error}
        </div>
      )}

      {!isLoading && placedOrder && (
        <div className="rounded-card border border-success/30 bg-success/[0.06] px-4 py-4 text-sm text-ink">
          <p className="font-semibold text-success">Order #{placedOrder.order_number} placed!</p>
          <p className="mt-1 text-ink-soft">
            Total {formatCurrency(placedOrder.total_amount)} — track it from the Orders panel.
          </p>
        </div>
      )}

      {!isLoading && !placedOrder && (
        <>
          {!hasItems && <p className="py-10 text-center text-sm text-ink-soft">Your cart is empty.</p>}

          {hasItems && (
            <ul className="flex flex-col gap-3">
              {cart.items.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center gap-3 rounded-card-sm border border-line bg-cream/40 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-ink">{item.product_name}</p>
                    <p className="text-xs text-ink-soft">
                      {formatCurrency(item.price)} / {item.unit}
                    </p>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={busyItemId === item.id}
                      onClick={() => changeQuantity(item, item.quantity - 1)}
                      aria-label={`Decrease quantity of ${item.product_name}`}
                      className="flex h-7 w-7 items-center justify-center rounded-full border border-line text-ink-soft transition hover:border-red/40 hover:text-red disabled:opacity-50"
                    >
                      <Minus size={13} />
                    </button>
                    <span className="w-8 text-center text-sm font-medium text-ink">{item.quantity}</span>
                    <button
                      type="button"
                      disabled={busyItemId === item.id}
                      onClick={() => changeQuantity(item, item.quantity + 1)}
                      aria-label={`Increase quantity of ${item.product_name}`}
                      className="flex h-7 w-7 items-center justify-center rounded-full border border-line text-ink-soft transition hover:border-red/40 hover:text-red disabled:opacity-50"
                    >
                      <Plus size={13} />
                    </button>
                  </div>

                  <p className="w-16 shrink-0 text-right text-sm font-semibold text-ink">
                    {formatCurrency(item.line_total)}
                  </p>

                  <button
                    type="button"
                    disabled={busyItemId === item.id}
                    onClick={() => changeQuantity(item, 0)}
                    aria-label={`Remove ${item.product_name}`}
                    className="text-ink-soft transition hover:text-error disabled:opacity-50"
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          )}

          {hasItems && (
            <div className="mt-5 border-t border-line pt-5">
              <div className="mb-4 flex items-center justify-between text-sm">
                <span className="text-ink-soft">Subtotal</span>
                <span className="text-base font-bold text-ink">{formatCurrency(cart.subtotal)}</span>
              </div>

              <Select
                label="Outlet"
                value={outletId}
                onChange={(e) => setOutletId(e.target.value)}
                className="mb-3"
              >
                {outlets.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} — {o.area}
                  </option>
                ))}
              </Select>

              {addresses.length === 0 ? (
                <div className="mb-4">
                  <span className="mb-1.5 block text-sm font-medium text-ink">Deliver to</span>
                  <p className="text-xs text-ink-soft">
                    No saved addresses yet — add one from the Addresses panel first.
                  </p>
                </div>
              ) : (
                <Select
                  label="Deliver to"
                  value={addressId}
                  onChange={(e) => setAddressId(e.target.value)}
                  className="mb-4"
                >
                  {addresses.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.label} — {a.address_text}
                    </option>
                  ))}
                </Select>
              )}

              <button
                type="button"
                disabled={isCheckingOut || !outletId || !addressId}
                onClick={handleCheckout}
                className="sheen w-full rounded-button bg-red-gradient px-5 py-3 text-sm font-semibold text-white shadow-glow transition duration-200 hover:shadow-glow-lg disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isCheckingOut ? "Placing order…" : "Checkout"}
              </button>
            </div>
          )}
        </>
      )}
    </SlideOver>
  );
}

export default CartPanel;
