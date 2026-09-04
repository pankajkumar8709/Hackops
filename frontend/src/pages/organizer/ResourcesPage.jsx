import { useState, useEffect } from 'react';
import { fetchResourcePools, fetchAllResourceAllocations } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';

export default function ResourcesPage() {
  const [pools, setPools] = useState([]);
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('pools');

  useEffect(() => {
    Promise.allSettled([fetchResourcePools(), fetchAllResourceAllocations()])
      .then(([p, a]) => {
        if (p.status === 'fulfilled') setPools(p.value);
        if (a.status === 'fulfilled') setAllocations(a.value);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner text="Loading resources..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Resources</h1>
          <p className="page-subtitle">{pools.length} resource pools · {allocations.length} allocations</p>
        </div>
      </div>

      <div className="tabs mb-6">
        <button className={`tab ${tab === 'pools' ? 'active' : ''}`} onClick={() => setTab('pools')}>
          Pools
        </button>
        <button className={`tab ${tab === 'allocations' ? 'active' : ''}`} onClick={() => setTab('allocations')}>
          Allocations
          {allocations.filter(a => a.status === 'allocated').length > 0 && (
            <span className="tab-count">{allocations.filter(a => a.status === 'allocated').length}</span>
          )}
        </button>
      </div>

      {tab === 'pools' && (
        pools.length === 0 ? (
          <EmptyState icon="📦" title="No resource pools" description="Resource pools will appear here once created." />
        ) : (
          <div className="resource-grid">
            {pools.map(pool => {
              const pct = pool.total_quantity > 0
                ? ((pool.total_quantity - pool.available_quantity) / pool.total_quantity * 100)
                : 0;
              return (
                <div key={pool.id} className="resource-card">
                  <div className="resource-card-header">
                    <span className="resource-card-name">{pool.name}</span>
                    {pool.available_quantity === 0 && <span className="badge badge-error">Out</span>}
                  </div>
                  <div className="resource-card-type">{pool.resource_type}</div>
                  <div className="resource-card-qty">
                    <span className="resource-qty-available">{pool.available_quantity}</span>
                    <span className="resource-qty-sep">/</span>
                    <span className="resource-qty-total">{pool.total_quantity}</span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className={`progress-fill ${pct > 80 ? 'error' : pct > 50 ? 'warning' : 'success'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-muted mt-2">
                    <span>{pool.allocated_count} allocated</span>
                    <span>{pool.overdue_count || 0} overdue</span>
                  </div>
                </div>
              );
            })}
          </div>
        )
      )}

      {tab === 'allocations' && (
        allocations.length === 0 ? (
          <EmptyState icon="📦" title="No allocations" description="Resource allocations will appear here." />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Team</th>
                  <th>Status</th>
                  <th>Allocated</th>
                  <th>Returned</th>
                </tr>
              </thead>
              <tbody>
                {allocations.map(a => (
                  <tr key={a.id}>
                    <td className="table-cell-primary">{a.resource_item?.name || '—'}</td>
                    <td>{a.team?.name || '—'}</td>
                    <td>
                      <span className={`badge badge-dot ${
                        a.status === 'allocated' ? 'badge-success' :
                        a.status === 'returned' ? 'badge-neutral' :
                        a.overdue ? 'badge-error' : 'badge-warning'
                      }`}>
                        {a.overdue ? 'overdue' : a.status}
                      </span>
                    </td>
                    <td className="text-xs text-muted">{new Date(a.allocated_at).toLocaleString()}</td>
                    <td className="text-xs text-muted">{a.returned_at ? new Date(a.returned_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
