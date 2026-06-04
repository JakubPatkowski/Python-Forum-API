import { useState } from 'react';
import { useTranslation } from '../i18n/LangContext';
import { useAuth } from '../auth/AuthContext';
import { Avatar } from '../components/Avatar';
import { SectionHead } from '../components/SectionHead';
import { LoadingState, EmptyState, ErrorState } from '../components/States';
import {
  useAdminUsers,
  useAssignRole,
  useRevokeRole,
  useSetUserStatus,
  useGrantPermission,
} from '../hooks/useAdmin';

const ROLES = ['user', 'moderator', 'admin'];

/** Panel administratora — wymaga uprawnienia user.read.any (rola admin). */
export function AdminPage() {
  const t = useTranslation();
  const a = t.admin;
  const { hasPermission } = useAuth();
  const usersQ = useAdminUsers({ limit: 100 });

  if (!hasPermission('user.read.any')) {
    return <div className="shell"><div className="state-box state-error">{a.noAccess}</div></div>;
  }

  return (
    <div className="shell">
      <SectionHead title={a.title} meta={a.meta} />
      {usersQ.isLoading && <LoadingState />}
      {usersQ.isError && <ErrorState error={usersQ.error} onRetry={usersQ.refetch} />}
      {usersQ.isSuccess && usersQ.data.length === 0 && <EmptyState />}
      {usersQ.isSuccess && usersQ.data.length > 0 && (
        <div className="admin-list">
          {usersQ.data.map((u) => (
            <AdminUserRow key={u.id} user={u} a={a} />
          ))}
        </div>
      )}
    </div>
  );
}

function AdminUserRow({ user, a }) {
  const assignRole = useAssignRole();
  const revokeRole = useRevokeRole();
  const setStatus = useSetUserStatus();
  const grantPermission = useGrantPermission();

  const [roleToAdd, setRoleToAdd] = useState('');
  const [perm, setPerm] = useState('');
  const [open, setOpen] = useState(false);

  const userRoles = user.roles ?? [];
  const addableRoles = ROLES.filter((r) => !userRoles.includes(r));

  return (
    <div className="admin-row bracketed">
      <span className="br-tr" />
      <div className="admin-user">
        <Avatar userId={user.id} username={user.username} size="md" />
        <div>
          <div className="name">@{user.username}</div>
          <div className="mono dim" style={{ fontSize: 11 }}>{user.email}</div>
        </div>
      </div>

      <div className="admin-roles">
        {userRoles.length === 0 && <span className="mono mute">—</span>}
        {userRoles.map((r) => (
          <span className="badge accent role-chip" key={r}>
            {r}
            <button
              type="button"
              className="chip-x"
              title={a.deny}
              onClick={() => revokeRole.mutate({ userId: user.id, role: r })}
            >
              ✕
            </button>
          </span>
        ))}
        {addableRoles.length > 0 && (
          <span className="role-add">
            <select value={roleToAdd} onChange={(e) => setRoleToAdd(e.target.value)}>
              <option value="">+ {a.addRole}</option>
              {addableRoles.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            {roleToAdd && (
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  assignRole.mutate({ userId: user.id, role: roleToAdd });
                  setRoleToAdd('');
                }}
              >
                ✓
              </button>
            )}
          </span>
        )}
      </div>

      <div className="admin-status">
        <span className={'badge ' + (user.is_active ? 'ok' : 'warn')}>
          {user.is_active ? a.active : a.blocked}
        </span>
        <button
          type="button"
          className={'btn ' + (user.is_active ? '' : 'primary')}
          onClick={() => setStatus.mutate({ userId: user.id, blocked: user.is_active })}
          disabled={setStatus.isPending}
        >
          {user.is_active ? a.block : a.unblock}
        </button>
        <button type="button" className="link-btn" onClick={() => setOpen((v) => !v)}>
          {a.permissions}
        </button>
      </div>

      {open && (
        <div className="admin-perms" onClick={(e) => e.stopPropagation()}>
          <input
            placeholder={a.permission}
            value={perm}
            onChange={(e) => setPerm(e.target.value)}
          />
          <button
            type="button"
            className="btn"
            disabled={!perm.trim() || grantPermission.isPending}
            onClick={() => grantPermission.mutate({ userId: user.id, permission: perm.trim(), granted: true })}
          >
            {a.grant}
          </button>
          <button
            type="button"
            className="btn"
            disabled={!perm.trim() || grantPermission.isPending}
            onClick={() => grantPermission.mutate({ userId: user.id, permission: perm.trim(), granted: false })}
          >
            {a.deny}
          </button>
          {(user.permissions ?? []).length > 0 && (
            <div className="perm-list mono dim">{(user.permissions ?? []).join(', ')}</div>
          )}
        </div>
      )}
    </div>
  );
}
