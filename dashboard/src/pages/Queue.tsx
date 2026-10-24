import { Link } from "react-router";
import { listRequests } from "../api";
import { StateBadge } from "../components/StateBadge";
import { money, when } from "../format";
import type { RequestSummary } from "../types";
import { useLoad } from "../useLoad";

const EVERY = 2000;
const anyWorking = (requests: RequestSummary[]) =>
  requests.some((request) => request.state === "working");

export function Queue() {
  const queue = useLoad(listRequests, "queue", {
    every: EVERY,
    while: anyWorking,
  });
  if (queue.error) {
    return (
      <p className="note tone-danger" role="alert">
        {queue.error}
      </p>
    );
  }
  if (!queue.data) return <p className="muted">Loading…</p>;
  return (
    <section className="panel">
      <h1>Refund requests</h1>
      <table className="queue">
        <thead>
          <tr>
            <th scope="col">Request</th>
            <th scope="col">Customer</th>
            <th scope="col" className="number">
              Amount
            </th>
            <th scope="col">Submitted</th>
            <th scope="col">State</th>
          </tr>
        </thead>
        <tbody>
          {queue.data.map((request) => (
            <tr key={request.id}>
              <td className="id">
                <Link to={`/requests/${request.id}`}>{request.id}</Link>
              </td>
              <td>{request.customer_name}</td>
              <td className="number">{money(request.amount)}</td>
              <td>{when(request.submitted_at)}</td>
              <td>
                <StateBadge state={request.state} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
