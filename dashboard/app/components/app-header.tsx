/* eslint-disable @next/next/no-html-link-for-pages */

interface AppHeaderProps {
  active: "dashboard" | "reports";
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
          <span>全市场研究系统</span>
        </span>
      </a>
      <nav className="primary-nav" aria-label="主导航">
        <a className={active === "dashboard" ? "is-active" : ""} href="/">
          研究决策台
        </a>
        <a className={active === "reports" ? "is-active" : ""} href="/reports">
          研报库
        </a>
      </nav>
    </header>
  );
}
