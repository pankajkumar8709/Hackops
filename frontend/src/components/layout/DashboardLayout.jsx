import { useState } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import { getToken } from '../../api';

export default function DashboardLayout({ title }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (!getToken()) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="layout">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="main-area">
        <TopBar title={title} onMenuToggle={() => setSidebarOpen(!sidebarOpen)} />
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
