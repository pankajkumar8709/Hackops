import { useNavigate } from 'react-router-dom';
import { clearToken, getRole } from '../../api';

export default function TopBar({ title, subtitle, onMenuToggle }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearToken();
    navigate('/');
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="topbar-mobile-toggle" onClick={onMenuToggle} aria-label="Toggle menu">
          ☰
        </button>
        <div className="topbar-breadcrumb">
          <span className="topbar-breadcrumb-current">{title}</span>
          {subtitle && (
            <>
              <span className="text-muted">/</span>
              <span className="text-muted">{subtitle}</span>
            </>
          )}
        </div>
      </div>
      <div className="topbar-right">
        <div className="badge badge-neutral">
          {getRole() === 'organizer' ? '🛠 Organizer' : '🎯 Participant'}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={handleLogout}>
          Logout
        </button>
      </div>
    </header>
  );
}
