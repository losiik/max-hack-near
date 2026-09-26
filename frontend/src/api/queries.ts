import type { QueryClient, QueryFunctionContext } from '@tanstack/react-query';
import {
  getActiveAssistSessions,
  getAssistInvite,
  getAssistSession,
  getAssistState,
  getAssistSummary,
  getDemoInbox,
  getDevUsers,
  getServiceSessions,
  getMe,
  getOperatorQueue,
  getTrustedHelpers,
  getService,
  getServices,
  type AssistSession,
  type ServiceSession,
} from './client';

export const queryKeys = {
  devUsers: () => ['dev-users'] as const,
  services: () => ['services'] as const,
  service: (code: string) => ['services', code] as const,
  sessions: () => ['service-sessions'] as const,
  session: (id: string) => ['service-sessions', id] as const,
  demoInbox: (sessionId: string) => ['service-sessions', sessionId, 'demo-inbox'] as const,
  me: () => ['me'] as const,
  activeAssists: () => ['assist-sessions', 'active'] as const,
  assist: (id: string) => ['assist-sessions', id] as const,
  assistState: (id: string) => ['assist-sessions', id, 'state'] as const,
  assistSummary: (id: string) => ['assist-sessions', id, 'summary'] as const,
  assistInvite: (token: string) => ['assist-invites', token] as const,
  operatorQueue: () => ['operator', 'requests'] as const,
  trustedHelpers: () => ['trusted-helpers'] as const,
};

export const queryPolicy = {
  staleTime: 30_000,
} as const;

export function devUsersQuery({ signal }: QueryFunctionContext<ReturnType<typeof queryKeys.devUsers>>) {
  return getDevUsers(signal);
}

export function servicesQuery({ signal }: QueryFunctionContext<ReturnType<typeof queryKeys.services>>) {
  return getServices(signal);
}

export function serviceQuery({ queryKey, signal }: QueryFunctionContext<ReturnType<typeof queryKeys.service>>) {
  return getService(queryKey[1], signal);
}

export function sessionsQuery({ signal }: QueryFunctionContext<ReturnType<typeof queryKeys.sessions>>) {
  return getServiceSessions(signal);
}

export function demoInboxQuery({ queryKey, signal }: QueryFunctionContext<ReturnType<typeof queryKeys.demoInbox>>) {
  return getDemoInbox(queryKey[1], signal);
}

export function meQuery({ signal }: QueryFunctionContext<ReturnType<typeof queryKeys.me>>) {
  return getMe(signal);
}

export function activeAssistsQuery({ signal }: QueryFunctionContext<ReturnType<typeof queryKeys.activeAssists>>) {
  return getActiveAssistSessions(signal);
}

export function assistQuery({ queryKey, signal }: QueryFunctionContext<ReturnType<typeof queryKeys.assist>>) {
  return getAssistSession(queryKey[1], signal);
}

export function assistStateQuery({ queryKey, signal }: QueryFunctionContext<ReturnType<typeof queryKeys.assistState>>) {
  return getAssistState(queryKey[1], signal);
}

export function assistSummaryQuery({ queryKey, signal }: QueryFunctionContext<ReturnType<typeof queryKeys.assistSummary>>) {
  return getAssistSummary(queryKey[1], signal);
}

export function assistInviteQuery({ queryKey, signal }: QueryFunctionContext<ReturnType<typeof queryKeys.assistInvite>>) {
  return getAssistInvite(queryKey[1], signal);
}

export function operatorQueueQuery({ signal }: QueryFunctionContext<ReturnType<typeof queryKeys.operatorQueue>>) { return getOperatorQueue(signal); }
export function trustedHelpersQuery({ signal }: QueryFunctionContext<ReturnType<typeof queryKeys.trustedHelpers>>) { return getTrustedHelpers(signal); }

export function cacheSession(queryClient: QueryClient, session: ServiceSession): void {
  queryClient.setQueryData(queryKeys.session(session.id), session);
  queryClient.setQueryData<ServiceSession[]>(queryKeys.sessions(), (current = []) => {
    const withoutSession = current.filter((draft) => draft.id !== session.id);
    return [session, ...withoutSession];
  });
}

export function removeCachedSession(queryClient: QueryClient, sessionId: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.session(sessionId) });
  queryClient.setQueryData<ServiceSession[]>(queryKeys.sessions(), (current = []) =>
    current.filter((session) => session.id !== sessionId),
  );
}

export function cacheAssistSession(queryClient: QueryClient, session: AssistSession): void {
  queryClient.setQueryData(queryKeys.assist(session.id), session);
}
