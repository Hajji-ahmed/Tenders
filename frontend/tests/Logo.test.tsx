import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LogoFull, LogoMark } from "@/components/brand/Logo";

describe("Logo", () => {
  it("renders the official mark with an accessible name", () => {
    render(<LogoMark size={40} />);
    const img = screen.getByRole("img", { name: "InnoSustain" });
    expect(img).toHaveAttribute("src", expect.stringContaining("iss_shortcut.png"));
    expect(img).toHaveAttribute("width", "40");
  });

  it("renders the full logo keeping the official aspect ratio", () => {
    render(<LogoFull width={536} />);
    const img = screen.getByRole("img", { name: "Innovative & Sustainable Solutions" });
    expect(img).toHaveAttribute("src", expect.stringContaining("iss_logo.png"));
    expect(img).toHaveAttribute("height", "134"); // 536 × 267 / 1072
  });
});
