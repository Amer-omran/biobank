import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ user: null as null | { id: number; role: string } }));
vi.mock("@/components/providers", async (orig) => ({
  ...(await orig<typeof import("@/components/providers")>()),
  useAuth: () => ({ user: auth.user, loading: false, publicMode: true, hasRole: () => false, refresh: async () => {}, logout: async () => {} }),
}));

import { AnalysisResult } from "@/components/analysis-result";
import { LocaleProvider } from "@/components/providers";
import type { Analysis } from "@/lib/types";

const base: Analysis = {
  id: 7,
  created_at: "2026-11-23T10:00:00Z",
  status: "model_not_trained",
  model_state: "not_trained",
  language: { detected: "ar", confidence: 1, used: "ar", details: {} },
  warnings: [],
  model: null,
  prediction: null,
  explanation: {},
  similar_claims: [],
  verification_resources: [{ name: { en: "WHO", ar: "منظمة الصحة العالمية" }, url: "https://www.who.int/" }],
  health_topic: "vaccines",
  review_status: "not_required",
  final_label_name: null,
  text: "x",
  redactions: {},
  disclaimer: { en: "", ar: "" },
  reviews: null,
};

const wrap = (ui: React.ReactNode, locale: "ar" | "en" = "en") => render(<LocaleProvider initial={locale}>{ui}</LocaleProvider>);

describe("AnalysisResult", () => {
  beforeEach(() => {
    auth.user = null;
  });

  it("hides 'request expert review' from anonymous visitors and shows it to signed-in users", () => {
    const { unmount } = wrap(<AnalysisResult analysis={base} />);
    expect(screen.queryByText("Request expert review")).not.toBeInTheDocument();
    unmount();
    auth.user = { id: 1, role: "researcher" };
    wrap(<AnalysisResult analysis={base} />);
    expect(screen.getByText("Request expert review")).toBeInTheDocument();
  });

  it("shows an explicit no-prediction state when the model is not trained", () => {
    wrap(<AnalysisResult analysis={base} />);
    expect(screen.getAllByText("Model not trained").length).toBeGreaterThan(0);
    expect(screen.getByText(/No prediction was produced/)).toBeInTheDocument();
    expect(screen.queryByText("Model prediction:")).not.toBeInTheDocument();
    expect(screen.queryByText(/Calibrated probabilities/)).not.toBeInTheDocument();
  });

  it("never presents raw scores as confidence and shows abstention", () => {
    const a: Analysis = {
      ...base,
      status: "completed",
      model: { id: 1, version_tag: "ar-v1", base_model: "aubmindlab/bert-base-arabertv02" },
      prediction: {
        label: 1,
        label_name: "MISLEADING",
        display_label: "NEEDS_REVIEW",
        raw_scores: { SUPPORTED: 0.1, MISLEADING: 0.6, NEEDS_REVIEW: 0.3 },
        calibrated_probabilities: null,
        confidence: null,
        is_calibrated: false,
        abstained: true,
        abstention_threshold: 0.8,
      },
    };
    wrap(<AnalysisResult analysis={a} />);
    expect(screen.getByText(/this model is not calibrated/)).toBeInTheDocument();
    expect(screen.getByText(/uncalibrated softmax — not a confidence/)).toBeInTheDocument();
    expect(screen.getByText(/The model abstained/)).toBeInTheDocument();
  });

  it("renders Arabic labels", () => {
    wrap(<AnalysisResult analysis={base} />, "ar");
    expect(screen.getAllByText("النموذج غير مدرَّب").length).toBeGreaterThan(0);
    expect(screen.getByText("منظمة الصحة العالمية")).toBeInTheDocument();
  });
});
