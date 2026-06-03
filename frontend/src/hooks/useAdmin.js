import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api/resources';

const adminUsersKey = (params = {}) => ['admin', 'users', params];

export function useAdminUsers(params = {}) {
  return useQuery({
    queryKey: adminUsersKey(params),
    queryFn: () => adminApi.listUsers(params),
  });
}

function useAdminMutation(fn) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'users'] }),
  });
}

export function useAssignRole() {
  return useAdminMutation(({ userId, role }) => adminApi.assignRole(userId, role));
}

export function useRevokeRole() {
  return useAdminMutation(({ userId, role }) => adminApi.revokeRole(userId, role));
}

export function useGrantPermission() {
  return useAdminMutation(({ userId, permission, granted }) =>
    adminApi.grantPermission(userId, permission, granted),
  );
}

export function useSetUserStatus() {
  return useAdminMutation(({ userId, blocked }) =>
    adminApi.setStatus(userId, blocked),
  );
}
