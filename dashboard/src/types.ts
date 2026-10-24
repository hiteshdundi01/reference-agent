// The backend's records, as its API returns them.

export type State =
  | "waiting"
  | "working"
  | "stalled"
  | "held"
  | "refunded"
  | "declined"
  | "escalated"
  | "failed";

export type Role = "rep" | "supervisor";

export interface User {
  email: string;
  name: string;
  role: Role;
}

export interface SignedIn {
  token: string;
  user: User;
}

export interface RequestSummary {
  id: string;
  customer_name: string;
  order_id: string;
  amount: number;
  submitted_at: string;
  state: State;
}

export interface Decision {
  id: number;
  decision: "approve" | "decline" | "escalate";
  amount: number | null;
  section: string;
  reason: string;
  decided_by: string;
  decided_at: string;
}

export interface Refund {
  amount: number;
  issued_at: string;
  signed_off_by: string | null;
}

export interface SendBack {
  note: string;
  sent_by: string;
  sent_at: string;
  revision: number;
}

export interface RequestDetail extends RequestSummary {
  customer_id: string;
  evidence: string;
  reason: string;
  attempt: number;
  revision: number;
  failure: string | null;
  decision: Decision | null;
  refund: Refund | null;
  send_back: SendBack | null;
}

export type StepKind =
  | "started"
  | "model_call"
  | "reply"
  | "tool_call"
  | "tool_result"
  | "refusal"
  | "decision"
  | "signed_off"
  | "sent_back"
  | "failure";

export interface Step {
  id: number;
  attempt: number;
  at: string;
  kind: StepKind;
  text: string;
}

export interface Item {
  sku: string;
  name: string;
  price: number;
  quantity: number;
  final_sale: boolean;
}

export interface Order {
  id: string;
  customer_id: string;
  placed_at: string;
  expected_delivery: string;
  delivered_at: string | null;
  carrier_status: string;
  items: Item[];
  shipping: number;
  total: number;
}
