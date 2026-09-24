import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QuestionsList } from "@/components/tenders/QuestionsList";
import type { Question } from "@/lib/types";

function question(over: Partial<Question>): Question {
  return {
    id: "q1",
    tender_id: "t1",
    requirement_id: "r1",
    requirement_code: "ADM-002",
    requirement_status: "INFO_MANQUANTE",
    is_mandatory: true,
    text: "Disposez-vous d'une attestation CNSS de moins de trois mois ?",
    priority: "CRITIQUE",
    status: "open",
    answer: null,
    created_at: "2026-09-21T11:00:00Z",
    updated_at: "2026-09-21T11:00:00Z",
    ...over,
  };
}

const questions: Question[] = [
  question({}),
  question({
    id: "q2",
    requirement_id: "r2",
    requirement_code: "EXP-001",
    requirement_status: "CONFORME",
    is_mandatory: false,
    priority: "IMPORTANTE",
    text: "Disposez-vous de deux références de plus de 3 000 points lumineux ?",
    status: "answered",
    answer: { id: "a1", answer: "Oui, deux chantiers de 4 000 points", answered_at: "2026-09-21T12:00:00Z" },
  }),
  question({
    id: "q3",
    requirement_id: "r3",
    requirement_code: "METH-001",
    requirement_status: "A_VERIFIER",
    is_mandatory: false,
    priority: "FACULTATIVE",
    text: "Qui rédige la note méthodologique ?",
    status: "skipped",
  }),
];

const noop = { onAnswer: vi.fn(), onSkip: vi.fn(), onGenerate: vi.fn() };

describe("QuestionsList", () => {
  it("groups questions by priority and shows the linked requirement and its status", () => {
    render(<QuestionsList questions={questions} {...noop} />);
    const groups = screen.getAllByRole("region");
    expect(groups.map((g) => g.getAttribute("aria-label"))).toEqual(["Critique", "Importante", "Facultative"]);

    const critical = within(groups[0]).getByRole("listitem");
    expect(critical).toHaveTextContent("attestation CNSS de moins de trois mois");
    expect(within(critical).getByText("ADM-002")).toBeInTheDocument();
    expect(within(critical).getByText("Information manquante")).toBeInTheDocument();

    const answered = within(groups[1]).getByRole("listitem");
    expect(answered).toHaveTextContent("Oui, deux chantiers de 4 000 points");
    expect(within(answered).getByText("Conforme")).toBeInTheDocument();
    expect(within(groups[2]).getByRole("listitem")).toHaveTextContent(/ignorée/i);
  });

  it("sends an answer and trims it", async () => {
    const onAnswer = vi.fn().mockResolvedValue(undefined);
    render(<QuestionsList questions={[questions[0]]} {...noop} onAnswer={onAnswer} />);
    await userEvent.type(screen.getByLabelText(/votre réponse à ADM-002/i), "  Oui, du 3 septembre  ");
    await userEvent.click(screen.getByRole("button", { name: /répondre/i }));
    expect(onAnswer).toHaveBeenCalledWith("q1", "Oui, du 3 septembre");
  });

  it("refuses an empty answer", async () => {
    const onAnswer = vi.fn();
    render(<QuestionsList questions={[questions[0]]} {...noop} onAnswer={onAnswer} />);
    await userEvent.click(screen.getByRole("button", { name: /répondre/i }));
    expect(onAnswer).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/votre réponse à ADM-002/i)).toHaveAttribute("aria-invalid", "true");
  });

  it("skips a question and allows changing an answer", async () => {
    const onSkip = vi.fn().mockResolvedValue(undefined);
    render(<QuestionsList questions={questions} {...noop} onSkip={onSkip} />);
    await userEvent.click(screen.getByRole("button", { name: /ignorer/i }));
    expect(onSkip).toHaveBeenCalledWith("q1");

    await userEvent.click(screen.getByRole("button", { name: /modifier la réponse/i }));
    expect(screen.getByLabelText(/votre réponse à EXP-001/i)).toHaveValue("Oui, deux chantiers de 4 000 points");
  });

  it("invites to generate the questions when there is none", async () => {
    const onGenerate = vi.fn();
    render(<QuestionsList questions={[]} {...noop} onGenerate={onGenerate} />);
    expect(screen.getByText(/aucune question/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /générer les questions/i }));
    expect(onGenerate).toHaveBeenCalledTimes(1);
  });

  it("disables the actions while a job runs", () => {
    render(<QuestionsList questions={questions} {...noop} busy />);
    expect(screen.getByRole("button", { name: /générer/i })).toBeDisabled();
    for (const button of screen.getAllByRole("button", { name: /répondre/i })) expect(button).toBeDisabled();
  });
});
