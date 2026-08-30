import React, { useState } from "react";

import {
  Routes,
  Route,
  Navigate,
  NavLink,
  useNavigate,
  useLocation
} from "react-router-dom";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  Camera,
  ChevronDown,
  CircleUserRound,
  FileText,
  Gauge,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MonitorPlay,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  UserRound,
  Video,
  Wifi,
  X,
  Zap
} from "lucide-react";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar
} from "recharts";


/* =====================================================
   DEMO DATA
   Later your backend teammate will replace this.
===================================================== */

const cameras = [
  {
    id: 1,
    name: "North Gate",
    location: "Sector A",
    status: "LIVE",
    detection: "Authorized"
  },
  {
    id: 2,
    name: "East Border",
    location: "Sector B",
    status: "LIVE",
    detection: "Intrusion Detected"
  },
  {
    id: 3,
    name: "West Tower",
    location: "Sector C",
    status: "LIVE",
    detection: "Vehicle Detected"
  },
  {
    id: 4,
    name: "South Perimeter",
    location: "Sector D",
    status: "LIVE",
    detection: "Watchlist Match"
  }
];


const alerts = [
  {
    id: 1,
    time: "21:45:21",
    camera: "Camera 2",
    event: "Intrusion Detected",
    level: "Critical",
    description: "Person crossed restricted virtual boundary."
  },
  {
    id: 2,
    time: "21:44:15",
    camera: "Camera 4",
    event: "Watchlist Match",
    level: "High",
    description: "Possible watchlist match detected."
  },
  {
    id: 3,
    time: "21:43:02",
    camera: "Camera 2",
    event: "Unidentified Person",
    level: "Medium",
    description: "Unknown person detected in restricted area."
  }
];


const events = [
  {
    time: "21:45:21",
    camera: "Camera 2",
    event: "Intrusion Detected",
    level: "Critical",
    status: "Active"
  },
  {
    time: "21:44:15",
    camera: "Camera 4",
    event: "Watchlist Match",
    level: "High",
    status: "Under Review"
  },
  {
    time: "21:43:02",
    camera: "Camera 2",
    event: "Unidentified Person",
    level: "Medium",
    status: "Monitoring"
  },
  {
    time: "21:42:33",
    camera: "Camera 1",
    event: "Authorized Access",
    level: "Low",
    status: "Resolved"
  },
  {
    time: "21:41:55",
    camera: "Camera 3",
    event: "Vehicle Detected",
    level: "Low",
    status: "Resolved"
  }
];


const chartData = [
  { time: "00:00", total: 18, critical: 2 },
  { time: "04:00", total: 28, critical: 2 },
  { time: "08:00", total: 42, critical: 3 },
  { time: "12:00", total: 35, critical: 2 },
  { time: "16:00", total: 61, critical: 4 },
  { time: "20:00", total: 74, critical: 6 },
  { time: "24:00", total: 86, critical: 8 }
];


const alertDistribution = [
  { name: "Critical", value: 7 },
  { name: "High", value: 13 },
  { name: "Medium", value: 27 },
  { name: "Low", value: 53 }
];


/* =====================================================
   LOGIN
===================================================== */

function Login() {

  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleLogin(e) {

    e.preventDefault();

    localStorage.setItem(
      "borderguard_user",
      JSON.stringify({
        email: email,
        name: "Command Operator"
      })
    );

    navigate("/");
  }

  return (

    <div className="auth-page">

      <div className="auth-card">

        <div className="auth-logo">
          <ShieldCheck size={28} />
        </div>

        <div className="eyebrow">
          BORDERGUARD AI
        </div>

        <h1>
          Welcome back
        </h1>

        <p>
          Sign in to access the Border Surveillance
          Command Center.
        </p>


        <form
          className="auth-form"
          onSubmit={handleLogin}
        >

          <label>
            Email

            <input
              type="email"
              placeholder="operator@example.com"
              value={email}
              onChange={(e) =>
                setEmail(e.target.value)
              }
              required
            />

          </label>


          <label>
            Password

            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) =>
                setPassword(e.target.value)
              }
              required
            />

          </label>


          <button
            className="primary-btn full"
            type="submit"
          >

            Sign In

            <Zap size={16} />

          </button>

        </form>


        <div className="demo-message">

          <strong>Demo authentication</strong>

          <br />

          This login is currently frontend-only.
          Your backend teammate will connect real authentication later.

        </div>

      </div>

    </div>
  );
}


