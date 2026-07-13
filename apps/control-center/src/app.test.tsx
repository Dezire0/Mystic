import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Metric, Status } from "./app";

describe("Control Center status components", () => {
  it("communicates a ready status with text as well as color", () => { render(<Status value="ready" />); expect(screen.getByText("ready")).toHaveClass("good"); });
  it("renders a labeled operational metric", () => { render(<Metric label="Worker health" value="ok" />); expect(screen.getByText("Worker health")).toBeVisible(); expect(screen.getByText("ok")).toBeVisible(); });
});
