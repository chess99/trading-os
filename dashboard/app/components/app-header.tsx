import Link from "next/link";

interface AppHeaderProps {
  active: "dashboard" | "reports";
}

export function AppHeader({ active }: AppHeaderProps) {
  return (
    <header className="app-header">
      <Link className="brand" href="/" aria-label="Trading OS 研究决策台首页">
        <span className="brand-mark" aria-hidden="true">
          TO
        </span>
        <span className="brand-copy">
          <strong>Trading OS</strong>
          <span>全市场研究系统</span>
        </span>
      </Link>
      <nav className="primary-nav" aria-label="主导航">
        <Link className={active === "dashboard" ? "is-active" : ""} href="/">
          研究决策台
        </Link>
        <Link className={active === "reports" ? "is-active" : ""} href="/reports">
          研报库
        </Link>
      </nav>
      <div className="header-meta">
        <span className="market-dot" aria-hidden="true" />
        <span>只读研究视图</span>
      </div>
    </header>
  );
}