/* =====================================================
   PROTECTED ROUTE
===================================================== */

function ProtectedRoute({ children }) {

  const user =
    localStorage.getItem("borderguard_user");

  if (!user) {

    return (
      <Navigate
        to="/login"
        replace
      />
    );

  }

  return children;
}


/* =====================================================
   MAIN APPLICATION
===================================================== */

function App() {

  return (

    <Routes>

      <Route
        path="/login"
        element={<Login />}
      />

      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      />

    </Routes>

  );
}


/* =====================================================
   DASHBOARD LAYOUT
===================================================== */

function DashboardLayout() {

  const [mobileMenu, setMobileMenu] =
    useState(false);

  const navigate = useNavigate();

  const location = useLocation();

  const user =
    JSON.parse(
      localStorage.getItem("borderguard_user")
      || "{}"
    );


  function logout() {

    localStorage.removeItem(
      "borderguard_user"
    );

    navigate("/login");

  }


  return (

    <div className="app">

      {/* ================= SIDEBAR ================= */}

      <aside
        className={
          mobileMenu
            ? "sidebar open"
            : "sidebar"
        }
      >

        <div className="brand">

          <div className="brand-icon">

            <ShieldCheck size={20} />

          </div>

          <div>

            <strong>
              BORDERGUARD
            </strong>

            <span>
              AI COMMAND CENTER
            </span>

          </div>

        </div>


        <div className="nav-title">
          OPERATIONS
        </div>


        <nav>

          <Navigation
            to="/"
            icon={<LayoutDashboard size={17} />}
            text="Dashboard"
          />

          <Navigation
            to="/monitoring"
            icon={<MonitorPlay size={17} />}
            text="Live Monitoring"
          />

          <Navigation
            to="/alerts"
            icon={<Bell size={17} />}
            text="Alerts"
            badge="3"
          />

          <Navigation
            to="/events"
            icon={<History size={17} />}
            text="Event History"
          />

          <Navigation
            to="/cameras"
            icon={<Camera size={17} />}
            text="Camera Management"
          />

        </nav>


        <div className="nav-title">
          ANALYTICS
        </div>


        <nav>

          <Navigation
            to="/analytics"
            icon={<BarChart3 size={17} />}
            text="System Analytics"
          />

          <Navigation
            to="/reports"
            icon={<FileText size={17} />}
            text="Reports"
          />

          <Navigation
            to="/settings"
            icon={<Settings size={17} />}
            text="Settings"
          />

        </nav>


        {/* AI STATUS */}

        <div className="model-status">

          <div className="status-heading">
            AI MODELS STATUS
          </div>

          {[
            "Object Detection",
            "Face Recognition",
            "Scene Analysis",
            "Anomaly Detection",
            "Tracking"
          ].map((model) => (

            <div
              className="model-row"
              key={model}
            >

              <span>
                {model}
              </span>

              <b>
                Active
              </b>

            </div>

          ))}

        </div>


        {/* USER */}

        <div className="sidebar-bottom">

          <div className="operator">

            <div className="avatar">
              <UserRound size={15} />
            </div>

            <div>

              <strong>
                {user.name || "Operator"}
              </strong>

              <span>
                Administrator
              </span>

            </div>

          </div>


          <button
            className="logout"
            onClick={logout}
          >

            <LogOut size={16} />

            Sign Out

          </button>

        </div>

      </aside>


      {/* MOBILE OVERLAY */}

      {mobileMenu && (

        <div
          className="mobile-overlay"
          onClick={() => setMobileMenu(false)}
        />

      )}


      {/* ================= MAIN ================= */}

      <main className="main">

        <header className="topbar">

          <button
            className="mobile-menu"
            onClick={() =>
              setMobileMenu(true)
            }
          >
            <Menu size={19} />
          </button>


          <div className="breadcrumb">

            COMMAND CENTER

            <span>/</span>

            <strong>
              {getPageName(
                location.pathname
              )}
            </strong>

          </div>


          <div className="top-right">

            <div className="operational">

              <i />

              OPERATIONAL

            </div>

            <span className="utc">
              2026-08-30 14:09 UTC
            </span>


            <div className="user-top">

              <CircleUserRound
                size={17}
              />

              Operator

              <ChevronDown size={13} />

            </div>

          </div>

        </header>


        <div className="content">

          <Routes>

            <Route
              path="/"
              element={<Dashboard />}
            />

            <Route
              path="/monitoring"
              element={<Monitoring />}
            />

            <Route
              path="/alerts"
              element={<Alerts />}
            />

            <Route
              path="/events"
              element={<Events />}
            />

            <Route
              path="/cameras"
              element={<Cameras />}
            />

            <Route
              path="/analytics"
              element={<Analytics />}
            />

            <Route
              path="/reports"
              element={<Reports />}
            />

            <Route
              path="/settings"
              element={<SettingsIcon/>}
            />

            <Route
              path="*"
              element={
                <Navigate to="/" />
              }
            />

          </Routes>

        </div>

      </main>

    </div>

  );
}


