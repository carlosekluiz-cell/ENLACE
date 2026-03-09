/**
 * Inline script to prevent flash of wrong theme on page load.
 * Runs before React hydrates. The script content is a compile-time
 * constant string literal — no user input is interpolated, so this
 * is safe from XSS. This is a standard pattern used by next-themes,
 * Tailwind docs, and other theme libraries.
 */

// Static constant — not derived from any user input
const THEME_INIT_SCRIPT = '(function(){try{var t=localStorage.getItem("pulso_theme")||"light";if(t==="system"){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}if(t==="dark"){document.documentElement.classList.add("dark")}}catch(e){}})()';

export function ThemeScript() {
  return (
    // eslint-disable-next-line react/no-danger -- safe: static constant, no user input
    <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
  );
}
