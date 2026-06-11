import { Navigate, Route, Routes } from 'react-router-dom';
import DetailPage from './pages/DetailPage';
import HomePage from './pages/HomePage';
import PlayerPage from './pages/PlayerPage';
import SearchPage from './pages/SearchPage';
import AiSearchPage from './pages/AiSearchPage';
import TheaterPage from './pages/TheaterPage';
import ProfilePage from './pages/ProfilePage';

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route path="/home" element={<HomePage />} />
        <Route path="/detail" element={<DetailPage />} />
        <Route path="/player" element={<PlayerPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/ai" element={<AiSearchPage />} />
        <Route path="/theater" element={<TheaterPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Routes>
    </div>
  );
}