/* =====================================================
   NAVIGATION COMPONENT
===================================================== */

function Navigation({
  to,
  icon,
  text,
  badge
}) {

  return (

    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        isActive
          ? "nav-link active"
          : "nav-link"
      }
    >

      {icon}

      <span>
        {text}
      </span>

      {badge && (
        <em>
          {badge}
        </em>
      )}

    </NavLink>

  );
}


/* =====================================================
   PAGE NAME
===================================================== */

function getPageName(path) {

  if (path === "/")
    return "Dashboard";

  return path
    .replace("/", "")
    .replace("-", " ")
    .replace(/\b\w/g, c =>
      c.toUpperCase()
    );

}


/* =====================================================
   PAGE HEADER
===================================================== */

function PageHeader({
  title,
  subtitle
}) {

  return (

    <div className="page-header">

      <div>

        <div className="eyebrow">
          BORDER SURVEILLANCE
        </div>

        <h2>
          {title}
        </h2>

        <p>
          {subtitle}
        </p>

      </div>

    </div>

  );
}


/* =====================================================
   STAT CARD
===================================================== */

function StatCard({
  icon,
  label,
  value,
  note,
  danger
}) {

  return (

    <div
      className={
        danger
          ? "stat-card danger"
          : "stat-card"
      }
    >

      <div className="stat-icon">
        {icon}
      </div>

      <div>

        <span>
          {label}
        </span>

        <strong>
          {value}
        </strong>

        <small>
          {note}
        </small>

      </div>

    </div>

  );
}


/* =====================================================
   DASHBOARD
===================================================== */

