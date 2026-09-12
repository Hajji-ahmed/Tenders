import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/auth/LoginForm";

describe("LoginForm", () => {
  it("submits email and password", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<LoginForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "secret123");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(onSubmit).toHaveBeenCalledWith({ email: "a@b.com", password: "secret123" });
  });

  it("shows an error message", () => {
    render(<LoginForm onSubmit={vi.fn()} error="Identifiants invalides" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Identifiants invalides");
  });

  it("does not submit an invalid email", async () => {
    const onSubmit = vi.fn();
    render(<LoginForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText(/email/i), "pas-un-email");
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "secret123");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
