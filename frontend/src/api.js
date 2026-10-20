export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const WS_URL = API.replace(/^http/, "ws");

export async function request(path, { method = "GET", token, headers = {}, json, form } = {}) {
  const opts = { method, headers: { ...headers } };
  if (token) opts.headers.Authorization = `Bearer ${token}`;
  if (json) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(json);
  }
  if (form) {
    opts.headers["Content-Type"] = "application/x-www-form-urlencoded";
    opts.body = new URLSearchParams(form).toString();
  }

  const res = await fetch(`${API}${path}`, opts);
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    let message = "Something went wrong";
    if (typeof data?.detail === "string") message = data.detail;
    else if (Array.isArray(data?.detail)) message = data.detail.map((d) => d.msg).join(", ");
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return { data, status: res.status };
}
