import { useState } from "react";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext.jsx";
import TextField from "../components/TextField/TextField.jsx";

/**
 * Login/register, toggled in place rather than two separate routes —
 * there's nothing else this page needs to do, and a route change would
 * just add a flash between two nearly-identical screens.
 */
function AuthPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(form.email, form.password);
      } else {
        await register({
          name: form.name,
          email: form.email,
          phone: form.phone || undefined,
          password: form.password,
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const switchMode = () => {
    setMode((m) => (m === "login" ? "register" : "login"));
    setError(null);
  };

  return (
    <div className="relative flex h-dvh items-center justify-center overflow-hidden bg-background px-4">
      <div className="bg-fx" aria-hidden="true">
        <div className="bg-fx__glow bg-fx__glow--red" />
        <div className="bg-fx__glow bg-fx__glow--brown" />
        <div className="bg-fx__grain" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="relative z-10 w-full max-w-md rounded-card border border-line bg-surface p-8 shadow-card-lg"
      >
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="text-3xl">🥩</span>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-ink">
            Local<span className="text-red">Butcher</span>
          </h1>
          <p className="mt-1 text-sm text-ink-soft">
            {mode === "login" ? "Welcome back — log in to continue." : "Create an account to get started."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {mode === "register" && (
            <TextField
              label="Full name"
              value={form.name}
              onChange={update("name")}
              placeholder="Your name"
              required
              autoComplete="name"
            />
          )}

          <TextField
            label="Email"
            type="email"
            value={form.email}
            onChange={update("email")}
            placeholder="you@example.com"
            required
            autoComplete="email"
          />

          {mode === "register" && (
            <TextField
              label="Phone (optional)"
              type="tel"
              value={form.phone}
              onChange={update("phone")}
              placeholder="+91 98765 43210"
              autoComplete="tel"
            />
          )}

          <TextField
            label="Password"
            type="password"
            value={form.password}
            onChange={update("password")}
            placeholder="At least 8 characters"
            required
            minLength={8}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />

          {error && (
            <div className="rounded-card-sm border border-error/30 bg-error/[0.06] px-4 py-2.5 text-sm text-error">
              {error}
            </div>
          )}

          <motion.button
            type="submit"
            disabled={submitting}
            whileHover={!submitting ? { y: -1 } : undefined}
            whileTap={!submitting ? { scale: 0.98 } : undefined}
            className="
              sheen mt-2 rounded-button bg-red-gradient px-5 py-3 text-sm font-semibold text-white
              shadow-glow transition duration-200 hover:shadow-glow-lg
              disabled:cursor-not-allowed disabled:opacity-60
            "
          >
            {submitting ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </motion.button>
        </form>

        <button
          type="button"
          onClick={switchMode}
          className="mt-5 w-full text-center text-sm font-medium text-ink-soft transition hover:text-red"
        >
          {mode === "login" ? "New here? Create an account" : "Already have an account? Log in"}
        </button>
      </motion.div>
    </div>
  );
}

export default AuthPage;