function Dashboard() {

  return (

    <>

      <PageHeader
        title="Border Surveillance Dashboard"
        subtitle="Real-time overview of cameras, AI detections, alerts and system health."
      />


      {/* STATISTICS */}

      <div className="stats-grid">

        <StatCard
          icon={<Camera />}
          label="TOTAL CAMERAS"
          value="4"
          note="Active"
        />

        <StatCard
          icon={<Activity />}
          label="NORMAL EVENTS"
          value="12"
          note="Today"
        />

        <StatCard
          icon={<AlertTriangle />}
          label="SUSPICIOUS EVENTS"
          value="3"
          note="Today"
        />

        <StatCard
          icon={<Bell />}
          label="CRITICAL ALERTS"
          value="1"
          note="Active"
          danger
        />

        <StatCard
          icon={<UserRound />}
          label="FACES DETECTED"
          value="8"
          note="Today"
        />

        <StatCard
          icon={<Gauge />}
          label="SYSTEM UPTIME"
          value="99.7%"
          note="Last 30 days"
        />

      </div>


      {/* FIRST ROW */}

      <div className="dashboard-grid">

        <Panel title="REAL-TIME EVENT FEED">

          <EventTable />

        </Panel>


        <Panel title="THREAT LEVEL OVERVIEW">

          <div className="threat">

            <div className="threat-circle">

              <strong>
                100%
              </strong>

              <span>
                ANALYSIS
              </span>

            </div>


            <div>

              <small>
                CURRENT LEVEL
              </small>

              <h3>
                ELEVATED
              </h3>

              <p>
                High situational awareness required.
              </p>

            </div>

          </div>


          <div className="legend">

            {alertDistribution.map(
              (item) => (

                <div
                  key={item.name}
                >

                  <span>
                    ●
                  </span>

                  {item.name}

                  <b>
                    {item.value}%
                  </b>

                </div>

              )
            )}

          </div>

        </Panel>

      </div>


      {/* CAMERA ROW */}

      <div className="dashboard-grid">

        <Panel title="LIVE CAMERA OVERVIEW">

          <div className="camera-grid">

            {cameras.map(
              camera => (

                <CameraCard
                  key={camera.id}
                  camera={camera}
                />

              )
            )}

          </div>

        </Panel>


        <Panel title="SYSTEM INFORMATION">

          <div className="system-info">

            <InfoRow
              title="Recording Status"
              value="ON"
              good
            />

            <InfoRow
              title="Storage Used"
              value="2.4 TB / 10 TB"
            />

            <InfoRow
              title="Network Status"
              value="Connected"
              good
            />

            <InfoRow
              title="Last Backup"
              value="30 Aug 2026"
            />

            <InfoRow
              title="AI Processing"
              value="Real-time"
              good
            />

          </div>

        </Panel>

      </div>

    </>

  );
}


/* =====================================================
   PANEL
===================================================== */

function Panel({
  title,
  children
}) {

  return (

    <section className="panel">

      <div className="panel-header">

        <h3>
          {title}
        </h3>

      </div>

      {children}

    </section>

  );
}


/* =====================================================
   EVENT TABLE
===================================================== */

function EventTable() {

  return (

    <div className="table-container">

      <table>

        <thead>

          <tr>

            <th>TIME</th>
            <th>CAMERA</th>
            <th>EVENT</th>
            <th>LEVEL</th>
            <th>STATUS</th>

          </tr>

        </thead>


        <tbody>

          {events.map(
            event => (

              <tr key={event.time}>

                <td className="mono">
                  {event.time}
                </td>

                <td>
                  {event.camera}
                </td>

                <td>
                  {event.event}
                </td>

                <td>

                  <Level
                    level={event.level}
                  />

                </td>

                <td>
                  {event.status}
                </td>

              </tr>

            )
          )}

        </tbody>

      </table>

    </div>

  );
}


/* =====================================================
   LEVEL
===================================================== */

function Level({ level }) {

  return (

    <span
      className={
        "level " +
        level.toLowerCase()
      }
    >
      {level}
    </span>

  );

}


/* =====================================================
   CAMERA CARD
===================================================== */

function CameraCard({
  camera
}) {

  return (

    <div className="camera-card">

      <div className="camera-preview">

        <Camera size={25} />

        <span>
          CAMERA {camera.id}
        </span>

      </div>


      <div className="camera-info">

        <strong>
          {camera.name}
        </strong>

        <span className="live">
          ● {camera.status}
        </span>

      </div>


      <small>
        {camera.location}
      </small>

    </div>

  );
}


/* =====================================================
   INFO ROW
===================================================== */

