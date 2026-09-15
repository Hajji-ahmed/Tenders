import { describe, expect, it } from "vitest";

import { pollInterval } from "@/lib/queries/jobs";
import { configToFields, fieldsToConfig, SOURCE_KIND_LABELS, toSourcePayload } from "@/lib/sources";
import { TENDER_STATUS_LABELS, urgencyOf } from "@/lib/tenders";
import type { Job } from "@/lib/types";

describe("urgencyOf", () => {
  it("derives the urgency badge from the days left", () => {
    expect(urgencyOf(null)).toEqual({ level: "none", label: "Sans échéance" });
    expect(urgencyOf(-1)).toEqual({ level: "expired", label: "Dépassée" });
    expect(urgencyOf(0)).toEqual({ level: "critical", label: "Aujourd'hui" });
    expect(urgencyOf(2)).toEqual({ level: "critical", label: "2 j" });
    expect(urgencyOf(7)).toEqual({ level: "high", label: "7 j" });
    expect(urgencyOf(20)).toEqual({ level: "medium", label: "20 j" });
    expect(urgencyOf(45)).toEqual({ level: "low", label: "45 j" });
  });

  it("labels every workflow status in French", () => {
    expect(TENDER_STATUS_LABELS.NOUVEAU).toBe("Nouveau");
    expect(TENDER_STATUS_LABELS.NO_GO).toBe("No-go");
    expect(TENDER_STATUS_LABELS.PRET).toBe("Prêt");
  });
});

describe("pollInterval", () => {
  const job = (status: Job["status"]) => ({ status }) as Job;
  it("polls every 2 s while the job is pending or running, then stops", () => {
    expect(pollInterval(job("pending"))).toBe(2000);
    expect(pollInterval(job("running"))).toBe(2000);
    expect(pollInterval(job("done"))).toBe(false);
    expect(pollInterval(job("failed"))).toBe(false);
    expect(pollInterval(undefined)).toBe(2000);
  });
});

describe("source config mapping", () => {
  it("flattens the API config into form fields and back, per source kind", () => {
    const fields = configToFields({ include_domains: ["marchespublics.gov.ma", "ao.ma"], max_results: 5 });
    expect(fields).toEqual({
      include_domains: ["marchespublics.gov.ma", "ao.ma"],
      max_results: 5,
      listing_paths: [],
      link_pattern: "",
      render_js: false,
      max_links: null,
    });
    expect(
      fieldsToConfig("search_engine", { include_domains: ["ao.ma"], max_results: null, listing_paths: ["/x"], link_pattern: "", render_js: true, max_links: 3 }),
    ).toEqual({ include_domains: ["ao.ma"] });
    expect(
      fieldsToConfig("portal", { include_domains: ["ao.ma"], max_results: 5, listing_paths: ["/appels-offres"], link_pattern: "/ao/\\d+", render_js: true, max_links: 20 }),
    ).toEqual({ listing_paths: ["/appels-offres"], link_pattern: "/ao/\\d+", render_js: true, max_links: 20 });
    expect(fieldsToConfig("rss", { include_domains: [], max_results: null, listing_paths: [], link_pattern: "", render_js: false, max_links: null })).toEqual({});
    expect(SOURCE_KIND_LABELS.search_engine).toBe("Moteur de recherche");
  });
});

describe("toSourcePayload", () => {
  it("builds the API body from flat form values, keeping only the relevant config", () => {
    expect(
      toSourcePayload({ name: "Portail", kind: "portal", base_url: "https://p.ma", priority: null, is_enabled: true, listing_paths: ["/ao"], link_pattern: null, render_js: false, max_links: null, include_domains: ["x"], max_results: 9 }),
    ).toEqual({ name: "Portail", kind: "portal", base_url: "https://p.ma", priority: 100, is_enabled: true, config: { listing_paths: ["/ao"] } });
  });
});
