/* eslint-disable @next/next/no-html-link-for-pages */

interface AppHeaderProps {
  active: "screening" | "dashboard" | "reports" | "industries" | "selection";
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
          <span>长期企业研究</span>
        </span>
      </a>
      <nav className="primary-nav" aria-label="主导航">
        <a className={active === "screening" ? "is-active" : ""} href="/screening">
          公司池
        </a>
        <a className={active === "dashboard" ? "is-active" : ""} href="/">
          研究决策台
        </a>
        <a className={active === "reports" ? "is-active" : ""} href="/reports">
          研报库
        </a>
        <a className={active === "industries" ? "is-active" : ""} href="/industries">
          产业研究
        </a>
        <a className={active === "selection" ? "is-active" : ""} href="/selection">
          长期精选
        </a>
      </nav>
    </header>
  );
}