function InfoRow({
  title,
  value,
  good
}) {

  return (

    <div className="info-row">

      <span>
        {title}
      </span>

      <b
        className={
          good ? "good" : ""
        }
      >
        {value}
      </b>

    </div>

  );

}


/* =====================================================
   LIVE MONITORING
===================================================== */

function Monitoring() {

  return (

    <>

      <PageHeader
        title="Live Monitoring"
        subtitle="Monitor connected CCTV feeds and AI-generated detections."
      />


      <div className="monitor-layout">

        <div className="video-grid">

          {cameras.map(
            camera => (

              <CameraFeed
                key={camera.id}
                camera={camera}
              />

            )
          )}

        </div>


        <div className="alert-sidebar">

          <Panel title="LIVE ALERTS">

            {alerts.map(
              alert => (

                <AlertCard
                  key={alert.id}
                  alert={alert}
                />

              )
            )}

          </Panel>

        </div>

      </div>


      <div className="monitor-bottom">

        <Panel title="ACTIVITY OVER TIME (24H)">

          <ActivityChart />

        </Panel>


        <Panel title="ALERT DISTRIBUTION">

          <DistributionChart />

        </Panel>


        <Panel title="TOP DETECTED OBJECTS">

          <ObjectList />

        </Panel>

      </div>

    </>

  );
}


/* =====================================================
   CAMERA FEED
===================================================== */

function CameraFeed({
  camera
}) {

  const critical =
    camera.id === 2;

  return (

    <div className="camera-feed">

      <div className="fake-video">

        <div className="sky" />

        <div className="ground" />

        <div className="fence" />

        <div
          className={
            critical
              ? "person-box critical"
              : "person-box"
          }
        >

          <span>
            Person ID:{" "}
            {critical
              ? "Unknown"
              : camera.id + 10}
          </span>

        </div>


        <div
          className={
            critical
              ? "virtual-boundary red"
              : "virtual-boundary"
          }
        />

        <div className="demo-video">
          DEMO VIDEO FEED
        </div>

      </div>


      <div className="feed-title">

        <strong>
          CAMERA {camera.id} ·{" "}
          {camera.name.toUpperCase()}
        </strong>

        <span>
          ● LIVE
        </span>

      </div>


      <div className="feed-time">
        21:45:32
      </div>


      <div
        className={
          critical
            ? "feed-alert critical"
            : "feed-alert"
        }
      >
        {camera.detection}
      </div>


      <div className="feed-footer">

        <span>
          ◉ AI
        </span>

        <span>
          Tracking
        </span>

        <span>
          Virtual Boundary
        </span>

      </div>

    </div>

  );
}


/* =====================================================
   ALERTS
===================================================== */

function Alerts() {

  const [filter, setFilter] =
    useState("All");


  const filtered =
    filter === "All"
      ? alerts
      : alerts.filter(
          alert =>
            alert.level === filter
        );


  return (

    <>

      <PageHeader
        title="Alerts Center"
        subtitle="Review and manage AI-generated security alerts."
      />


      <div className="filters">

        {[
          "All",
          "Critical",
          "High",
          "Medium",
          "Low"
        ].map(
          option => (

            <button
              key={option}
              className={
                filter === option
                  ? "filter active"
                  : "filter"
              }
              onClick={() =>
                setFilter(option)
              }
            >
              {option}
            </button>

          )
        )}


        <div className="search">

          <Search size={15} />

          <input
            placeholder="Search alerts..."
          />

        </div>

      </div>


      <div className="alert-grid">

        {filtered.map(
          alert => (

            <AlertCard
              key={alert.id}
              alert={alert}
              detailed
            />

          )
        )}

      </div>

    </>

  );
}


/* =====================================================
   ALERT CARD
===================================================== */

