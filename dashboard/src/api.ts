import { post, request } from "./connection";
import type {
  Order,
  RequestDetail,
  RequestSummary,
  SignedIn,
  Step,
  User,
} from "./types";

// The dashboard's API on the backend: one function per operation it calls,
// named after the operation.

export const signIn = (email: string, password: string) =>
  post<SignedIn>("/sign-in", { email, password });

export const me = () => request<User>("/me");

export const listRequests = () => request<RequestSummary[]>("/requests");

export const getRequest = (id: string) =>
  request<RequestDetail>(`/requests/${id}`);

export const getOrder = (id: string) => request<Order>(`/orders/${id}`);

export const listSteps = (id: string) =>
  request<Step[]>(`/requests/${id}/steps`);

export const startWork = (id: string) =>
  post<RequestDetail>(`/requests/${id}/start`);

export const signOff = (id: string, decisionId: number) =>
  post<RequestDetail>(`/requests/${id}/sign-off`, { decision_id: decisionId });

export const sendBack = (id: string, decisionId: number, note: string) =>
  post<RequestDetail>(`/requests/${id}/send-back`, {
    decision_id: decisionId,
    note,
  });
