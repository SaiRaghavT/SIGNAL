import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import "../styles/login.css";

const DEMO_USERS = {
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

function Login() {
  const navigate = useNavigate();

  const [selectedRole, setSelectedRole] = useState("clinical");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const selectedUser = DEMO_USERS[selectedRole];

  const isAuthenticated =
    sessionStorage.getItem("signal-auth") === "true" ||
    localStorage.getItem("signal-auth") === "true";

  if (isAuthenticated) {
    const storedUser =
      JSON.parse(
        sessionStorage.getItem("signal-user") ||
          localStorage.getItem("signal-user") ||
          "null"
      ) || {};

    if (storedUser.role === "Administrator") {
      return <Navigate to="/admin/dashboard" replace />;
    }

    return <Navigate to="/dashboard" replace />;
  }

  const handleRoleChange = (role) => {
    setSelectedRole(role);
    setEmail("");
    setPassword("");
    setError("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setLoading(true);

    /*
      TEMPORARY DEMO LOGIN

      Later this will become:

      POST /api/auth/login

      {
        email,
        password
      }
    */

    await new Promise((resolve) => setTimeout(resolve, 500));

    if (
      email.trim().toLowerCase() === selectedUser.email.toLowerCase() &&
      password === selectedUser.password
    ) {
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

      navigate(selectedUser.redirect, { replace: true });
    } else {
      setError(
        `Invalid ${selectedUser.role.toLowerCase()} demo credentials.`
      );
    }

    setLoading(false);
  };

  return (
    <main className="login-page">
      {/* LEFT SIDE */}
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
            AI-assisted intelligence that transforms clinical
            and laboratory information into complete,
            jurisdiction-aware public health reporting workflows.
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

                <small>
                  Track reporting, acknowledgement and follow-up.
                </small>
              </div>
            </div>
          </div>
        </div>

        <div className="login-footer">
          Synthetic demonstration environment
        </div>
      </section>

      {/* RIGHT SIDE */}
      <section className="login-right">
        <form
          className="login-card"
          onSubmit={handleSubmit}
        >
          {/* ROLE TABS */}
          <div className="login-role-tabs">
            <button
              type="button"
              className={`login-role-tab ${
                selectedRole === "clinical"
                  ? "active"
                  : ""
              }`}
              onClick={() => handleRoleChange("clinical")}
              disabled={loading}
            >
              Clinical Staff
            </button>

            <button
              type="button"
              className={`login-role-tab ${
                selectedRole === "admin"
                  ? "active"
                  : ""
              }`}
              onClick={() => handleRoleChange("admin")}
              disabled={loading}
            >
              Administrator
            </button>
          </div>

          {/* HEADER */}
          <div className="login-card-header">
            <div className="login-card-mark">S</div>

            <div>
              <div className="login-card-kicker">
                {selectedRole === "clinical"
                  ? "CLINICAL STAFF"
                  : "ADMINISTRATOR"}
              </div>

              <h2>Sign in to SIGNAL</h2>

              <p>
                Enter your credentials to access{" "}
                {selectedRole === "clinical"
                  ? "the clinical reporting workspace."
                  : "the administrative reporting workspace."}
              </p>
            </div>
          </div>

          {/* EMAIL */}
          <div className="login-form-group">
            <label htmlFor="email">
              Work Email
            </label>

            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@hospital.org"
              autoComplete="username"
              disabled={loading}
            />
          </div>

          {/* PASSWORD */}
          <div className="login-form-group">
            <label htmlFor="password">
              Password
            </label>

            <div className="login-password-field">
              <input
                id="password"
                type={
                  showPassword
                    ? "text"
                    : "password"
                }
                value={password}
                onChange={(e) =>
                  setPassword(e.target.value)
                }
                placeholder="Enter your password"
                autoComplete="current-password"
                disabled={loading}
              />

              <button
                type="button"
                className="password-visibility-toggle"
                onClick={() =>
                  setShowPassword(
                    (visible) => !visible
                  )
                }
                aria-label={
                  showPassword
                    ? "Hide password"
                    : "Show password"
                }
                aria-pressed={showPassword}
                aria-controls="password"
                disabled={loading}
              >
                {showPassword ? (
                  <EyeOff
                    size={19}
                    aria-hidden="true"
                  />
                ) : (
                  <Eye
                    size={19}
                    aria-hidden="true"
                  />
                )}
              </button>
            </div>
          </div>

          {/* OPTIONS */}
          <div className="login-options">
            <label>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) =>
                  setRememberMe(e.target.checked)
                }
              />

              <span>Remember me</span>
            </label>

            <button
              type="button"
              className="forgot-password"
              onClick={() =>
                setError(
                  "Password recovery is not enabled yet."
                )
              }
            >
              Forgot password?
            </button>
          </div>

          {/* ERROR */}
          {error && (
            <div className="login-error">
              {error}
            </div>
          )}

          {/* SIGN IN */}
          <button
            type="submit"
            className="login-submit"
            disabled={loading}
          >
            {loading
              ? "Signing in..."
              : "Sign in to SIGNAL →"}
          </button>

        </form>

        <div className="login-copyright">
          © SIGNAL · Public Health Reporting Intelligence Layer
        </div>
      </section>
    </main>
  );
}

export default Login;
