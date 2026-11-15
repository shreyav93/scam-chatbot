
import { useEffect, useState } from "react";

const API = "/api/developer";

function getCookie(name) {
  const cookies = document.cookie.split(";");

  for (const cookie of cookies) {
    const trimmed = cookie.trim();

    if (trimmed.startsWith(name + "=")) {
      return decodeURIComponent(trimmed.substring(name.length + 1));
    }
  }

  return null;
}

async function apiRequest(endpoint, options = {}) {
  const csrfToken = getCookie("csrftoken");

  const response = await fetch(`${API}${endpoint}`, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.error || "Something went wrong.");
  }

  return data;
}

const emptySourceForm = {
  title: "",
  publisher: "",
  url: "",
  category: "",
  channel: "any",
};

export default function DeveloperPage() {
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestionResult, setIngestionResult] = useState(null);

  const [loginForm, setLoginForm] = useState({
    username: "",
    password: "",
  });

  const [sources, setSources] = useState([]);
  const [stats, setStats] = useState({
    total_sources: 0,
    active_sources: 0,
    inactive_sources: 0,
    total_chunks: 0,
  });

  const [loadingSources, setLoadingSources] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [sourceForm, setSourceForm] = useState(emptySourceForm);
  const [editingId, setEditingId] = useState(null);

  useEffect(() => {
    async function checkLogin() {
      try {
        await apiRequest("/csrf/");
        const data = await apiRequest("/status/");

        setAuthenticated(data.authenticated && data.is_developer);
        setUsername(data.username || "");
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    checkLogin();
  }, []);

  useEffect(() => {
    if (authenticated) {
      loadDashboard();
    }
  }, [authenticated]);

  async function loadDashboard() {
    setError("");
    setLoadingSources(true);

    try {
      const [sourceData, statsData] = await Promise.all([
        apiRequest("/sources/"),
        apiRequest("/stats/"),
      ]);

      setSources(sourceData.sources || []);
      setStats(statsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingSources(false);
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    setError("");

    try {
      const data = await apiRequest("/login/", {
        method: "POST",
        body: JSON.stringify(loginForm),
      });

      setAuthenticated(true);
      setUsername(data.username);
      setLoginForm({ username: "", password: "" });
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleLogout() {
    try {
      await apiRequest("/logout/", { method: "POST" });
      setAuthenticated(false);
      setUsername("");
      setSources([]);
      setSuccess("");
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  function startEditing(source) {
    setEditingId(source.id);
    setSourceForm({
      title: source.title,
      publisher: source.publisher,
      url: source.url,
      category: source.category || "",
      channel: source.channel || "any",
    });
    setShowAddForm(false);
    setError("");
    setSuccess("");
  }

  function cancelForm() {
    setEditingId(null);
    setShowAddForm(false);
    setSourceForm(emptySourceForm);
  }

  async function handleSaveSource(event) {
    event.preventDefault();
    setError("");
    setSuccess("");

    try {
      if (editingId !== null) {
        await apiRequest(`/sources/${editingId}/`, {
          method: "PATCH",
          body: JSON.stringify(sourceForm),
        });

        setSuccess("Source updated successfully.");
      } else {
        await apiRequest("/sources/add/", {
          method: "POST",
          body: JSON.stringify(sourceForm),
        });

        setSuccess(
          "Source added. Run ingestion to make its content available to the chatbot."
        );
      }

      cancelForm();
      await loadDashboard();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleSource(source) {
    setError("");
    setSuccess("");

    try {
      await apiRequest(`/sources/${source.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ active: !source.active }),
      });

      setSuccess(
        source.active
          ? "Source deactivated."
          : "Source activated."
      );

      await loadDashboard();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleIngest() {
  setIngesting(true);
  setError("");
  setSuccess("");
  setIngestionResult(null);

  try {
    const data = await apiRequest("/ingest/", {
      method: "POST",
    });

    setIngestionResult(data);
    setSuccess("Ingestion completed successfully.");

    await loadDashboard();
  } catch (err) {
    setError(err.message);
  } finally {
    setIngesting(false);
  }
  }

  if (loading) {
    return <p>Loading developer portal...</p>;
  }

  

  if (!authenticated) {
    return (
      <div className="developer-login">
        <h2>Developer Login</h2>
        <p>Sign in with your authorized developer account.</p>

        <form onSubmit={handleLogin}>
          <input
            type="text"
            placeholder="Username"
            value={loginForm.username}
            onChange={(e) =>
              setLoginForm({
                ...loginForm,
                username: e.target.value,
              })
            }
            required
          />

          <input
            type="password"
            placeholder="Password"
            value={loginForm.password}
            onChange={(e) =>
              setLoginForm({
                ...loginForm,
                password: e.target.value,
              })
            }
            required
          />

          <button type="submit">Log In</button>
        </form>

        {error && <p className="developer-error">{error}</p>}
      </div>
    );
  }

  return (
    <div className="developer-dashboard">
      <div className="developer-header">
        <div>
          <h2>Developer Dashboard</h2>
          <p>Welcome, {username}</p>
        </div>

        <button onClick={handleLogout}>Log Out</button>
      </div>

      {error && <p className="developer-error">{error}</p>}
      {success && <p className="developer-success">{success}</p>}

      {/* DATASET MANAGEMENT */}
      <section className="developer-section">
        <div className="developer-section-heading">
          <div>
            <h3>Dataset Management</h3>
            <p>
              Manage the trusted information used by the chatbot's
              retrieval system.
            </p>
          </div>

          <button
            onClick={() => {
              cancelForm();
              setShowAddForm(true);
              setError("");
              setSuccess("");
            }}
          >
            + Add Source
          </button>
        </div>

        {showAddForm && (
          <form className="source-form" onSubmit={handleSaveSource}>
            <h4>Add New Source</h4>

            <label>
              Source Title
              <input
                value={sourceForm.title}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    title: e.target.value,
                  })
                }
                placeholder="Title of the webpage"
                required
              />
            </label>

            <label>
              Publisher
              <input
                value={sourceForm.publisher}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    publisher: e.target.value,
                  })
                }
                placeholder="e.g. Consumer Financial Protection Bureau"
                required
              />
            </label>

            <label>
              Source URL
              <input
                type="url"
                value={sourceForm.url}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    url: e.target.value,
                  })
                }
                placeholder="https://example.com/article"
                required
              />
            </label>

            <label>
              Category
              <input
                value={sourceForm.category}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    category: e.target.value,
                  })
                }
                placeholder="e.g. warning-signs"
              />
            </label>

            <label>
              Channel
              <select
                value={sourceForm.channel}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    channel: e.target.value,
                  })
                }
              >
                <option value="any">Any</option>
                <option value="text">Text</option>
                <option value="email">Email</option>
                <option value="phone">Phone</option>
              </select>
            </label>

            <div className="source-form-actions">
              <button type="submit">Save Source</button>
              <button type="button" onClick={cancelForm}>
                Cancel
              </button>
            </div>
          </form>
        )}

        {editingId !== null && (
          <form className="source-form" onSubmit={handleSaveSource}>
            <h4>Edit Source</h4>

            <label>
              Source Title
              <input
                value={sourceForm.title}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    title: e.target.value,
                  })
                }
                required
              />
            </label>

            <label>
              Publisher
              <input
                value={sourceForm.publisher}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    publisher: e.target.value,
                  })
                }
                required
              />
            </label>

            <label>
              Source URL
              <input
                type="url"
                value={sourceForm.url}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    url: e.target.value,
                  })
                }
                required
              />
            </label>

            <label>
              Category
              <input
                value={sourceForm.category}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    category: e.target.value,
                  })
                }
              />
            </label>

            <label>
              Channel
              <select
                value={sourceForm.channel}
                onChange={(e) =>
                  setSourceForm({
                    ...sourceForm,
                    channel: e.target.value,
                  })
                }
              >
                <option value="any">Any</option>
                <option value="text">Text</option>
                <option value="email">Email</option>
                <option value="phone">Phone</option>
              </select>
            </label>

            <div className="source-form-actions">
              <button type="submit">Save Changes</button>
              <button type="button" onClick={cancelForm}>
                Cancel
              </button>
            </div>
          </form>
        )}

        <div className="dataset-toolbar">
          <p>
            {stats.active_sources} active / {stats.total_sources} total
            sources
          </p>

          <button
            type="button"
            onClick={loadDashboard}
            disabled={loadingSources}
          >
            {loadingSources ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {loadingSources ? (
          <p>Loading sources...</p>
        ) : sources.length === 0 ? (
          <p>No sources found. Add a trusted source to get started.</p>
        ) : (
          <div className="source-list">
            {sources.map((source) => (
              <div className="source-card" key={source.id}>
                <div className="source-card-header">
                  <div>
                    <h4>{source.title}</h4>
                    <p>{source.publisher}</p>
                  </div>

                  <span
                    className={
                      source.active
                        ? "source-status active"
                        : "source-status inactive"
                    }
                  >
                    {source.active ? "Active" : "Inactive"}
                  </span>
                </div>

                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {source.url}
                </a>

                <div className="source-metadata">
                  <span>Category: {source.category || "None"}</span>
                  <span>Channel: {source.channel || "any"}</span>
                  <span>Chunks: {source.chunk_count}</span>
                  <span>
                    Last ingested:{" "}
                    {source.last_ingested
                      ? new Date(source.last_ingested).toLocaleString()
                      : "Never"}
                  </span>
                </div>

                <div className="source-actions">
                  <button
                    type="button"
                    onClick={() => startEditing(source)}
                  >
                    Edit
                  </button>

                  <button
                    type="button"
                    onClick={() => toggleSource(source)}
                  >
                    {source.active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* DATA INGESTION */}
        <section className="developer-section">
        <h3>Data Ingestion</h3>

        <p>
            Fetch trusted sources, extract webpage content, and generate
            embeddings for the chatbot's knowledge base.
        </p>

        <button
            type="button"
            onClick={handleIngest}
            disabled={ingesting}
        >
            {ingesting ? "Ingesting..." : "Run Ingestion"}
        </button>

        {ingestionResult && (
            <div className="ingestion-results">
            <h4>Ingestion Results</h4>

            <p>
                Sources ingested: {ingestionResult.sources_ingested}
            </p>

            <p>
                Sources unchanged: {ingestionResult.sources_unchanged}
            </p>

            <p>
                Sources skipped: {ingestionResult.sources_skipped}
            </p>

            <p>
                New chunks created: {ingestionResult.chunks_created}
            </p>

            {ingestionResult.output && (
                <>
                <h4>Execution Details</h4>
                <pre>
                    <code>{ingestionResult.output}</code>
                </pre>
                </>
            )}

            {ingestionResult.errors && (
                <pre>
                <code>{ingestionResult.errors}</code>
                </pre>
            )}
            </div>
        )}
        </section>

      {/* USAGE STATISTICS */}
      <section className="developer-section">
        <h3>Knowledge Base Statistics</h3>
        <p>Monitor the current contents of your chatbot's knowledge base.</p>

        <div className="developer-stats">
          <div className="stat-card">
            <h4>{stats.total_sources}</h4>
            <p>Total Sources</p>
          </div>

          <div className="stat-card">
            <h4>{stats.active_sources}</h4>
            <p>Active Sources</p>
          </div>

          <div className="stat-card">
            <h4>{stats.inactive_sources}</h4>
            <p>Inactive Sources</p>
          </div>

          <div className="stat-card">
            <h4>{stats.total_chunks}</h4>
            <p>Total Chunks</p>
          </div>
        </div>
      </section>
    </div>
  );
}
