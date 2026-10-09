
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import "../styles/login.css";

const USERS = {
  clinical: {
    email: "report@signal.local",
    password: "SIGNAL2026",
    name: "SIGNAL Clinical Staff",
    role: "Clinical Staff",
    redirect: "/dashboard",
  },
  admin: {
    email: "admin@signal.local",
    password: "SIGNALADMIN2026",
    name: "SIGNAL Administrator",
    role: "Administrator",
    redirect: "/admin/dashboard",
  },
};

export default function Login() {
  const navigate = useNavigate();

  const [selectedRole, setSelectedRole] = useState("clinical");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const user = USERS[selectedRole];

  function changeRole(role) {
    setSelectedRole(role);
    setEmail("");
    setPassword("");
    setShowPassword(false);
    setError("");
  }

  function handleSubmit(event) {
    event.preventDefault();

    if (loading) return;

    setError("");

    if (!email.trim() || !password) {
      setError("Please enter your work email and password.");
      return;
    }

    const selectedUser = USERS[selectedRole];

    // Demo authentication using the accounts configured above.
    if (
      email.trim().toLowerCase() !== selectedUser.email.toLowerCase() ||
      password !== selectedUser.password
    ) {
      setError("Invalid email or password.");
      return;
    }

    setLoading(true);

    // Clear any previous role from both storage locations.
    sessionStorage.removeItem("signal-auth");
    sessionStorage.removeItem("signal-user");
    localStorage.removeItem("signal-auth");
    localStorage.removeItem("signal-user");

    const storage = rememberMe ? localStorage : sessionStorage;

    storage.setItem("signal-auth", "true");
    storage.setItem(
      "signal-user",
      JSON.stringify({
        name: selectedUser.name,
        email: selectedUser.email,
        role: selectedUser.role,
      })
    );

    // Administrator and Clinical Staff use different applications.
    navigate(selectedUser.redirect, { replace: true });
  }

  return (
    <main className="login-page">
      <section className="login-left">
        <div className="login-brand">
          <div className="login-brand-mark">S</div>

          <div>
            <div className="login-brand-title">SIGNAL</div>
            <div className="login-brand-subtitle">
              PUBLIC HEALTH INTELLIGENCE
            </div>
          </div>
        </div>

        <div className="login-content">
          <div className="login-kicker">PUBLIC HEALTH REPORTING</div>

          <h1>
            Intelligent public health reporting
            <br />
            for healthcare organizations.
          </h1>

          <p>
            AI-assisted intelligence that transforms clinical and laboratory
            information into complete, jurisdiction-aware public health
            reporting workflows.
          </p>

          <div className="login-flow">
            <div className="login-flow-item">
              <span>01</span>
              <div>
                <strong>Prepare</strong>
                <small>
                  Organize clinical and laboratory information.
                </small>
              </div>
            </div>

            <div className="login-flow-item">
              <span>02</span>
              <div>
                <strong>Decide</strong>
                <small>
                  Determine jurisdiction and reportability.
                </small>
              </div>
            </div>

            <div className="login-flow-item">
              <span>03</span>
              <div>
                <strong>Report</strong>
                <small>Track reporting and acknowledgement.</small>
              </div>
            </div>
          </div>
        </div>

        <div className="login-footer">
          Synthetic demonstration environment
        </div>
      </section>

      <section className="login-right">
        <form className="login-card" onSubmit={handleSubmit}>
          <div className="login-role-tabs" aria-label="Choose your role">
            <button
              type="button"
              className={`login-role-tab ${
                selectedRole === "clinical" ? "active" : ""
              }`}
              aria-pressed={selectedRole === "clinical"}
              onClick={() => changeRole("clinical")}
              disabled={loading}
            >
              Clinical Staff
            </button>

            <button
              type="button"
              className={`login-role-tab ${
                selectedRole === "admin" ? "active" : ""
              }`}
              aria-pressed={selectedRole === "admin"}
              onClick={() => changeRole("admin")}
              disabled={loading}
            >
              Administrator
            </button>
          </div>

          <div className="login-card-header">
            <div className="login-card-mark">S</div>

            <div className="login-card-heading">
              <div className="login-card-kicker">
                {user.role.toUpperCase()}
              </div>

              <h2>Sign in to your workspace</h2>

              <p>
                Enter your credentials to access the{" "}
                {selectedRole === "admin" ? "administrative" : "clinical"}{" "}
                reporting workspace.
              </p>
            </div>
          </div>

          <div className="login-form-group">
            <label htmlFor="email">Work Email</label>

            <input
              id="email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@hospital.org"
              autoComplete="username"
              required
              disabled={loading}
            />
          </div>

          <div className="login-form-group">
            <label htmlFor="password">Password</label>

            <div className="login-password-field">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
                disabled={loading}
              />

              <button
                type="button"
                className="password-visibility-toggle"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                disabled={loading}
              >
                {showPassword ? (
                  <EyeOff size={19} />
                ) : (
                  <Eye size={19} />
                )}
              </button>
            </div>
          </div>

          <div className="login-options">
            <label className="login-remember">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(event) => setRememberMe(event.target.checked)}
                disabled={loading}
              />
              <span>Remember me</span>
            </label>

            <button
              type="button"
              className="forgot-password"
              onClick={() =>
                setError("Password recovery is not enabled yet.")
              }
              disabled={loading}
            >
              Forgot password?
            </button>
          </div>

          {error && (
            <div className="login-error" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="login-submit"
            disabled={loading}
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>

          <p className="login-security-note">
            Authorized access to the SIGNAL reporting workspace.
          </p>
        </form>

        <div className="login-copyright">
          © SIGNAL · Public Health Reporting Intelligence Layer
        </div>
      </section>
    </main>
  );
}