function AlertCard({
  alert,
  detailed
}) {

  return (

    <div
      className={
        "alert-card " +
        alert.level.toLowerCase()
      }
    >

      <div className="alert-top">

        <Level
          level={alert.level}
        />

        <span className="mono">
          {alert.time}
        </span>

      </div>


      <h3>
        {alert.event}
      </h3>

      <p>
        {alert.description}
      </p>


      <div className="alert-meta">

        <span>
          {alert.camera}
        </span>

        <span>
          Active
        </span>

      </div>


      {detailed && (

        <div className="alert-buttons">

          <button className="secondary-btn">
            View Event
          </button>

          <button className="primary-btn small">
            Acknowledge
          </button>

        </div>

      )}

    </div>

  );
}


/* =====================================================
   EVENTS
===================================================== */

function Events() {

  return (

    <>

      <PageHeader
        title="Event History"
        subtitle="Searchable history of detections and security events."
      />


      <Panel title="EVENT LOG">

        <div className="event-search">

          <Search size={15} />

          <input
            placeholder="Search event history..."
          />

        </div>

        <EventTable />

      </Panel>

    </>

  );
}


/* =====================================================
   CAMERAS
===================================================== */

function Cameras() {

  return (

    <>

      <PageHeader
        title="Camera Management"
        subtitle="Manage connected CCTV cameras."
      />


      <div className="management-grid">

        {cameras.map(
          camera => (

            <div
              className="management-card"
              key={camera.id}
            >

              <div className="management-preview">

                <Camera size={30} />

                <span>
                  CAMERA {camera.id}
                </span>

                <div className="live">
                  ● LIVE
                </div>

              </div>


              <div className="management-body">

                <div>

                  <small>
                    CAMERA {camera.id}
                  </small>

                  <h3>
                    {camera.name}
                  </h3>

                  <p>
                    {camera.location}
                  </p>

                </div>


                <button className="icon-btn">
                  <SettingsIcon size={17} />
                </button>

              </div>


              <div className="tags">

                <span>
                  IP CAMERA
                </span>

                <span>
                  AI ENABLED
                </span>

                <span>
                  RECORDING ON
                </span>

              </div>

            </div>

          )
        )}

      </div>

    </>

  );
}


/* =====================================================
   ANALYTICS
===================================================== */

function Analytics() {

  return (

    <>

      <PageHeader
        title="System Analytics"
        subtitle="Operational metrics and AI detection trends."
      />


      <div className="analytics-grid">

        <Panel title="EVENT ACTIVITY">

          <ActivityChart />

        </Panel>


        <Panel title="ALERT DISTRIBUTION">

          <DistributionChart />

        </Panel>


        <Panel title="CAMERA EVENT LOAD">

          <CameraBarChart />

        </Panel>

      </div>

    </>

  );
}


/* =====================================================
   ACTIVITY CHART
===================================================== */

function ActivityChart() {

  return (

    <div className="chart">

      <ResponsiveContainer
        width="100%"
        height="100%"
      >

        <AreaChart
          data={chartData}
        >

          <XAxis
            dataKey="time"
            stroke="#6e88a3"
          />

          <YAxis
            stroke="#6e88a3"
          />

          <Tooltip />

          <Area
            type="monotone"
            dataKey="total"
            stroke="#16b9c9"
            fill="#16b9c9"
            fillOpacity={0.12}
          />

          <Area
            type="monotone"
            dataKey="critical"
            stroke="#ef4b5f"
            fill="transparent"
          />

        </AreaChart>

      </ResponsiveContainer>

    </div>

  );
}


/* =====================================================
   PIE CHART
===================================================== */

function DistributionChart() {

  const colors = [
    "#ef4b5f",
    "#ff9f43",
    "#9c6cff",
    "#16b9c9"
  ];


  return (

    <div className="chart">

      <ResponsiveContainer
        width="100%"
        height="100%"
      >

        <PieChart>

          <Pie
            data={alertDistribution}
            dataKey="value"
            innerRadius={55}
            outerRadius={80}
          >

            {alertDistribution.map(
              (_, index) => (

                <Cell
                  key={index}
                  fill={colors[index]}
                />

              )
            )}

          </Pie>

        </PieChart>

      </ResponsiveContainer>

    </div>

  );
}


