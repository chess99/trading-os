/* eslint-disable @next/next/no-html-link-for-pages */

interface AppHeaderProps {
  active: "screening" | "dashboard" | "reports" | "industries" | "macro";
}

export function AppHeader({ active }: AppHeaderProps) {
  return (
    <header className="app-header">
      <a className="brand" href="/" aria-label="Trading OS 研究决策台首页">
        <span className="brand-mark" aria-hidden="true">
          TO
        </span>
        <span className="brand-copy">
          <strong>Trading OS</strong>
          <span>价值投资研究</span>
        </span>
      </a>
      <nav className="primary-nav" aria-label="主导航">
        <a className={(active === "dashboard" || active === "screening") ? "is-active" : ""} href="/">
          个股研究
        </a>
        <a className={active === "reports" ? "is-active" : ""} href="/reports">
          研报库
        </a>
        <a className={active === "industries" ? "is-active" : ""} href="/industries">
          行业研究
        </a>
        <a className={active === "macro" ? "is-active" : ""} href="/macro">
          宏观与市场
        </a>
      </nav>
    </header>
  );
}
