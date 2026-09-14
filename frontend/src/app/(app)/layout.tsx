import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";

/** Gabarit applicatif : barre latérale fixe (desktop) + en-tête collant + contenu centré. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main id="main" className="flex-1">
          <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
