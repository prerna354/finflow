import { useCallback, useEffect, useRef, useState } from "react";
import { WS_URL, request } from "./api.js";

const newKey = () => crypto.randomUUID();

export default function Dashboard({ token, onLogout }) {
  const [me, setMe] = useState(null);
  const [txns, setTxns] = useState([]);
  const [stats, setStats] = useState(null);
  const [live, setLive] = useState(false);

  const [receiverEmail, setReceiverEmail] = useState("");
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState(null); // { type: "ok" | "error", text }
  const [busy, setBusy] = useState(false);
  const keyRef = useRef(newKey()); // same key is reused until a payment succeeds (idempotency)
  const roleRef = useRef(null);

  const logoutOn401 = useCallback(
    (err) => {
      if (err.status === 401) onLogout();
    },
    [onLogout]
  );

  const loadStats = useCallback(
    (role) => {
      if (role === "admin" || role === "analyst") {
        request("/admin/stats", { token }).then((r) => setStats(r.data)).catch(() => {});
      }
    },
    [token]
  );

  // First load
  useEffect(() => {
    request("/users/me", { token })
      .then((r) => {
        setMe(r.data);
        roleRef.current = r.data.role;
        loadStats(r.data.role);
      })
      .catch(logoutOn401);
    request("/payments", { token }).then((r) => setTxns(r.data)).catch(logoutOn401);
  }, [token, loadStats, logoutOn401]);

  // Live updates over WebSocket (auto-reconnects)
  useEffect(() => {
    let socket;
    let closedByUs = false;
    let retryTimer;

    function connect() {
      socket = new WebSocket(`${WS_URL}/ws/transactions?token=${encodeURIComponent(token)}`);
      socket.onopen = () => setLive(true);
      socket.onclose = () => {
        setLive(false);
        if (!closedByUs) retryTimer = setTimeout(connect, 2000);
      };
      socket.onmessage = (event) => {
        const { transaction } = JSON.parse(event.data);
        setTxns((current) => {
          const others = current.filter((t) => t.id !== transaction.id);
          return [transaction, ...others].sort((a, b) => b.created_at.localeCompare(a.created_at));
        });
        loadStats(roleRef.current);
      };
    }

    connect();
    return () => {
      closedByUs = true;
      clearTimeout(retryTimer);
      socket && socket.close();
    };
  }, [token, loadStats]);

  async function pay(e) {
    e.preventDefault();
    setMessage(null);
    setBusy(true);
    try {
      const { data: receiver } = await request(`/users/lookup?email=${encodeURIComponent(receiverEmail)}`, { token });
      const { data, status } = await request("/payments", {
        method: "POST",
        token,
        headers: { "Idempotency-Key": keyRef.current },
        json: { receiver_id: receiver.id, amount: Number(amount), currency: "INR" },
      });
      setTxns((current) => [data, ...current.filter((t) => t.id !== data.id)]);
      setMessage({
        type: "ok",
        text:
          status === 200
            ? "Duplicate request detected: no new payment was created."
            : `Payment sent to ${receiver.full_name}. Fraud check is running...`,
      });
      keyRef.current = newKey(); // next payment gets a new key
      setAmount("");
    } catch (err) {
      logoutOn401(err);
      setMessage({ type: "error", text: err.message });
    } finally {
      setBusy(false);
    }
  }

  const nameOf = (id) => (me && id === me.id ? "You" : id.slice(0, 8));

  return (
    <div className="page">
      <header>
        <div>
          <h1>FinFlow</h1>
          {me && (
            <span className="muted">
              {me.full_name} · <span className="role">{me.role}</span>
            </span>
          )}
        </div>
        <div className="right">
          <span className={live ? "live on" : "live"}>{live ? "● Live" : "○ Reconnecting..."}</span>
          <button className="secondary" onClick={onLogout}>Log out</button>
        </div>
      </header>

      {stats && (
        <section className="stats">
          <div className="card stat"><b>{stats.total}</b><span>Total payments</span></div>
          {["APPROVED", "FLAGGED", "REJECTED", "PENDING"].map((s) => (
            <div className="card stat" key={s}>
              <b>{stats.by_status[s]?.count ?? 0}</b>
              <span>{s}</span>
            </div>
          ))}
        </section>
      )}

      <section className="card">
        <h2>Send a payment</h2>
        <form className="row" onSubmit={pay}>
          <input type="email" placeholder="Receiver's email" value={receiverEmail}
                 onChange={(e) => setReceiverEmail(e.target.value)} required />
          <input type="number" placeholder="Amount (INR)" value={amount} min="1" step="0.01"
                 onChange={(e) => setAmount(e.target.value)} required />
          <button disabled={busy}>{busy ? "Sending..." : "Pay"}</button>
        </form>
        {message && <div className={message.type === "ok" ? "ok" : "error"}>{message.text}</div>}
        <p className="muted small">
          Tip: try 500 (approved), 60000 (large), or 120000 from a new account (rejected). Double-click Pay to see idempotency work.
        </p>
      </section>

      <section className="card">
        <h2>Payments</h2>
        {txns.length === 0 ? (
          <p className="muted">No payments yet.</p>
        ) : (
          <div className="scroll">
            <table>
              <thead>
                <tr><th>Time</th><th>From</th><th>To</th><th>Amount</th><th>Status</th><th>Risk</th><th>Reason</th></tr>
              </thead>
              <tbody>
                {txns.map((t) => (
                  <tr key={t.id}>
                    <td>{new Date(t.created_at).toLocaleString()}</td>
                    <td>{nameOf(t.sender_id)}</td>
                    <td>{nameOf(t.receiver_id)}</td>
                    <td>{t.currency} {Number(t.amount).toLocaleString()}</td>
                    <td><span className={`badge ${t.status}`}>{t.status}</span></td>
                    <td>{t.fraud_score ?? "-"}</td>
                    <td className="muted">{t.fraud_reason ?? "Checking..."}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
