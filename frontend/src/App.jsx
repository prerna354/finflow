import { useState } from "react";
import Login from "./Login.jsx";
import Dashboard from "./Dashboard.jsx";

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("finflow_token"));

  function handleLogin(newToken) {
    localStorage.setItem("finflow_token", newToken);
    setToken(newToken);
  }

  function handleLogout() {
    localStorage.removeItem("finflow_token");
    setToken(null);
  }

  return token ? (
    <Dashboard token={token} onLogout={handleLogout} />
  ) : (
    <Login onLogin={handleLogin} />
  );
}
