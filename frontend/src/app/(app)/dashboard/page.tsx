import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Page provisoire — remplacée par le vrai dashboard en Phase 11.
export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <Card>
        <CardHeader>
          <CardTitle>Bienvenue</CardTitle>
          <CardDescription>
            La plateforme est prête. Commencez par renseigner le profil de l&apos;entreprise.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Les indicateurs (opportunités, échéances, scores) apparaîtront ici.
        </CardContent>
      </Card>
    </div>
  );
}
