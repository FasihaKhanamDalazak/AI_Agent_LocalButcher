import httpClient from "./httpClient.js";

/**
 * Every function here does ONE thing: call one backend endpoint and return
 * plain JS data (camelCase where it helps callers, otherwise the shape the
 * backend already returns). All error handling funnels through
 * normalizeApiError so components never touch Axios internals.
 */

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

/** @param {{name: string, email: string, password: string, phone: string}} data */
export async function register(data) {
  try {
    const { data: res } = await httpClient.post("/auth/register", data);
    return res.access_token;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

/**
 * The backend's /auth/login is a standard OAuth2 password flow — it wants
 * form-encoded data with the email in a field called `username`, not JSON.
 */
export async function login(email, password) {
  try {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const { data } = await httpClient.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    return data.access_token;
  } catch (error) {
    // A 401 here means the login attempt itself was rejected (wrong
    // password OR no account with this email — the backend deliberately
    // doesn't distinguish the two, to avoid confirming which emails are
    // registered). That's a different situation from a 401 on an
    // already-authenticated request, which normalizeApiError's generic
    // "session expired" copy is written for — so it's handled here
    // instead of falling through to that shared branch.
    if (error.response?.status === 401) {
      throw new Error(
        "We couldn't log you in with that email and password. New here? Create an account instead."
      );
    }
    throw normalizeApiError(error);
  }
}

export async function getCurrentUser() {
  try {
    const { data } = await httpClient.get("/auth/me");
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

/** @returns {Promise<{conversationId: string, greeting: string, followUps: string[]}>} */
export async function getGreeting() {
  try {
    const { data } = await httpClient.get("/chat/greeting");
    return { conversationId: data.conversation_id, greeting: data.greeting, followUps: data.follow_ups };
  } catch (error) {
    throw normalizeApiError(error);
  }
}

/**
 * @param {string} message
 * @param {string|null} conversationId - omit to start a new conversation
 * @returns {Promise<{conversationId: string, reply: string, followUps: string[]}>}
 */
export async function sendChatMessage(message, conversationId) {
  try {
    const { data } = await httpClient.post("/chat", {
      message,
      conversation_id: conversationId ?? null,
    });
    return { conversationId: data.conversation_id, reply: data.reply, followUps: data.follow_ups };
  } catch (error) {
    throw normalizeApiError(error);
  }
}

// ---------------------------------------------------------------------------
// Cart
// ---------------------------------------------------------------------------

export async function getCart() {
  try {
    const { data } = await httpClient.get("/cart");
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function addCartItem(productId, quantity) {
  try {
    const { data } = await httpClient.post("/cart/items", { product_id: productId, quantity });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function updateCartItem(itemId, quantity) {
  try {
    const { data } = await httpClient.patch(`/cart/items/${itemId}`, { quantity });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function removeCartItem(itemId) {
  try {
    await httpClient.delete(`/cart/items/${itemId}`);
  } catch (error) {
    throw normalizeApiError(error);
  }
}

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

/** Delivery only — no pickup option. @param {{outletId: string, addressId: string}} data */
export async function checkout({ outletId, addressId }) {
  try {
    const { data } = await httpClient.post("/orders/checkout", {
      outlet_id: outletId,
      address_id: addressId,
    });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function listOrders() {
  try {
    const { data } = await httpClient.get("/orders");
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function getOrder(orderId) {
  try {
    const { data } = await httpClient.get(`/orders/${orderId}`);
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function cancelOrder(orderId) {
  try {
    const { data } = await httpClient.post(`/orders/${orderId}/cancel`);
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function updateOrderItem(orderId, itemId, quantity) {
  try {
    const { data } = await httpClient.patch(`/orders/${orderId}/items/${itemId}`, { quantity });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function removeOrderItem(orderId, itemId) {
  try {
    const { data } = await httpClient.delete(`/orders/${orderId}/items/${itemId}`);
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

// ---------------------------------------------------------------------------
// Addresses
// ---------------------------------------------------------------------------

export async function listAddresses() {
  try {
    const { data } = await httpClient.get("/addresses");
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

/** @param {{label: string, addressText: string, isDefault?: boolean}} data */
export async function createAddress({ label, addressText, isDefault = false }) {
  try {
    const { data } = await httpClient.post("/addresses", {
      label,
      address_text: addressText,
      is_default: isDefault,
    });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

/** @param {{label?: string, addressText?: string, isDefault?: boolean}} data */
export async function updateAddress(addressId, { label, addressText, isDefault } = {}) {
  try {
    const payload = {};
    if (label !== undefined) payload.label = label;
    if (addressText !== undefined) payload.address_text = addressText;
    if (isDefault !== undefined) payload.is_default = isDefault;
    const { data } = await httpClient.patch(`/addresses/${addressId}`, payload);
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function deleteAddress(addressId) {
  try {
    await httpClient.delete(`/addresses/${addressId}`);
  } catch (error) {
    throw normalizeApiError(error);
  }
}

// ---------------------------------------------------------------------------
// Outlets & products (read-only, used to label order/cart items and for
// the addresses panel's "nearest outlet" preview)
// ---------------------------------------------------------------------------

export async function listOutlets() {
  try {
    const { data } = await httpClient.get("/outlets");
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function getNearestOutlet(addressId) {
  try {
    const { data } = await httpClient.get("/outlets/nearest", { params: { address_id: addressId } });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function listProducts(category) {
  try {
    const { data } = await httpClient.get("/products", { params: category ? { category } : {} });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

// ---------------------------------------------------------------------------
// Support
// ---------------------------------------------------------------------------

export async function listSupportTickets() {
  try {
    const { data } = await httpClient.get("/support-tickets");
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function createSupportTicket({ issueText, orderId }) {
  try {
    const { data } = await httpClient.post("/support-tickets", {
      issue_text: issueText,
      order_id: orderId ?? null,
    });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

// ---------------------------------------------------------------------------
// Staff (dashboard) — every call here 403s server-side unless the logged-in
// user's role is "staff" (see backend get_current_staff_user); the frontend
// only uses these behind that same role check, never as the real guard.
// ---------------------------------------------------------------------------

/** @param {{statusCode?: string, outletId?: string}} [filters] */
export async function listStaffOrders({ statusCode, outletId } = {}) {
  try {
    const params = {};
    if (statusCode) params.status = statusCode;
    if (outletId) params.outlet_id = outletId;
    const { data } = await httpClient.get("/staff/orders", { params });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function updateStaffOrderStatus(orderId, statusCode) {
  try {
    const { data } = await httpClient.patch(`/staff/orders/${orderId}/status`, { status_code: statusCode });
    return data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

// ---------------------------------------------------------------------------
// Error normalization
// ---------------------------------------------------------------------------

/**
 * Converts Axios/network errors into a consistent, user-facing Error
 * object so the UI layer never has to know about Axios internals or the
 * backend's exact error-body shape.
 */
function normalizeApiError(error) {
  if (error.response) {
    const status = error.response.status;
    const serverMessage = error.response.data?.detail;

    if (status === 429) {
      const err = new Error(
        "Whoa, slow down a sec — you're doing that a little too fast. Give it a moment and try again."
      );
      err.isRateLimited = true;
      return err;
    }
    if (status === 401) {
      return new Error("Your session has expired — please log in again.");
    }
    if (status >= 500) {
      return new Error(
        typeof serverMessage === "string"
          ? serverMessage
          : "Something went wrong on our end. Please try again."
      );
    }
    return new Error(typeof serverMessage === "string" ? serverMessage : "We couldn't process that request.");
  }

  if (error.request) {
    // By the time this fires, httpClient's response interceptor has
    // already retried once for GET requests (see httpClient.js) — so this
    // is either a genuinely dead connection, or a POST/PATCH/DELETE that
    // hit a slow Render cold start and wasn't safe to auto-retry. Either
    // way, telling the customer to wait a moment is more accurate than
    // just "check your connection" — the server itself is very likely
    // just waking up, not actually unreachable.
    return new Error(
      "Couldn't reach the server — it may just be waking up after being idle. Please try again in a few seconds."
    );
  }

  return new Error("Unexpected error. Please try again.");
}
