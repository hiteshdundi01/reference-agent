import { money } from "../format";
import type { Order } from "../types";

// The order a request is about, with what a supervisor checks before signing
// off: what was bought, what was paid, and whether it arrived.
export function OrderPanel({ order }: Readonly<{ order: Order }>) {
  return (
    <section className="panel" aria-labelledby="order-heading">
      <h2 id="order-heading">Order {order.id}</h2>
      <table className="queue">
        <thead>
          <tr>
            <th scope="col">Item</th>
            <th scope="col" className="number">
              Price
            </th>
            <th scope="col" className="number">
              Quantity
            </th>
            <th scope="col">Final sale</th>
          </tr>
        </thead>
        <tbody>
          {order.items.map((item) => (
            <tr key={item.sku}>
              <td>{item.name}</td>
              <td className="number">{money(item.price)}</td>
              <td className="number">{item.quantity}</td>
              <td>{item.final_sale ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="facts order-facts">
        <dt>Shipping</dt>
        <dd>{money(order.shipping)}</dd>
        <dt>Paid</dt>
        <dd>{money(order.total)}</dd>
        <dt>Placed</dt>
        <dd>{order.placed_at}</dd>
        <dt>Delivery</dt>
        <dd>
          {order.delivered_at
            ? `Delivered ${order.delivered_at}`
            : `Expected ${order.expected_delivery}`}{" "}
          (carrier: {order.carrier_status})
        </dd>
      </dl>
    </section>
  );
}
