import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Page provisoire — remplacée par le vrai dashboard en Phase 11.
export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Vue d&apos;ensemble de l&apos;activité appels d&apos;offres</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Bienvenue</CardTitle>
          <CardDescription>
            La plateforme est prête. Commencez par renseigner le profil d&apos;InnoSustain.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Les indicateurs (opportunités, échéances, scores) apparaîtront ici.
        </CardContent>
      </Card>
    </div>
  );
}
