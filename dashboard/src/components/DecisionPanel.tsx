import { money, when } from "../format";
import type { RequestDetail } from "../types";

const VERBS = { approve: "Approve", decline: "Decline", escalate: "Escalate" };

export function DecisionPanel({
  request,
}: Readonly<{ request: RequestDetail }>) {
  const { decision, refund, send_back: sentBack } = request;
  return (
    <section className="panel" aria-labelledby="decision-heading">
      <h2 id="decision-heading">Decision</h2>
      {decision ? (
        <dl className="facts">
          <dt>Decision</dt>
          <dd>
            {VERBS[decision.decision]}
            {decision.amount === null ? "" : ` ${money(decision.amount)}`}
          </dd>
          <dt>Section</dt>
          <dd>{decision.section}</dd>
          <dt>Reason</dt>
          <dd>{decision.reason}</dd>
          <dt>Decided by</dt>
          <dd>
            {decision.decided_by}, {when(decision.decided_at)}
          </dd>
        </dl>
      ) : (
        <p className="muted">No decision yet.</p>
      )}
      {refund && (
        <p className="note tone-success">
          Refunded {money(refund.amount)} on {when(refund.issued_at)}
          {refund.signed_off_by
            ? `, signed off by ${refund.signed_off_by}`
            : ""}
        </p>
      )}
      {sentBack && (
        <p className="note tone-warning">
          Sent back by {sentBack.sent_by}: {sentBack.note}
        </p>
      )}
      {request.failure && (
        <p className="note tone-danger" role="alert">
          {request.failure}
        </p>
      )}
    </section>
  );
}
