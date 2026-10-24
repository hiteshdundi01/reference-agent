// How amounts and times read on the dashboard.

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

const moments = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
});

export const money = (amount: number) => dollars.format(amount);

export const when = (iso: string) => moments.format(new Date(iso));
