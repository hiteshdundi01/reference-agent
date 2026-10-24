import { when } from "../format";
import type { Step, StepKind } from "../types";

const NAMES: Record<StepKind, string> = {
  started: "Started",
  model_call: "Model call",
  reply: "Agent",
  tool_call: "Looked up",
  tool_result: "Result",
  refusal: "Refused",
  decision: "Decision",
  signed_off: "Signed off",
  sent_back: "Sent back",
  failure: "Failed",
};

export function Steps({ steps }: Readonly<{ steps: Step[] }>) {
  if (steps.length === 0) return <p className="muted">No steps yet.</p>;
  return (
    <ol className="steps">
      {steps.map((step) => (
        <li key={step.id} className={`step kind-${step.kind}`}>
          <span className="step-kind">{NAMES[step.kind]}</span>
          <span className="step-text">{step.text}</span>
          <time className="step-time" dateTime={step.at}>
            {when(step.at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
