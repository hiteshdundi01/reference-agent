import { ArrowLeft, Play } from "lucide-react";
import { Link, useParams } from "react-router";
import { getOrder, getRequest, listSteps, startWork } from "../api";
import { useSignedIn } from "../auth";
import { DecisionPanel } from "../components/DecisionPanel";
import { OrderPanel } from "../components/OrderPanel";
import { StateBadge } from "../components/StateBadge";
import { Steps } from "../components/Steps";
import { SupervisorActions } from "../components/SupervisorActions";
import { money, when } from "../format";
import { STARTABLE } from "../states";
import type { Order, RequestDetail, Step } from "../types";
import { useAction } from "../useAction";
import { useLoad } from "../useLoad";

const EVERY = 1000;

interface Seen {
  request: RequestDetail;
  order: Order;
  steps: Step[];
}

const working = (seen: Seen) => seen.request.state === "working";

export function RequestPage() {
  const { id = "" } = useParams();
  const seen = useLoad(
    async (): Promise<Seen> => {
      const request = await getRequest(id);
      const [order, steps] = await Promise.all([
        getOrder(request.order_id),
        listSteps(id),
      ]);
      return { request, order, steps };
    },
    id,
    { every: EVERY, while: working },
  );
  const starting = useAction(() => startWork(id), seen.reload);
  const who = useSignedIn();

  if (seen.error) {
    return (
      <p className="note tone-danger" role="alert">
        {seen.error}
      </p>
    );
  }
  if (!seen.data) return <p className="muted">Loading…</p>;
  const { request, order, steps } = seen.data;
  const supervisor = who?.role === "supervisor";

  return (
    <div className="request">
      <Link to="/" className="back">
        <ArrowLeft size={16} aria-hidden="true" /> All requests
      </Link>
      <section className="panel" aria-labelledby="request-heading">
        <div className="title-row">
          <h1 id="request-heading">{request.id}</h1>
          <StateBadge state={request.state} />
        </div>
        <dl className="facts">
          <dt>Customer</dt>
          <dd>{request.customer_name}</dd>
          <dt>Order</dt>
          <dd className="id">{request.order_id}</dd>
          <dt>Asked for</dt>
          <dd>{money(request.amount)}</dd>
          <dt>Submitted</dt>
          <dd>{when(request.submitted_at)}</dd>
          <dt>Evidence</dt>
          <dd>{request.evidence}</dd>
          <dt>Reason</dt>
          <dd>{request.reason}</dd>
        </dl>
        {STARTABLE.includes(request.state) && (
          <button
            type="button"
            className="primary"
            disabled={starting.busy}
            onClick={() => void starting.run()}
          >
            <Play size={16} aria-hidden="true" /> Start the agent
          </button>
        )}
        {starting.error && (
          <p className="note tone-danger" role="alert">
            {starting.error}
          </p>
        )}
      </section>
      <OrderPanel order={order} />
      <DecisionPanel request={request} />
      {request.state === "held" && request.decision && supervisor && (
        <SupervisorActions
          requestId={request.id}
          decision={request.decision}
          done={seen.reload}
        />
      )}
      <section className="panel" aria-labelledby="steps-heading">
        <h2 id="steps-heading">The agent's steps</h2>
        <Steps steps={steps} />
      </section>
    </div>
  );
}
