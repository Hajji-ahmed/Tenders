import Image from "next/image";
import { cn } from "cn";

/**
 * Logos officiels d'InnoSustain (« Innovative & Sustainable Solutions »), récupérés depuis
 * innosustain.africa (PNG transparents, vert #059541 / jaune #fdcd0e) :
 * - LogoMark : le symbole seul (disque jaune + arcs verts), pour la barre latérale et le favicon
 * - LogoFull : symbole + wordmark, pour la page de connexion et les exports
 * Les deux fonctionnent sur fond clair comme sur fond sombre.
 */

type MarkProps = { className?: string; size?: number; priority?: boolean };

export function LogoMark({ className, size = 36, priority = false }: MarkProps) {
  return (
    <Image
      src="/brand/iss_shortcut.png"
      alt="InnoSustain"
      width={size}
      height={size}
      priority={priority}
      className={cn("shrink-0 select-none", className)}
    />
  );
}

type FullProps = { className?: string; width?: number; priority?: boolean };

export function LogoFull({ className, width = 320, priority = false }: FullProps) {
  // Ratio du fichier officiel : 1072 × 267
  const height = Math.round((width * 267) / 1072);
  return (
    <Image
      src="/brand/iss_logo.png"
      alt="Innovative & Sustainable Solutions"
      width={width}
      height={height}
      priority={priority}
      className={cn("h-auto select-none", className)}
    />
  );
}
