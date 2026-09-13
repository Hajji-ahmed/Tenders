import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LogoFull, LogoMark } from "@/components/brand/Logo";

describe("Logo", () => {
  it("renders an accessible mark with the brand colors", () => {
    const { container } = render(<LogoMark />);
    expect(screen.getByRole("img", { name: "InnoSustain" })).toBeInTheDocument();
    expect(container.querySelector("circle")).toHaveAttribute("fill", "#ffcb05");
    expect(container.querySelectorAll("path[stroke='#0a9a47']")).toHaveLength(3);
  });

  it("renders the full wordmark", () => {
    render(<LogoFull />);
    expect(screen.getByText(/Innovative &/)).toBeInTheDocument();
    expect(screen.getByText(/Sustainable Solutions/)).toBeInTheDocument();
  });
});