/* =====================================================
   BAR CHART
===================================================== */

function CameraBarChart() {

  const data = [
    { name: "CAM 1", events: 24 },
    { name: "CAM 2", events: 39 },
    { name: "CAM 3", events: 18 },
    { name: "CAM 4", events: 31 }
  ];


  return (

    <div className="chart">

      <ResponsiveContainer
        width="100%"
        height="100%"
      >

        <BarChart data={data}>

          <XAxis
            dataKey="name"
            stroke="#6e88a3"
          />

          <YAxis
            stroke="#6e88a3"
          />

          <Tooltip />

          <Bar
            dataKey="events"
            fill="#16b9c9"
          />

        </BarChart>

      </ResponsiveContainer>

    </div>

  );
}


/* =====================================================
   OBJECT LIST
===================================================== */

function ObjectList() {

  return (

    <div className="object-list">

      <div>

        <UserRound />

        Persons

        <b>
          45
        </b>

      </div>


      <div>

        <Video />

        Vehicles

        <b>
          12
        </b>

      </div>


      <div>

        <Search />

        Unidentified

        <b>
          7
        </b>

      </div>


      <div>

        <Bell />

        Watchlist Matches

        <b>
          3
        </b>

      </div>

    </div>

  );
}


/* =====================================================
   REPORTS
===================================================== */

function Reports() {

  const reports = [
    [
      "Daily Operations Report",
      "Events, alerts and camera activity."
    ],
    [
      "Incident Summary",
      "Critical and high priority events."
    ],
    [
      "System Health Report",
      "Network, storage and AI status."
    ]
  ];


  return (

    <>

      <PageHeader
        title="Reports"
        subtitle="Generate operational reports."
      />


      <div className="reports">

        {reports.map(
          report => (

            <div
              className="report-card"
              key={report[0]}
            >

              <div className="report-icon">
                <FileText />
              </div>


              <div>

                <h3>
                  {report[0]}
                </h3>

                <p>
                  {report[1]}
                </p>

              </div>


              <button className="secondary-btn">
                Preview
              </button>

            </div>

          )
        )}

      </div>

    </>

  );
}


/* =====================================================
   SETTINGS
===================================================== */

function Settings() {

  const [notifications, setNotifications] =
    useState(true);


  return (

    <>

      <PageHeader
        title="Settings"
        subtitle="Configure operator preferences."
      />


      <div className="settings-grid">

        <Panel title="OPERATOR PROFILE">

          <div className="profile">

            <div className="avatar large">
              <UserRound />
            </div>

            <div>

              <h3>
                Command Operator
              </h3>

              <p>
                Administrator
              </p>

            </div>

          </div>

        </Panel>


        <Panel title="NOTIFICATIONS">

          <Toggle
            text="Critical alert notifications"
            enabled={notifications}
            onClick={() =>
              setNotifications(!notifications)
            }
          />

          <Toggle
            text="System health notifications"
            enabled
          />

          <Toggle
            text="Daily report reminder"
          />

        </Panel>


        <Panel title="BACKEND CONNECTION">

          <div className="connection">

            <Wifi />

            <div>

              <strong>
                Frontend Mock API
              </strong>

              <span>
                Ready for backend integration
              </span>

            </div>

            <b>
              Connected
            </b>

          </div>

        </Panel>

      </div>

    </>

  );
}


/* =====================================================
   TOGGLE
===================================================== */

function Toggle({
  text,
  enabled,
  onClick
}) {

  return (

    <div className="toggle-row">

      <span>
        {text}
      </span>

      <button
        className={
          enabled
            ? "toggle on"
            : "toggle"
        }
        onClick={onClick}
      >

        <i />

      </button>

    </div>

  );
}


export default App;