import { useState, useEffect, useCallback } from 'react';
import { fetchMyResourceAllocations, fetchAvailableResources, requestResource, returnResource } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';

export default function ParticipantResourcesPage() {
  const [allocations, setAllocations] = useState([]);
  const [pools, setPools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('available');
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    Promise.allSettled([fetchMyResourceAllocations(), fetchAvailableResources()])
      .then(([a, p]) => {
        if (a.status === 'fulfilled') setAllocations(a.value);
        if (p.status === 'fulfilled') setPools(p.value);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRequest = async (itemId) => {
    try {
      await requestResource(itemId);
      toast('Resource requested!', 'success');
      load();
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const handleReturn = async (allocId) => {
    try {
      await returnResource(allocId);
      toast('Resource returned!', 'success');
      load();
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  if (loading) return <LoadingSpinner text="Loading resources..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Resources</h1>
          <p className="page-subtitle">Available hackathon resources</p>
        </div>
      </div>

      <div className="tabs mb-6">
        <button className={`tab ${tab === 'available' ? 'active' : ''}`} onClick={() => setTab('available')}>Available</button>
        <button className={`tab ${tab === 'my' ? 'active' : ''}`} onClick={() => setTab('my')}>
          My Allocations
          {allocations.filter(a => a.status === 'allocated').length > 0 && (
            <span className="tab-count">{allocations.filter(a => a.status === 'allocated').length}</span>
          )}
        </button>
      </div>

      {tab === 'available' && (
        pools.length === 0 ? (
          <EmptyState icon="📦" title="No resources available" description="Resource pools will appear here when the organizer creates them." />
        ) : (
          <div className="resource-grid">
            {pools.map(pool => (
              <div key={pool.id} className="resource-card">
                <div className="resource-card-header">
                  <span className="resource-card-name">{pool.name}</span>
                  {pool.available_quantity === 0 && <span className="badge badge-error">Out of Stock</span>}
                </div>
                <div className="resource-card-type">{pool.resource_type}</div>
                <div className="resource-card-qty">
                  <span className="resource-qty-available">{pool.available_quantity}</span>
                  <span className="resource-qty-sep">/</span>
                  <span className="resource-qty-total">{pool.total_quantity}</span>
                  <span className="text-xs text-muted" style={{ marginLeft: '4px' }}>available</span>
                </div>
                <button
                  className="btn btn-primary btn-sm btn-full mt-2"
                  disabled={pool.available_quantity === 0}
                  onClick={() => handleRequest(pool.id)}
                >
                  {pool.available_quantity === 0 ? 'Out of Stock' : 'Request Resource'}
                </button>
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'my' && (
        allocations.length === 0 ? (
          <EmptyState icon="📦" title="No allocations" description="You haven't requested any resources yet." />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Allocated</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {allocations.map(a => (
                  <tr key={a.id}>
                    <td className="table-cell-primary">{a.resource_item?.name || '—'}</td>
                    <td>{a.resource_item?.resource_type || '—'}</td>
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
                    <td>
                      {a.status === 'allocated' && (
                        <button className="btn btn-secondary btn-sm" onClick={() => handleReturn(a.id)}>
                          Return
                        </button>
                      )}
                    </td>
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
