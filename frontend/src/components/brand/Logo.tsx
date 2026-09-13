import { cn } from "cn";

/**
 * Logo InnoSustain (« Innovative & Sustainable Solutions »), reproduit en vectoriel :
 * disque jaune entouré de trois arcs verts, ouverture en haut à gauche.
 * Les couleurs sont celles de la charte (globals.css) et fonctionnent sur fond clair ou sombre.
 */

const GREEN = "#0a9a47";
const YELLOW = "#ffcb05";

// Cercle de rayon 113 centré en (135,135), angles mesurés dans le sens horaire depuis 12 h.
const ARCS = [
  "M 87.2 32.6 A 113 113 0 0 1 191.5 232.9", // 335° → 150° : grand arc par la droite
  "M 55.1 214.9 A 113 113 0 0 1 164.2 244.1", // 225° → 165° : arc bas
  "M 25.4 107.7 A 113 113 0 0 0 25.4 162.3", // 284° → 256° : segment gauche
];

type MarkProps = { className?: string; title?: string };

export function LogoMark({ className, title = "InnoSustain" }: MarkProps) {
  return (
    <svg
      viewBox="0 0 270 270"
      role="img"
      aria-label={title}
      className={cn("size-8 shrink-0", className)}
      fill="none"
    >
      <title>{title}</title>
      <circle cx="135" cy="135" r="70" fill={YELLOW} />
      {ARCS.map((d) => (
        <path key={d} d={d} stroke={GREEN} strokeWidth="30" strokeLinecap="round" />
      ))}
    </svg>
  );
}

type FullProps = { className?: string; markClassName?: string; textClassName?: string };

export function LogoFull({ className, markClassName, textClassName }: FullProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <LogoMark className={cn("size-12", markClassName)} />
      <p
        className={cn(
          "text-brand-green font-bold leading-[1.05] tracking-tight",
          "text-[1.15rem]",
          textClassName,
        )}
      >
        Innovative &amp;
        <br />
        Sustainable Solutions
        <sup className="ml-0.5 text-[0.45em] font-semibold align-super">®</sup>
      </p>
    </div>
  );
}
