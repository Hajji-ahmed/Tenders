"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { canDecide } from "@/lib/tenders";
import type { DecisionKind, TenderStatus } from "@/lib/types";

type Props = {
  status: TenderStatus;
  onDecide: (decision: DecisionKind, reason: string | null) => Promise<void> | void;
};

const COPY: Record<DecisionKind, { title: string; description: string; confirm: string }> = {
  go: {
    title: "Confirmer le GO",
    description: "L'opportunité passe en préparation de réponse. Le motif est conservé dans l'historique.",
    confirm: "Confirmer le GO",
  },
  no_go: {
    title: "Confirmer le NO-GO",
    description: "L'opportunité est écartée ; elle pourra être réexaminée plus tard. Un motif aide l'équipe à comprendre.",
    confirm: "Confirmer le NO-GO",
  },
};

/** Décision GO / NO-GO avec dialogue de motif ; seules les décisions permises par le cycle de vie sont actives. */
export function DecisionButtons({ status, onDecide }: Props) {
  const [pending, setPending] = useState<DecisionKind | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const goAllowed = canDecide(status, "go");
  const noGoAllowed = canDecide(status, "no_go");

  function open(decision: DecisionKind) {
    setReason("");
    setError(null);
    setPending(decision);
  }

  async function confirm() {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      await onDecide(pending, reason.trim() || null);
      setPending(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Décision impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => open("go")} disabled={!goAllowed}>
          <ThumbsUp />
          GO
        </Button>
        <Button variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" onClick={() => open("no_go")} disabled={!noGoAllowed}>
          <ThumbsDown />
          NO-GO
        </Button>
      </div>
      {!goAllowed && !noGoAllowed && (
        <p className="text-xs text-muted-foreground">Dossier déjà engagé : la décision se gère depuis le statut.</p>
      )}

      <Dialog open={pending !== null} onOpenChange={(o) => !o && !busy && setPending(null)}>
        <DialogContent>
          {pending && (
            <>
              <DialogHeader>
                <DialogTitle>{COPY[pending].title}</DialogTitle>
                <DialogDescription>{COPY[pending].description}</DialogDescription>
              </DialogHeader>
              <div className="space-y-2">
                <Label htmlFor="decision-reason">Motif (optionnel)</Label>
                <Textarea
                  id="decision-reason"
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder={pending === "go" ? "Ex. : secteur cible, références comparables…" : "Ex. : hors périmètre, budget insuffisant…"}
                />
              </div>
              {error && (
                <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </p>
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => setPending(null)} disabled={busy}>
                  Annuler
                </Button>
                <Button variant={pending === "go" ? "default" : "destructive"} onClick={confirm} disabled={busy}>
                  {busy ? "…" : COPY[pending].confirm}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
