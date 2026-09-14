import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());

// findBy* / waitFor : 5 s au lieu de 1 s (rendu lent sous charge).
configure({ asyncUtilTimeout: 5_000 });
