import { NavLink, Route, Routes } from "react-router-dom";
import MapView from "./pages/MapView";
import Reliability from "./pages/Reliability";
import News from "./pages/News";

const navItem = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-full text-sm transition ${
    isActive
      ? "bg-peach text-ink"
      : "text-ink2 hover:bg-sand"
  }`;

export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-cream">
      <header className="flex items-center gap-4 px-4 py-2 bg-white/80 backdrop-blur border-b border-sand shrink-0">
        <div className="font-semibold tracking-tight text-ink">
          KL Transit Tracker
        </div>
        <nav className="flex gap-1">
          <NavLink to="/" end className={navItem}>Map</NavLink>
          <NavLink to="/reliability" className={navItem}>Reliability</NavLink>
          <NavLink to="/news" className={navItem}>News</NavLink>
        </nav>
        <div className="ml-auto text-xs text-ink2">v0.1.0</div>
      </header>
      <main className="flex-1 min-h-0 relative">
        <Routes>
          <Route path="/" element={<MapView />} />
          <Route path="/reliability" element={<Reliability />} />
          <Route path="/news" element={<News />} />
        </Routes>
      </main>
    </div>
  );
}
