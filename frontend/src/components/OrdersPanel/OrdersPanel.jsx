import { useCallback, useEffect, useState } from "react";
import { Loader2, Minus, Package, Plus, Trash2 } from "lucide-react";
import SlideOver from "../SlideOver/SlideOver.jsx";
import * as api from "../../services/api.js";
import { formatCurrency, formatDateTime } from "../../utils/helpers.js";

const STATUS_STYLES = {
  cancelled: "bg-error/10 text-error",
  delivered: "bg-success/10 text-success",
  completed: "bg-success/10 text-success",
};
const DEFAULT_STATUS_STYLE = "bg-gold/15 text-brown";

/**
 * Order history with inline item edits — but only for orders the backend
 * actually still allows to change. `order.is_modifiable`/`is_cancellable`
 * come straight from the order_statuses row backing that order (see
 * backend/app/models/order.py's OrderStatus and order_to_read) rather
 * than being guessed from the status string here, so a delivered/
 * cancelled order shows a plain read-only quantity instead of stepper
 * controls that would just come back as OrderNotModifiableError.
 */
function OrdersPanel({ isOpen, onClose }) {
  const [orders, setOrders] = useState([]);
  const [productNames, setProductNames] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyKey, setBusyKey] = useState(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [ordersData, productsData] = await Promise.all([api.listOrders(), api.listProducts()]);
      setOrders([...ordersData].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)));
      setProductNames(Object.fromEntries(productsData.map((p) => [p.id, p.name])));
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) load();
  }, [isOpen, load]);

  const runAction = async (key, fn) => {
    setBusyKey(key);
    setError(null);
    try {
      const updated = await fn();
      setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <SlideOver isOpen={isOpen} onClose={onClose} title="Your orders" icon={Package}>
      {isLoading && (
        <div className="flex items-center justify-center py-16 text-ink-soft">
          <Loader2 size={22} className="animate-spin" />
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-card-sm border border-error/30 bg-error/[0.06] px-4 py-2.5 text-sm text-error">
          {error}
        </div>
      )}

      {!isLoading && orders.length === 0 && (
        <p className="py-10 text-center text-sm text-ink-soft">No orders yet.</p>
      )}

      {!isLoading && orders.length > 0 && (
        <ul className="flex flex-col gap-4">
          {orders.map((order) => (
            <li key={order.id} className="rounded-card border border-line bg-cream/40 p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="font-display text-sm font-bold text-ink">Order #{order.order_number}</p>
                <span
                  className={`rounded-chip px-2.5 py-1 text-xs font-semibold ${
                    STATUS_STYLES[order.status] ?? DEFAULT_STATUS_STYLE
                  }`}
                >
                  {order.status_label}
                </span>
              </div>
              <p className="mb-3 text-xs text-ink-soft">
                {formatDateTime(order.created_at)} · {order.fulfillment_type}
              </p>

              <ul className="mb-3 flex flex-col gap-2">
                {order.items.map((item) => {
                  const busyId = `${order.id}:${item.id}`;
                  return (
                    <li key={item.id} className="flex items-center gap-2 text-sm">
                      <span className="min-w-0 flex-1 truncate text-ink">
                        {productNames[item.product_id] ?? "Item"}
                      </span>

                      {order.is_modifiable ? (
                        <>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              disabled={busyKey === busyId || item.quantity <= 1}
                              onClick={() =>
                                runAction(busyId, () =>
                                  api.updateOrderItem(order.id, item.id, item.quantity - 1)
                                )
                              }
                              aria-label="Decrease quantity"
                              className="flex h-6 w-6 items-center justify-center rounded-full border border-line text-ink-soft transition hover:border-red/40 hover:text-red disabled:opacity-40"
                            >
                              <Minus size={11} />
                            </button>
                            <span className="w-6 text-center text-xs font-medium text-ink">{item.quantity}</span>
                            <button
                              type="button"
                              disabled={busyKey === busyId}
                              onClick={() =>
                                runAction(busyId, () =>
                                  api.updateOrderItem(order.id, item.id, item.quantity + 1)
                                )
                              }
                              aria-label="Increase quantity"
                              className="flex h-6 w-6 items-center justify-center rounded-full border border-line text-ink-soft transition hover:border-red/40 hover:text-red disabled:opacity-40"
                            >
                              <Plus size={11} />
                            </button>
                          </div>
                          <span className="w-16 shrink-0 text-right text-xs font-semibold text-ink">
                            {formatCurrency(item.price_at_order * item.quantity)}
                          </span>
                          <button
                            type="button"
                            disabled={busyKey === busyId}
                            onClick={() => runAction(busyId, () => api.removeOrderItem(order.id, item.id))}
                            aria-label="Remove item"
                            className="text-ink-soft transition hover:text-error disabled:opacity-40"
                          >
                            <Trash2 size={13} />
                          </button>
                        </>
                      ) : (
                        <>
                          <span className="shrink-0 text-xs text-ink-soft">Qty {item.quantity}</span>
                          <span className="w-16 shrink-0 text-right text-xs font-semibold text-ink">
                            {formatCurrency(item.price_at_order * item.quantity)}
                          </span>
                        </>
                      )}
                    </li>
                  );
                })}
              </ul>

              <div className="flex items-center justify-between border-t border-line pt-3">
                <p className="text-sm font-bold text-ink">{formatCurrency(order.total_amount)}</p>
                {order.is_cancellable && (
                  <button
                    type="button"
                    disabled={busyKey === order.id}
                    onClick={() => runAction(order.id, () => api.cancelOrder(order.id))}
                    className="text-xs font-semibold text-error transition hover:underline disabled:cursor-not-allowed disabled:opacity-40 disabled:no-underline"
                  >
                    Cancel order
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </SlideOver>
  );
}

export default OrdersPanel;
