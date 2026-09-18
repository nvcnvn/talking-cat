import type { Phase } from "../state/conversation";

interface Props {
  phase: Phase;
  level: number; // 0..1
}

/** SVG cat. Animation state comes from `phase`; the mouth opens with `level`. */
export function Cat({ phase, level }: Props) {
  const mouth = phase === "speaking" ? 3 + level * 9 : 2;
  return (
    <div className={`cat cat--${phase}`} data-testid="cat" data-phase={phase}>
      <svg viewBox="0 0 240 240" width="100%" height="100%" aria-hidden="true">
        {/* tail */}
        <path className="cat__tail" d="M60 190 C 20 200, 15 150, 45 140" stroke="#f4a261" strokeWidth="14" fill="none" strokeLinecap="round" />
        {/* body */}
        <ellipse cx="120" cy="185" rx="70" ry="45" fill="#f4a261" />
        <ellipse cx="120" cy="195" rx="42" ry="28" fill="#fde8d0" />
        {/* paws */}
        <ellipse cx="92" cy="222" rx="16" ry="10" fill="#f4a261" />
        <ellipse cx="148" cy="222" rx="16" ry="10" fill="#f4a261" />
        {/* head group */}
        <g className="cat__head">
          <path className="cat__ear cat__ear--l" d="M52 70 L62 18 L100 52 Z" fill="#f4a261" />
          <path className="cat__ear cat__ear--l" d="M62 62 L67 34 L88 54 Z" fill="#ffb4a2" />
          <path className="cat__ear cat__ear--r" d="M188 70 L178 18 L140 52 Z" fill="#f4a261" />
          <path className="cat__ear cat__ear--r" d="M178 62 L173 34 L152 54 Z" fill="#ffb4a2" />
          <ellipse cx="120" cy="100" rx="72" ry="62" fill="#f4a261" />
          <ellipse cx="120" cy="118" rx="36" ry="26" fill="#fde8d0" />
          {/* eyes */}
          <g className="cat__eyes">
            <ellipse className="cat__eye" cx="92" cy="90" rx="12" ry="14" fill="#2b2d42" />
            <ellipse className="cat__eye" cx="148" cy="90" rx="12" ry="14" fill="#2b2d42" />
            <circle cx="96" cy="85" r="4" fill="#fff" />
            <circle cx="152" cy="85" r="4" fill="#fff" />
          </g>
          {/* cheeks */}
          <circle cx="70" cy="112" r="9" fill="#ffb4a2" opacity=".8" />
          <circle cx="170" cy="112" r="9" fill="#ffb4a2" opacity=".8" />
          {/* nose */}
          <path d="M112 108 L128 108 L120 116 Z" fill="#e76f51" />
          {/* mouth */}
          <ellipse className="cat__mouth" cx="120" cy={126 + mouth} rx={6 + level * 3} ry={mouth} fill="#c0392b" />
          <path d="M108 116 Q114 122 120 116 Q126 122 132 116" stroke="#8d5524" strokeWidth="2.5" fill="none" strokeLinecap="round" />
          {/* whiskers */}
          <g stroke="#8d5524" strokeWidth="2" strokeLinecap="round" className="cat__whiskers">
            <path d="M50 108 L82 114" /><path d="M48 122 L82 122" />
            <path d="M190 108 L158 114" /><path d="M192 122 L158 122" />
          </g>
        </g>
        {phase === "thinking" && (
          <g className="cat__dots" fill="#2b2d42">
            <circle cx="196" cy="40" r="5" /><circle cx="212" cy="32" r="6" /><circle cx="230" cy="22" r="7" />
          </g>
        )}
        {phase === "listening" && (
          <g className="cat__ring" fill="none" stroke="#6ec6ff" strokeWidth="4">
            <circle cx="120" cy="110" r={100 + level * 12} />
          </g>
        )}
      </svg>
    </div>
  );
}
