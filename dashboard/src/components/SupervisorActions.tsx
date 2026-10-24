import { Check, Undo2 } from "lucide-react";
import { useState } from "react";
import { sendBack, signOff } from "../api";
import { money } from "../format";
import type { Decision } from "../types";
import { useAction } from "../useAction";

const LONGEST_NOTE = 1000;

export function SupervisorActions({
  requestId,
  decision,
  done,
}: Readonly<{
  requestId: string;
  decision: Decision;
  done: () => void;
}>) {
  const [note, setNote] = useState("");
  const signingOff = useAction(() => signOff(requestId, decision.id), done);
  const sending = useAction(() => sendBack(requestId, decision.id, note), done);
  const busy = signingOff.busy || sending.busy;
  const error = signingOff.error ?? sending.error;
  const amount = decision.amount === null ? "" : ` ${money(decision.amount)}`;

  return (
    <section className="panel" aria-labelledby="supervisor-heading">
      <h2 id="supervisor-heading">Waiting for a supervisor</h2>
      <button
        type="button"
        className="primary"
        disabled={busy}
        onClick={() => void signingOff.run()}
      >
        <Check size={16} aria-hidden="true" /> Sign off and refund{amount}
      </button>
      <label className="field">
        Note for the agent
        <textarea
          value={note}
          maxLength={LONGEST_NOTE}
          rows={3}
          onChange={(event) => {
            setNote(event.target.value);
          }}
        />
      </label>
      <button
        type="button"
        disabled={busy || note.trim() === ""}
        onClick={() => void sending.run()}
      >
        <Undo2 size={16} aria-hidden="true" /> Send back
      </button>
      {error && (
        <p className="note tone-danger" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
