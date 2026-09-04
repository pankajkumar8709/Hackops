import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { clearToken, getRole, isOrganizer } from '../../api';

const organizerLinks = [
  { section: 'OVERVIEW' },
  { to: '/organizer', icon: '📊', label: 'Dashboard', end: true },
  { section: 'SETUP' },
  { to: '/organizer/setup', icon: '🛠️', label: 'Event Setup' },
  { section: 'EVENT' },
  { to: '/organizer/participants', icon: '👤', label: 'Participants' },
  { to: '/organizer/teams', icon: '👥', label: 'Teams' },
  { to: '/organizer/submissions', icon: '📋', label: 'Submissions' },
  { to: '/organizer/mentors', icon: '🎓', label: 'Mentors' },
  { to: '/organizer/resources', icon: '📦', label: 'Resources' },
  { section: 'OPERATIONS' },
  { to: '/organizer/escalations', icon: '🚨', label: 'Escalations' },
  { to: '/organizer/agent', icon: '🤖', label: 'Agent Activity' },
  { to: '/organizer/approvals', icon: '✋', label: 'Approvals' },
  { section: 'SYSTEM' },
  { to: '/organizer/notifications', icon: '🔔', label: 'Notifications' },
];

const participantLinks = [
  { section: 'MY HACKATHON' },
  { to: '/participant', icon: '📊', label: 'Dashboard', end: true },
  { to: '/participant/team', icon: '👥', label: 'My Team' },
  { to: '/participant/submission', icon: '📋', label: 'Submission' },
  { to: '/participant/chat', icon: '💬', label: 'AI Assistant' },
  { section: 'DISCOVER' },
  { to: '/participant/matches', icon: '🎯', label: 'Match Suggestions' },
  { to: '/participant/issues', icon: '🐛', label: 'Issues' },
  { to: '/participant/resources', icon: '📦', label: 'Resources' },
  { section: 'ACTIVITY' },
  { to: '/participant/notifications', icon: '🔔', label: 'Notifications' },
];

export default function Sidebar({ open, onClose }) {
  const navigate = useNavigate();
  const role = getRole();
  const links = isOrganizer() ? organizerLinks : participantLinks;

  const handleLogout = () => {
    clearToken();
    navigate('/');
  };

  return (
    <>
      <div className={`sidebar-overlay ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-header">
          <NavLink to={isOrganizer() ? '/organizer' : '/participant'} className="sidebar-logo" onClick={onClose}>
            <div className="sidebar-logo-icon">H</div>
            <span>HackOps</span>
          </NavLink>
        </div>

        <nav className="sidebar-nav">
          {links.map((link, i) =>
            link.section ? (
              <div key={i} className="sidebar-section-label">{link.section}</div>
            ) : (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
                onClick={onClose}
              >
                <span className="sidebar-link-icon">{link.icon}</span>
                <span>{link.label}</span>
              </NavLink>
            )
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user" onClick={handleLogout} role="button" tabIndex={0}>
            <div className="avatar avatar-sm">
              {isOrganizer() ? 'O' : 'P'}
            </div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">
                {isOrganizer() ? 'Organizer' : 'Participant'}
              </div>
              <div className="sidebar-user-role">
                {isOrganizer() ? 'Admin' : 'Hacker'}
              </div>
            </div>
            <span className="text-muted text-xs" title="Logout">⏻</span>
          </div>
        </div>
      </aside>
    </>
  );
}
