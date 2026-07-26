import { useCallback, useEffect, useState } from "react";
import { LogOut, RefreshCw } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";
import * as api from "../services/api.js";
import { ORDER_STATUS_OPTIONS } from "../utils/constants.js";
import { formatCurrency, formatDateTime } from "../utils/helpers.js";

const STATUS_STYLES = {
  cancelled: "bg-error/10 text-error",
  delivered: "bg-success/10 text-success",
};
const DEFAULT_STATUS_STYLE = "bg-gold/15 text-brown";

/**
 * Minimal staff-only view: every order across all customers, with a status
 * filter and a way to advance/change status. Reachable only at /staff (see
 * App.jsx) — deliberately not linked from the customer-facing header, since
 * this is an internal tool, not a customer feature. The backend's
 * get_current_staff_user 403s any non-staff caller regardless of this
 * page's own role check below, which only exists to avoid showing a
 * confusing all-403 screen to a customer who stumbles onto the URL.
 */
function StaffDashboardPage() {
  const { user, logout } = useAuth();
  const [orders, setOrders] = useState([]);
  const [productNames, setProductNames] = useState({});
  const [statusFilter, setStatusFilter] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyOrderId, setBusyOrderId] = useState(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [ordersData, productsData] = await Promise.all([
        api.listStaffOrders({ statusCode: statusFilter || undefined }),
        api.listProducts(),
      ]);
      setOrders(ordersData);
      setProductNames(Object.fromEntries(productsData.map((p) => [p.id, p.name])));
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStatusChange = async (orderId, newStatus) => {
    setBusyOrderId(orderId);
    setError(null);
    try {
      const updated = await api.updateStaffOrderStatus(orderId, newStatus);
      setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyOrderId(null);
    }
  };

  if (user?.role !== "staff") {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-3 bg-background px-4 text-center">
        <p className="text-lg font-semibold text-ink">Staff access required</p>
        <p className="text-sm text-ink-soft">This account isn't a staff account.</p>
        <button
          type="button"
          onClick={logout}
          className="mt-2 rounded-button bg-red-gradient px-5 py-2.5 text-sm font-semibold text-white shadow-glow"
        >
          Log out
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-background px-4 py-6 sm:px-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-display text-xl font-bold text-ink">
            Local<span className="text-red">Butcher</span> Staff Dashboard
          </h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={load}
              disabled={isLoading}
              aria-label="Refresh"
              className="flex h-9 w-9 items-center justify-center rounded-full border border-line text-ink-soft transition hover:border-red/40 hover:text-red disabled:opacity-50"
            >
              <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
            </button>
            <button
              type="button"
              onClick={logout}
              className="flex items-center gap-1.5 rounded-button border border-line px-3 py-2 text-sm font-medium text-ink-soft transition hover:border-red/40 hover:text-red"
            >
              <LogOut size={14} /> Log out
            </button>
          </div>
        </div>

        <div className="mb-5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setStatusFilter("")}
            className={`rounded-chip px-3 py-1.5 text-xs font-semibold transition ${
              statusFilter === "" ? "bg-red text-white" : "border border-line text-ink-soft hover:border-red/40"
            }`}
          >
            All
          </button>
          {ORDER_STATUS_OPTIONS.map(({ code, label }) => (
            <button
              key={code}
              type="button"
              onClick={() => setStatusFilter(code)}
              className={`rounded-chip px-3 py-1.5 text-xs font-semibold transition ${
                statusFilter === code ? "bg-red text-white" : "border border-line text-ink-soft hover:border-red/40"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-4 rounded-card-sm border border-error/30 bg-error/[0.06] px-4 py-2.5 text-sm text-error">
            {error}
          </div>
        )}

        {isLoading && orders.length === 0 && (
          <p className="py-16 text-center text-sm text-ink-soft">Loading orders…</p>
        )}

        {!isLoading && orders.length === 0 && (
          <p className="py-16 text-center text-sm text-ink-soft">No orders match this filter.</p>
        )}

        <ul className="flex flex-col gap-3">
          {orders.map((order) => (
            <li key={order.id} className="rounded-card border border-line bg-surface p-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-display text-sm font-bold text-ink">
                    Order #{order.order_number} · {order.customer_name}
                  </p>
                  <p className="text-xs text-ink-soft">
                    {order.customer_phone ?? "no phone on file"} · {order.outlet_name} · {order.fulfillment_type}
                  </p>
                </div>
                <span
                  className={`rounded-chip px-2.5 py-1 text-xs font-semibold ${
                    STATUS_STYLES[order.status] ?? DEFAULT_STATUS_STYLE
                  }`}
                >
                  {order.status_label}
                </span>
              </div>

              <p className="mb-3 text-xs text-ink-soft">{formatDateTime(order.created_at)}</p>

              <ul className="mb-3 flex flex-col gap-1 text-sm text-ink">
                {order.items.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-2">
                    <span className="min-w-0 flex-1 truncate">
                      {productNames[item.product_id] ?? "Item"} · Qty {item.quantity}
                    </span>
                    <span className="shrink-0 font-medium">
                      {formatCurrency(item.price_at_order * item.quantity)}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="flex items-center justify-between border-t border-line pt-3">
                <p className="text-sm font-bold text-ink">{formatCurrency(order.total_amount)}</p>
                <select
                  value={order.status}
                  disabled={busyOrderId === order.id}
                  onChange={(e) => handleStatusChange(order.id, e.target.value)}
                  className="rounded-button border border-line bg-surface px-2.5 py-1.5 text-xs font-medium text-ink disabled:opacity-50"
                >
                  {ORDER_STATUS_OPTIONS.map(({ code, label }) => (
                    <option key={code} value={code}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default StaffDashboardPage;
